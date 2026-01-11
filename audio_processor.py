"""
Centralized audio processing for voice assistant.

Hybrid Architecture:
- Wake word detection: Vosk (local, fast, offline)
- Command recognition: Google Speech API (cloud, accurate, free)
- Voice Activity Detection: webrtcvad (reduces CPU by filtering silence)

This allows users to say wake word + command together naturally,
with high accuracy for artist names, song titles, and commands.
"""

# Suppress ALSA/JACK warnings during PyAudio initialization
# These are harmless messages about missing audio configurations
import os
import sys
from contextlib import contextmanager

@contextmanager
def suppress_stderr():
    """Temporarily suppress stderr output (ALSA/JACK warnings)."""
    devnull = os.open(os.devnull, os.O_WRONLY)
    old_stderr = os.dup(2)
    os.dup2(devnull, 2)
    os.close(devnull)
    try:
        yield
    finally:
        os.dup2(old_stderr, 2)
        os.close(old_stderr)

with suppress_stderr():
    import pyaudio
from vosk import Model, KaldiRecognizer
import json
import time
import re
import struct
import numpy as np
from config import (
    VOSK_MODEL_PATH,
    SAMPLE_RATE,
    CHUNK_SIZE,
    WAKE_WORDS,
    WAKE_WORD_PATTERN,
    SPEECH_TIMEOUT,
    AUDIO_INPUT_DEVICE_INDEX,
    COMMAND_RECOGNITION,
    VAD_ENABLED,
    VAD_AGGRESSIVENESS,
    AUDIO_GAIN,
    setup_logging
)
from pathlib import Path

# Try to import webrtcvad for voice activity detection
try:
    import webrtcvad
    WEBRTCVAD_AVAILABLE = True
except ImportError:
    WEBRTCVAD_AVAILABLE = False

logger = setup_logging(__name__)

# Import cloud recognizer if enabled
if COMMAND_RECOGNITION == 'google':
    try:
        from cloud_recognizer import CloudRecognizer
        CLOUD_AVAILABLE = True
        logger.debug("Cloud speech recognition enabled (Google)")
    except ImportError as e:
        logger.warning(f"Cloud recognizer not available: {e}. Falling back to Vosk.")
        CLOUD_AVAILABLE = False
else:
    CLOUD_AVAILABLE = False
    logger.debug("Using Vosk for command recognition (cloud disabled)")

