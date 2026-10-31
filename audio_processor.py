"""
Audio front end: ALSA capture at 16 kHz, two Vosk recognizers fed in parallel, ring buffer for the LLM.

  arecord (plughw, 16 kHz mono)
    -> wake recognizer (grammar: wake phrases + [unk], ~3% CPU) detects "okey música"
    -> full recognizer (free vocabulary, ~12% of one core) transcribes the whole utterance
  On wake: on_wake_word() right away (pause music), then listen until speech energy (RMS over the noise
  floor tracked while idle) has been gone for END_SILENCE_SECONDS; Vosk's text is only a hint, because the
  small model misses quiet speech that Gemini hears. If nothing is heard EARLY_PROMPT_SECONDS after the wake
  word, on_prompt() plays a cue and we keep listening. Finally on_command({'audio', 'transcript',
  'sample_rate', 'reprompted'}) where audio is the ring buffer from just before the wake word to the end of
  speech; a return value of 'reprompt' from the handler cues once more without dropping the queued audio.
"""

import collections
import numpy as np
import json
import os
import subprocess
import time
from typing import Callable, Optional

from vosk import Model, KaldiRecognizer, SetLogLevel

from config import (
    VOSK_MODEL_PATH,
    SAMPLE_RATE,
    AUDIO_DEVICE,
    WAKE_WORDS,
    SPEECH_TIMEOUT,
    COMMAND_NO_SPEECH_TIMEOUT,
    AUDIO_PRE_WAKE_SECONDS,
    setup_logging,
)

logger = setup_logging(__name__)

CHUNK_MS = 100
CHUNK_BYTES = SAMPLE_RATE * 2 * CHUNK_MS // 1000
RING_SECONDS = 20
PROMPT_BLANK_SECONDS = 1.3  # Ignore transcript while the prompt cue plays on the speaker
WAKE_ONLY_SECONDS = 1.8     # A short final this soon after the wake word is probably the wake phrase alone
EARLY_PROMPT_SECONDS = 1.2  # Cue the user this long after the wake word if nothing else was heard
LEFTOVER_WAIT_SECONDS = 2.5 # After the cue, how long to wait before sending a short pre-cue text as the command
DEBUG_WAV_DIR = "/tmp/tidal-commands"
DEBUG_WAV_KEEP = 20         # wake-*.wav and timeout-*.wav kept per kind (/tmp is a 512 MB tmpfs on the Pi)
SPEECH_RMS_MIN = 350        # Absolute RMS floor for speech energy (16-bit samples)
SPEECH_RMS_RATIO = 2.5      # Speech must be this many times the tracked noise floor
END_SILENCE_SECONDS = 0.9   # Speech energy gone this long: the utterance is over
WAKE_CONFIRM_SECONDS = 2.5  # On a streaming trigger, re-decode this much audio with a fresh recognizer and require the phrase again
WAKE_STABLE_CHUNKS = 3      # The wake hypothesis must survive this many 100 ms chunks (grammar mode first guesses are often wrong)
WAKE_TAIL_SECONDS = 0.6     # Energy this soon after the wake detection is the tail of "música", not the command


class AudioProcessor:
    def __init__(self, on_wake_word: Callable[[], None], on_command: Callable[[dict], None],
                 on_timeout: Callable[[], None], on_prompt: Optional[Callable[[], None]] = None):
        self.on_wake_word = on_wake_word
        self.on_command = on_command
        self.on_timeout = on_timeout
        self.on_prompt = on_prompt or (lambda: None)

        SetLogLevel(-1)
        logger.info(f"Loading Vosk model from {VOSK_MODEL_PATH}")
        self.model = Model(VOSK_MODEL_PATH)
        grammar = json.dumps(list(WAKE_WORDS) + ["[unk]"], ensure_ascii=False)
        self.grammar = grammar
        self.wake_rec = KaldiRecognizer(self.model, SAMPLE_RATE, grammar)
        self.full_rec = KaldiRecognizer(self.model, SAMPLE_RATE)
        self.wake_phrases = [w.lower() for w in WAKE_WORDS]

        self.noise_floor = 300.0  # tracked while idle, used for the energy-based speech detector
        self.ring = collections.deque(maxlen=RING_SECONDS * 1000 // CHUNK_MS)
        self.proc: Optional[subprocess.Popen] = None
        self.running = False

    # ---- capture -------------------------------------------------------
    def _start_capture(self):
        cmd = ["arecord", "-q", "-D", AUDIO_DEVICE, "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", "1", "-t", "raw"]
        logger.info(f"Starting capture: {' '.join(cmd)}")
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)

    def _read_chunk(self) -> bytes:
        data = self.proc.stdout.read(CHUNK_BYTES)
        if not data:
            raise RuntimeError("arecord stream ended")
        self.ring.append(data)
        return data

    def _audio_since(self, chunks_ago: int) -> bytes:
        items = list(self.ring)
        return b"".join(items[-chunks_ago:]) if chunks_ago < len(items) else b"".join(items)

    # ---- helpers -------------------------------------------------------
    def _wake_text(self, chunk: bytes):
        """Returns (text, is_final) from the grammar recognizer."""
        if self.wake_rec.AcceptWaveform(chunk):
            return json.loads(self.wake_rec.Result()).get("text", ""), True
        return json.loads(self.wake_rec.PartialResult()).get("partial", ""), False

    def _confirm_wake(self) -> bool:
        """Re-decode the last WAKE_CONFIRM_SECONDS with a fresh grammar recognizer.

        The streaming recognizer carries state from the conversation before, and its hypothesis for a
        new segment is sometimes a wake phrase that a cold decode of the same audio never produces.
        On the day this was added, a cold decode found the phrase in 6 of 6 real wakes and 0 of 6 false ones.
        """
        audio = self._audio_since(int(WAKE_CONFIRM_SECONDS * 1000 / CHUNK_MS))
        rec = KaldiRecognizer(self.model, SAMPLE_RATE, self.grammar)
        finals, partials = [], []
        for i in range(0, len(audio), CHUNK_BYTES):
            if rec.AcceptWaveform(audio[i:i + CHUNK_BYTES]):
                finals.append(json.loads(rec.Result()).get("text", ""))
            else:
                partials.append(json.loads(rec.PartialResult()).get("partial", ""))
        finals.append(json.loads(rec.FinalResult()).get("text", ""))
        # Only a final result counts. Partial hypotheses briefly contain the phrase in ordinary
        # conversation ("oye papi", "o bien") and every one of the 5 false triggers on 2026-10-31
        # was a partial-only hit, while all 8 real wakes had the phrase in the final.
        heard = [t for t in finals if t]
        ok = any(any(phrase in t for phrase in self.wake_phrases) for t in heard)
        seen = sorted(set(heard or [t for t in partials if t]))[-3:]
        logger.debug(f"Wake re-decode {'confirmed' if ok else 'REJECTED'}{'' if heard else ' (partial only)'}: {seen}")
        return ok

    def _wake_in(self, text: str) -> bool:
        """The hypothesis is a wake phrase, possibly followed by [unk] (the user kept talking).

        Nothing may precede the phrase: in grammar mode the decoder's first guess for a new segment
        is often a wake phrase that gets revised a few chunks later, so the caller also requires the
        hypothesis to stay put for WAKE_STABLE_CHUNKS before trusting it.
        """
        toks = text.strip().lower().split()
        for phrase in self.wake_phrases:
            n = len(phrase.split())
            if toks[:n] == phrase.split() and all(t == "[unk]" for t in toks[n:]):
                return True
        return False

    def _full_text(self, chunk: bytes):
        """Returns (text, is_final). Vosk's endpointer marks the end of an utterance."""
        if self.full_rec.AcceptWaveform(chunk):
            return json.loads(self.full_rec.Result()).get("text", ""), True
        return json.loads(self.full_rec.PartialResult()).get("partial", ""), False

    def _is_wake(self, text: str) -> bool:
        t = text.strip().lower()
        return bool(t) and "[unk]" not in t and any(t.endswith(w) for w in self.wake_phrases)

    WAKE_NOISE = {"ok", "okay", "okey", "oye", "o", "aunque", "hemos", "música", "musica", "musical", "muy", "sica"}

    def _strip_wake(self, text: str) -> str:
        t = text.strip().lower()
        for w in self.wake_phrases:
            i = t.rfind(w)
            if i >= 0:
                t = t[i + len(w):].strip()
                break
        # Vosk often renders the wake phrase as "okay musical" or "aunque música": if nothing but
        # wake-like words remain, the user said only the wake phrase.
        if t and all(tok in self.WAKE_NOISE or len(tok) <= 2 for tok in t.split()):
            return ""
        return t

    # ---- main loop -----------------------------------------------------
    def run(self):
        self.running = True
        streak = 0  # consecutive chunks whose wake hypothesis held
        self._start_capture()
        logger.info(f"Listening for wake words {self.wake_phrases} on {AUDIO_DEVICE} @ {SAMPLE_RATE} Hz")
        try:
            while self.running:
                chunk = self._read_chunk()
                self._track_floor(self._rms(chunk))
                self._full_text(chunk)  # keep the full recognizer in sync with the stream
                text, final = self._wake_text(chunk)
                streak = streak + 1 if self._wake_in(text) else 0
                if streak >= WAKE_STABLE_CHUNKS or (final and streak):
                    streak = 0
                    self.wake_rec.Reset()
                    self._dump_wav(self._audio_since(int(2500 / CHUNK_MS)), "wake")
                    if not self._confirm_wake():
                        continue
                    logger.info(f"Wake word detected: '{text}'")
                    result = self._capture_command()
                    if result != "reprompt":
                        # Everything heard while the command was handled (TTS announcement, cue) is
                        # still queued in the pipe: drop it so the speaker cannot trigger us.
                        self._drain_backlog()
                    self.wake_rec.Reset()
                    self.full_rec.Reset()
                    if result == "reprompt":
                        # The handler heard only the wake phrase (or a lone verb): cue and listen again.
                        # The audio queued meanwhile is kept: the user may already be saying the command.
                        self.full_rec.Reset()
                        self._capture_command(reprompt=True)
                        self._drain_backlog()
                        self.wake_rec.Reset()
                        self.full_rec.Reset()
        except KeyboardInterrupt:
            logger.info("Interrupted")
        finally:
            self.cleanup()

    @staticmethod
    def _rms(chunk: bytes) -> float:
        a = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
        return float(np.sqrt(np.mean(a * a))) if len(a) else 0.0

    def _track_floor(self, rms: float):
        # Fast to drop, slow to rise: speech must not pull the floor up
        self.noise_floor += (0.2 if rms < self.noise_floor else 0.005) * (rms - self.noise_floor)

    def _is_speech(self, rms: float) -> bool:
        return rms > max(SPEECH_RMS_RATIO * self.noise_floor, SPEECH_RMS_MIN)

    COMMAND_WORDS = {"para", "stop", "pausa", "pausar", "sigue", "continúa", "continua", "siguiente", "salta", "otra", "reanuda"}

    def _ambiguous(self, cmd: str, since_wake: float) -> bool:
        """A short final right after the wake word: Vosk's rendering of 'okey música' or a one-word query."""
        toks = cmd.split()
        return since_wake < WAKE_ONLY_SECONDS and len(toks) <= 2 and not any(t in self.COMMAND_WORDS for t in toks)

    def _capture_command(self, reprompt=False):
        """Listen for the command after the wake word.

        Vosk's small model is deaf to quiet or distant speech that Gemini hears fine, so the
        end of the utterance is decided by speech energy (RMS over the tracked noise floor), not
        only by Vosk's endpointer. Whatever Vosk transcribed goes along as a hint.
        """
        t_wake = time.time()
        chunks_since_wake = 0
        prompted = reprompt
        t_prompt = t_wake if reprompt else None
        blanked = False  # transcript reset once the cue has leaked into the mic
        transcript = ""
        leftover = ""  # short text heard right after the wake word, kept in case it was the command
        deadline = t_wake + SPEECH_TIMEOUT
        last_partial = ""
        speech_seen = False
        t_last_speech = None
        floor = self.noise_floor
        if reprompt:
            logger.debug("Re-prompting for the command")
            self.on_prompt()
            deadline = t_wake + COMMAND_NO_SPEECH_TIMEOUT + SPEECH_TIMEOUT
        else:
            self.on_wake_word()

        def prompt_now(reason):
            nonlocal prompted, t_prompt, deadline
            prompted = True
            t_prompt = time.time()
            logger.debug(f"Wake word alone ({reason}), prompting for command")
            self.on_prompt()
            deadline = time.time() + COMMAND_NO_SPEECH_TIMEOUT + SPEECH_TIMEOUT

        def flush_final() -> str:
            return self._strip_wake(json.loads(self.full_rec.FinalResult()).get("text", ""))

        while time.time() < deadline:
            chunk = self._read_chunk()
            chunks_since_wake += 1
            now = time.time()
            since_wake = now - t_wake
            rms = self._rms(chunk)
            in_blank = t_prompt is not None and now - t_prompt < PROMPT_BLANK_SECONDS
            # Energy right after the wake detection is the tail of "música"; the cue leaks into the mic
            if rms > max(SPEECH_RMS_RATIO * floor, SPEECH_RMS_MIN) and not in_blank and (reprompt or since_wake > WAKE_TAIL_SECONDS):
                if not speech_seen:
                    logger.debug(f"Speech energy at {since_wake:.1f}s (rms {rms:.0f}, floor {floor:.0f})")
                speech_seen = True
                t_last_speech = now
            text, final = self._full_text(chunk)
            if final:
                cmd = self._strip_wake(text)
                if cmd and not prompted and self._ambiguous(cmd, since_wake) and not speech_seen:
                    logger.debug(f"Short final '{cmd}' {since_wake:.1f}s after the wake word: keeping it, prompting")
                    leftover = cmd
                    cmd = ""
                if cmd:
                    transcript = cmd
                    break
                if not prompted and not speech_seen:
                    prompt_now("final")
                continue
            if not prompted and since_wake > EARLY_PROMPT_SECONDS and not speech_seen and not self._strip_wake(text):
                # Nothing beyond the wake phrase yet: do not wait for Vosk's endpointer to cue the user
                prompt_now("silence")
            if t_prompt is not None and not blanked and not in_blank and not speech_seen:
                # The cue played on the speaker and leaked into the mic: start the transcript clean
                blanked = True
                if not self._strip_wake(text):
                    self.full_rec.Reset()
                    text = ""
            if text != last_partial:
                logger.debug(f"Partial: '{text}'")
                last_partial = text
            if speech_seen and now - t_last_speech > END_SILENCE_SECONDS:
                # The user stopped talking: take whatever Vosk has and let Gemini hear the audio
                transcript = flush_final()
                logger.debug(f"End of speech by energy at {since_wake:.1f}s")
                break
            if prompted and not speech_seen:
                waited = now - t_prompt
                quiet_limit = LEFTOVER_WAIT_SECONDS if leftover else COMMAND_NO_SPEECH_TIMEOUT
                if waited > quiet_limit:
                    if leftover:
                        break  # the short text after the wake word was the whole command
                    logger.info(f"No command after prompt (floor {floor:.0f})")
                    self._dump_wav(self._audio_since(chunks_since_wake + int(2000 / CHUNK_MS)), "timeout")  # 2 s before the wake too
                    self.on_timeout()
                    return None
        else:
            # Hit the hard cap mid-utterance: take whatever we have
            transcript = flush_final()

        transcript = (leftover + " " + transcript).strip()
        pre = 0 if reprompt else int(AUDIO_PRE_WAKE_SECONDS * 1000 / CHUNK_MS)
        audio = self._audio_since(chunks_since_wake + pre)
        logger.info(f"Command captured in {time.time() - t_wake:.1f}s ({len(audio) / (SAMPLE_RATE * 2):.1f}s audio): '{transcript}'")
        return self.on_command({"audio": audio, "transcript": transcript, "sample_rate": SAMPLE_RATE, "reprompted": prompted})

    @staticmethod
    def _dump_wav(audio: bytes, tag: str):
        """Keep the audio of a failed window in /tmp/tidal-commands for offline debugging."""
        try:
            import wave
            os.makedirs(DEBUG_WAV_DIR, exist_ok=True)
            with wave.open(os.path.join(DEBUG_WAV_DIR, f"{tag}-{time.strftime('%H%M%S')}.wav"), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(SAMPLE_RATE)
                w.writeframes(audio)
            import glob
            for old in sorted(glob.glob(os.path.join(DEBUG_WAV_DIR, f"{tag}-*.wav")))[:-DEBUG_WAV_KEEP]:
                os.remove(old)
        except OSError:
            pass

    def _drain_backlog(self):
        fd = self.proc.stdout.fileno()
        os.set_blocking(fd, False)
        dropped = 0
        try:
            while True:
                try:
                    data = os.read(fd, 65536)
                except BlockingIOError:
                    break
                if not data:
                    break
                dropped += len(data)
        finally:
            os.set_blocking(fd, True)
        if dropped:
            logger.debug(f"Dropped {dropped / (SAMPLE_RATE * 2):.1f}s of audio heard while handling the command")

    def cleanup(self):
        self.running = False
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        logger.info("Audio capture stopped")