class AudioProcessor:
    """
    Handles all audio input, state management, and speech recognition.

    Hybrid Architecture:
    - Vosk: Wake word detection (local, fast, always listening)
    - Google Speech API: Command recognition (cloud, accurate, after wake word)

    This allows users to say "okay musica reproduce bohemian rhapsody" naturally
    with high accuracy for artist names and song titles.
    """

    STATE_LISTENING_WAKE_WORD = "LISTENING_WAKE_WORD"
    STATE_LISTENING_COMMAND = "LISTENING_COMMAND"

    def __init__(self, on_wake_word, on_command, on_timeout):
        """
        Initializes the audio processor.

        Args:
            on_wake_word (function): Callback to execute when wake word is detected.
            on_command (function): Callback to execute with command alternatives (list).
            on_timeout (function): Callback to execute when command listening times out.
        """
        # Callbacks
        self.on_wake_word = on_wake_word
        self.on_command = on_command
        self.on_timeout = on_timeout

        # State
        self.state = self.STATE_LISTENING_WAKE_WORD
        self._command_listen_start_time = 0
        self._last_command_partial = ""
        self._wake_word_pending = False

        # Audio buffer for cloud recognition
        self._audio_buffer = []

        # Cloud recognizer for commands (if enabled)
        self.cloud_recognizer = None
        if CLOUD_AVAILABLE:
            self.cloud_recognizer = CloudRecognizer()
            logger.debug("Cloud recognizer initialized for command recognition")

        # Vosk Model (used for wake word detection, fallback for commands)
        model_path = VOSK_MODEL_PATH
        model_dir = Path(model_path)
        if not model_dir.exists():
            raise FileNotFoundError(f"Vosk model not found at: {model_path}")

        logger.debug(f"Loading Vosk model from: {model_path}")
        self.model = Model(str(model_dir))

        # Wake phrases for detection
        self.wake_phrases = [phrase.lower().strip() for phrase in WAKE_WORDS]
        logger.debug(f"Wake phrases: {self.wake_phrases}")

        # Sliding window for partial results (to catch split wake words)
        self._recent_partials = []
        self._partial_window_size = 8  # Keep last N partials for better coverage

        # Build grammar for wake word detection (limited vocabulary mode)
        # This dramatically improves accuracy by constraining recognition
        # Include [unk] to handle non-wake-word speech without force-matching
        wake_word_grammar = self._build_wake_word_grammar()
        logger.debug(f"Wake word grammar: {wake_word_grammar}")

        # Vosk recognizer for wake word detection with constrained grammar
        # Using limited vocabulary mode for better accuracy
        self.recognizer = KaldiRecognizer(self.model, SAMPLE_RATE, wake_word_grammar)
        self.recognizer.SetMaxAlternatives(5)

        # Full vocabulary recognizer for command fallback (if cloud unavailable)
        self.command_recognizer = KaldiRecognizer(self.model, SAMPLE_RATE)
        self.command_recognizer.SetMaxAlternatives(5)

        # Voice Activity Detection (VAD) - reduces CPU by skipping silence
        self.vad_enabled = VAD_ENABLED
        self.vad = None
        self._silence_frames = 0
        self._speech_frames = 0
        self._vad_threshold = 300  # RMS threshold for energy-based VAD (lower = more sensitive)

        if self.vad_enabled:
            if WEBRTCVAD_AVAILABLE:
                # webrtcvad requires specific sample rates, use energy-based fallback for 44100Hz
                if SAMPLE_RATE in (8000, 16000, 32000, 48000):
                    self.vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
                    logger.debug(f"WebRTC VAD enabled (aggressiveness: {VAD_AGGRESSIVENESS})")
                else:
                    logger.debug(f"Using energy-based VAD (sample rate {SAMPLE_RATE}Hz not supported by webrtcvad)")
            else:
                logger.debug("Using energy-based VAD (webrtcvad not installed)")

        # Audio Stream - suppress ALSA/JACK warnings during initialization
        with suppress_stderr():
            self.audio = pyaudio.PyAudio()
            self.stream = self.audio.open(
                rate=SAMPLE_RATE,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=CHUNK_SIZE,
                input_device_index=AUDIO_INPUT_DEVICE_INDEX
            )
        logger.debug("Audio stream opened.")

    def run(self):
        """
        Starts the main audio processing loop.
        This is a blocking call.
        """
        logger.debug(f"Starting audio processing loop. Initial state: {self.state}")
        self.stream.start_stream()

        try:
            while True:
                data = self.stream.read(CHUNK_SIZE, exception_on_overflow=False)

                # Apply software gain if configured
                if AUDIO_GAIN != 1.0:
                    data = self._apply_gain(data, AUDIO_GAIN)

                if self.state == self.STATE_LISTENING_WAKE_WORD:
                    # Use VAD to skip processing silence (saves CPU)
                    if self._is_speech(data):
                        self._process_wake_word(data)
                    # Still feed silence to Vosk occasionally to maintain state
                    elif self._silence_frames % 10 == 0:
                        self.recognizer.AcceptWaveform(data)
                elif self.state == self.STATE_LISTENING_COMMAND:
                    # Always process during command listening
                    self._process_command(data)

        except KeyboardInterrupt:
            logger.info("Audio processing loop interrupted.")
        finally:
            self.cleanup()

    def _build_wake_word_grammar(self) -> str:
        """
        Build a JSON grammar string for constrained wake word recognition.

        Using limited vocabulary mode dramatically improves accuracy:
        - Vosk only tries to match these specific phrases
        - [unk] handles non-wake-word speech without force-matching
        - Reduces false positives and improves true positive rate

        Returns:
            JSON string array of wake phrases for Vosk grammar
        """
        # Comprehensive wake word variations
        # Include phonetic variations that Vosk might hear
        grammar_phrases = [
            # Standard forms
            "okay musica",
            "okey musica",
            "ok musica",
            "oque musica",
            # With "y" filler
            "okay y musica",
            "okey y musica",
            # Musical variant
            "okay musical",
            "okey musical",
            "ok musical",
            # Misrecognition variants
            "okay muchas",
            "okey muchas",
            "okay muy sica",
            "okey muy sica",
            "okay mi sica",
            "okey mi sica",
            # Split variants (Vosk sometimes splits words)
            "okay",
            "okey",
            "musica",
            "musical",
            # Unknown token for non-wake-word speech
            "[unk]",
        ]

        # Add configured wake words from config
        for phrase in self.wake_phrases:
            if phrase not in grammar_phrases:
                grammar_phrases.insert(0, phrase)

        return json.dumps(grammar_phrases)

    def _is_wake_word_match(self, text):
        """
        Check if text contains a wake word using flexible matching.
        Handles variations like "ok/okay/okey" and "musica/música/musical".

        Uses custom WAKE_WORD_PATTERN from config if set, otherwise uses default.

        Returns:
            tuple: (matched, end_index) - end_index is where command starts
        """
        text_lower = text.lower().strip()

        # Use custom pattern if configured, otherwise use default
        if WAKE_WORD_PATTERN:
            pattern = WAKE_WORD_PATTERN
        else:
            # Default: ok/okay/okey + optional filler words + musica/música/musical
            # Accepts common Vosk misrecognitions:
            # - "okay y música" (adds "y")
            # - "okay muchas" (mishears música)
            # - "muy sica", "muisica", "mi sica"
            # - "hokey", "a key" (prefix variations)
            # - "okeymusica" (joined without space)
            # Flexible pattern:
            # - Optional prefix: a, ha, h (for "a-kay", "hokey")
            # - Core: ok/oq + optional y/ey/ei/ue suffix
            # - Optional space (or joined)
            # - Optional filler: y, a, de
            # - música variants: musica, musical, muchas, muisica, muy sica, mi sica
            pattern = r'\b(?:a|ha?)?o[kq](?:a?y|e[iy]|ue)?\s*(?:y\s+|a\s+|de\s+)?(m[uú](?:y\s*|i\s*)?(?:sica?l?|chas?|isica))\b'
        match = re.search(pattern, text_lower)

        if match:
            logger.debug(f"Regex matched wake word: '{match.group()}'")
            return (True, match.end())

        # Also check exact phrases as fallback
        for phrase in self.wake_phrases:
            if phrase in text_lower:
                idx = text_lower.find(phrase)
                return (True, idx + len(phrase))

        return (False, 0)

    def _apply_gain(self, audio_data: bytes, gain: float) -> bytes:
        """
        Apply software gain to audio data.

        Args:
            audio_data: Raw PCM audio bytes (16-bit signed)
            gain: Multiplier (1.0 = no change, 2.0 = double volume)

        Returns:
            Amplified audio bytes, clipped to prevent distortion
        """
        # Convert to numpy array for fast processing
        samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
        # Apply gain
        samples *= gain
        # Clip to prevent distortion (int16 range: -32768 to 32767)
        samples = np.clip(samples, -32768, 32767)
        # Convert back to bytes
        return samples.astype(np.int16).tobytes()

    def _is_speech(self, audio_data: bytes) -> bool:
        """
        Check if audio contains speech using VAD.

        Uses webrtcvad if available and sample rate is compatible,
        otherwise falls back to energy-based detection.

        Args:
            audio_data: Raw PCM audio bytes (16-bit signed)

        Returns:
            True if speech detected, False otherwise
        """
        if not self.vad_enabled:
            return True  # Process all audio if VAD disabled

        # Energy-based VAD (works with any sample rate)
        try:
            # Convert bytes to samples
            samples = struct.unpack(f'{len(audio_data)//2}h', audio_data)
            # Calculate RMS (root mean square)
            rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
            is_speech = rms > self._vad_threshold

            # Adaptive threshold: adjust based on recent activity
            if is_speech:
                self._speech_frames += 1
                self._silence_frames = 0
            else:
                self._silence_frames += 1
                # Reset speech counter after prolonged silence
                if self._silence_frames > 30:  # ~0.5 seconds
                    self._speech_frames = 0

            return is_speech
        except Exception:
            return True  # On error, process audio anyway

    def _extract_command_after_wake_word(self, text):
        """
        Extract command text that follows a wake phrase.

        Args:
            text: Full transcription text

        Returns:
            tuple: (wake_phrase_found, command_text or None)
        """
        matched, end_idx = self._is_wake_word_match(text)

        if matched:
            command_text = text[end_idx:].strip()
            if command_text:
                logger.debug(f"Extracted command: '{command_text}'")
                return (True, command_text)
            else:
                return (True, None)

        return (False, None)

    def _process_wake_word(self, data):
        """Process audio looking for wake word, potentially with command attached."""
        if self.recognizer.AcceptWaveform(data):
            result = json.loads(self.recognizer.Result())
            text = result.get('text', '').strip()

            # Clear pending flag
            was_pending = getattr(self, '_wake_word_pending', False)
            self._wake_word_pending = False

            if text:
                # Always log what we heard for debugging
                logger.debug(f"Heard: '{text}'")
                wake_found, command_text = self._extract_command_after_wake_word(text)

                if wake_found or was_pending:
                    if not was_pending:
                        logger.debug("Wake word detected")
                        self.on_wake_word()

                    if command_text:
                        # Command was included with wake word - process immediately
                        logger.debug(f"Command included with wake word: '{command_text}'")
                        # Build alternatives list from result
                        alternatives = self._build_command_alternatives(result, command_text)
                        self.on_command(alternatives)
                        self.recognizer.Reset()
                    else:
                        # Only wake word was said - wait for command
                        # Reset and clear buffers for fresh command capture
                        self.recognizer.Reset()
                        self._audio_buffer = []
                        self._last_command_partial = ""
                        self.state = self.STATE_LISTENING_COMMAND
                        self._command_listen_start_time = time.time()
                        logger.debug(f"State changed to: {self.state}")
        else:
            # Check partial results for early wake word detection
            partial = json.loads(self.recognizer.PartialResult())
            partial_text = partial.get('partial', '').strip()
            if partial_text:
                logger.debug(f"Partial: '{partial_text}'")

                # Add to sliding window of recent partials
                self._recent_partials.append(partial_text)
                if len(self._recent_partials) > self._partial_window_size:
                    self._recent_partials.pop(0)

                # Check current partial AND combined recent partials for wake word
                # This catches cases where Vosk splits "okay" and "música"
                combined_text = ' '.join(self._recent_partials)
                wake_found, end_idx = self._is_wake_word_match(partial_text)
                if not wake_found:
                    wake_found, end_idx = self._is_wake_word_match(combined_text)

                if wake_found and not getattr(self, '_wake_word_pending', False):
                    logger.debug("Wake word detected in partial")
                    self._wake_word_pending = True
                    self.on_wake_word()  # Play TTS prompt (blocking)

                    # Reset recognizer and buffer AFTER TTS finishes
                    # This ensures we capture fresh audio for command
                    self.recognizer.Reset()
                    self._audio_buffer = []
                    self._last_command_partial = ""
                    self._recent_partials = []  # Clear sliding window

                    # Switch to command mode
                    self.state = self.STATE_LISTENING_COMMAND
                    self._command_listen_start_time = time.time()
                    logger.debug(f"State changed to: {self.state}")

    def _build_command_alternatives(self, result, primary_command):
        """
        Build alternatives list, extracting commands from each alternative transcription.
        """
        alternatives = [primary_command]

        for alt in result.get('alternatives', []):
            alt_text = alt.get('text', '').strip()
            if alt_text:
                _, alt_command = self._extract_command_after_wake_word(alt_text)
                if alt_command and alt_command not in alternatives:
                    alternatives.append(alt_command)

        return alternatives

    def _process_command(self, data):
        """
        Process audio while listening for command after wake word.

        Hybrid mode:
        - Collects audio into buffer for cloud recognition
        - Uses Vosk to detect speech end (AcceptWaveform)
        - Sends buffered audio to Google for accurate transcription
        - Falls back to Vosk if cloud recognition fails
        """
        # Always buffer audio for cloud recognition
        self._audio_buffer.append(data)

        # Check for timeout first
        elapsed = time.time() - self._command_listen_start_time
        if elapsed > SPEECH_TIMEOUT:
            logger.warning(f"Command listening timed out after {elapsed:.1f}s")
            self._finalize_command_recognition()
            self.on_timeout()
            self._reset_to_wake_word_state()
            return

        # Use full vocabulary recognizer to detect end of speech and for fallback transcription
        if self.command_recognizer.AcceptWaveform(data):
            logger.debug("Vosk detected end of speech")
            self._finalize_command_recognition()
            self._reset_to_wake_word_state()
        else:
            # Log partial results for debugging
            partial_result_json = self.command_recognizer.PartialResult()
            partial_result = json.loads(partial_result_json)
            partial_text = partial_result.get("partial", "")
            if partial_text:
                logger.debug(f"Vosk partial: '{partial_text}'")
                self._last_command_partial = partial_text

    def _finalize_command_recognition(self):
        """
        Finalize command recognition using cloud or Vosk fallback.

        Called when speech ends (Vosk AcceptWaveform) or timeout.
        """
        alternatives = []

        # Try cloud recognition first if available
        if self.cloud_recognizer and self._audio_buffer:
            logger.debug("Sending audio to Google Speech API...")
            audio_bytes = b''.join(self._audio_buffer)

            try:
                alternatives = self.cloud_recognizer.recognize_from_audio_data(
                    audio_bytes,
                    sample_rate=SAMPLE_RATE,
                    sample_width=2  # 16-bit audio
                )
            except Exception as e:
                logger.error(f"Cloud recognition failed: {e}")
                alternatives = []

        # Fall back to Vosk if cloud failed or unavailable
        if not alternatives:
            logger.debug("Using Vosk fallback for command recognition")
            final_result = self.command_recognizer.FinalResult()
            result = json.loads(final_result)

            main_text = result.get('text', '').strip()
            if main_text:
                alternatives = [main_text]
                # Add Vosk alternatives
                for alt in result.get('alternatives', []):
                    alt_text = alt.get('text', '').strip()
                    if alt_text and alt_text not in alternatives:
                        alternatives.append(alt_text)
            elif self._last_command_partial:
                logger.debug(f"Using last partial: '{self._last_command_partial}'")
                alternatives = [self._last_command_partial]

        # Clean up any wake word remnants from alternatives
        cleaned = []
        for alt in alternatives:
            matched, end_idx = self._is_wake_word_match(alt)
            if matched:
                cmd = alt[end_idx:].strip()
                if cmd:
                    cleaned.append(cmd)
            else:
                cleaned.append(alt)

        # Remove duplicates while preserving order
        seen = set()
        unique_alternatives = []
        for alt in cleaned:
            if alt and alt.lower() not in seen:
                seen.add(alt.lower())
                unique_alternatives.append(alt)

        if unique_alternatives:
            logger.debug(f"Command alternatives: {unique_alternatives}")
        else:
            logger.warning("No command recognized")

        self.on_command(unique_alternatives)

    def _handle_command_from_text(self, text):
        """Handle command from raw text (e.g., from partial result)."""
        logger.debug(f"Command heard: '{text}'")

        # Strip wake word if present
        matched, end_idx = self._is_wake_word_match(text)
        if matched:
            command = text[end_idx:].strip()
        else:
            command = text.strip()

        if command:
            logger.debug(f"Command extracted: '{command}'")
            self.on_command([command])
        else:
            logger.warning("No command after wake word.")
            self.on_command([])

    def _handle_command_result(self, result_json):
        """Parse result JSON and invoke on_command callback if text is found."""
        result = json.loads(result_json)
        main_text = result.get('text', '').strip()

        if main_text:
            logger.debug(f"Command heard: '{main_text}'")
            alternatives = [alt.get('text', '').strip() for alt in result.get('alternatives', []) if alt.get('text')]
            if main_text not in alternatives:
                alternatives.insert(0, main_text)

            # Filter out any accidental wake word captures in command phase
            cleaned = []
            for alt in alternatives:
                matched, end_idx = self._is_wake_word_match(alt)
                if matched:
                    cmd = alt[end_idx:].strip()
                    cleaned.append(cmd if cmd else alt)
                else:
                    cleaned.append(alt)

            # Remove empty strings
            cleaned = [c for c in cleaned if c]

            logger.debug(f"Command alternatives: {cleaned}")
            self.on_command(cleaned)
        else:
            logger.warning("No command text was recognized.")
            self.on_command([])

    def _reset_to_wake_word_state(self):
        """Resets recognizers and state back to listening for wake word."""
        self.recognizer.Reset()
        self.command_recognizer.Reset()
        self._wake_word_pending = False
        self._last_command_partial = ""
        self._audio_buffer = []  # Clear audio buffer
        self.state = self.STATE_LISTENING_WAKE_WORD
        logger.debug(f"State changed back to: {self.state}")

    def cleanup(self):
        """Clean up audio resources."""
        if self.stream and self.stream.is_active():
            self.stream.stop_stream()
            self.stream.close()
        if self.audio:
            self.audio.terminate()
        logger.debug("Audio processor cleaned up.")
