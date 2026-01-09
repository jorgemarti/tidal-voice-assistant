"""
Centralized audio processing for voice assistant.

Uses a single full-model recognizer that detects wake words in the transcription,
allowing users to say wake word + command together naturally.
"""

import pyaudio
from vosk import Model, KaldiRecognizer
import json
import time
import re
from config import (
    VOSK_MODEL_PATH,
    SAMPLE_RATE,
    CHUNK_SIZE,
    WAKE_WORDS,
    SPEECH_TIMEOUT,
    AUDIO_INPUT_DEVICE_INDEX,
    setup_logging
)
from pathlib import Path

logger = setup_logging(__name__)

class AudioProcessor:
    """
    Handles all audio input, state management, and speech recognition.

    Uses a single full-model recognizer that detects wake words in transcriptions.
    This allows users to say "okay musica reproduce bohemian rhapsody" naturally
    without needing to pause between wake word and command.
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

        # Vosk Model
        model_path = VOSK_MODEL_PATH
        model_dir = Path(model_path)
        if not model_dir.exists():
            raise FileNotFoundError(f"Vosk model not found at: {model_path}")

        logger.info(f"Loading Vosk model from: {model_path}")
        self.model = Model(str(model_dir))

        # Wake phrases for detection
        self.wake_phrases = [phrase.lower().strip() for phrase in WAKE_WORDS]
        logger.info(f"Wake phrases: {self.wake_phrases}")

        # Single recognizer for both wake word detection and commands
        # Using full model (not grammar-restricted) to capture wake word + command together
        self.recognizer = KaldiRecognizer(self.model, SAMPLE_RATE)
        self.recognizer.SetMaxAlternatives(5)

        # Audio Stream
        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(
            rate=SAMPLE_RATE,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
            input_device_index=AUDIO_INPUT_DEVICE_INDEX
        )
        logger.info("Audio stream opened.")

    def run(self):
        """
        Starts the main audio processing loop.
        This is a blocking call.
        """
        logger.info(f"Starting audio processing loop. Initial state: {self.state}")
        self.stream.start_stream()

        try:
            while True:
                data = self.stream.read(CHUNK_SIZE, exception_on_overflow=False)

                if self.state == self.STATE_LISTENING_WAKE_WORD:
                    self._process_wake_word(data)
                elif self.state == self.STATE_LISTENING_COMMAND:
                    self._process_command(data)

        except KeyboardInterrupt:
            logger.info("Audio processing loop interrupted.")
        finally:
            self.cleanup()

    def _is_wake_word_match(self, text):
        """
        Check if text contains a wake word using flexible matching.
        Handles variations like "ok/okay/okey" and "musica/música/musical".

        Returns:
            tuple: (matched, end_index) - end_index is where command starts
        """
        text_lower = text.lower().strip()

        # Flexible pattern: ok/okay/okey/okei/oque + musica/música/musical
        # Handle variations from speech recognition
        pattern = r'\b(o[kq](?:a?y|e[iy]|ue)?)\s*(m[uú]sica?l?)\b'
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
                logger.info(f"Extracted command: '{command_text}'")
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
                logger.info(f"Heard: '{text}'")
                wake_found, command_text = self._extract_command_after_wake_word(text)

                if wake_found or was_pending:
                    if not was_pending:
                        logger.info(f"Wake word detected!")
                        self.on_wake_word()

                    if command_text:
                        # Command was included with wake word - process immediately
                        logger.info(f"Command included with wake word: '{command_text}'")
                        # Build alternatives list from result
                        alternatives = self._build_command_alternatives(result, command_text)
                        self.on_command(alternatives)
                        self.recognizer.Reset()
                    else:
                        # Only wake word was said - wait for command
                        self.state = self.STATE_LISTENING_COMMAND
                        self._command_listen_start_time = time.time()
                        self.recognizer.Reset()
                        logger.info(f"State changed to: {self.state}")
        else:
            # Check partial results for early wake word detection
            partial = json.loads(self.recognizer.PartialResult())
            partial_text = partial.get('partial', '').strip()
            if partial_text:
                logger.info(f"Partial: '{partial_text}'")

                # Check if wake word is in partial result
                wake_found, end_idx = self._is_wake_word_match(partial_text)
                if wake_found and not getattr(self, '_wake_word_pending', False):
                    logger.info(f"Wake word detected in partial!")
                    self._wake_word_pending = True
                    self.on_wake_word()  # Play beep to acknowledge

                    # Switch to command mode immediately
                    self.state = self.STATE_LISTENING_COMMAND
                    self._command_listen_start_time = time.time()
                    logger.info(f"State changed to: {self.state}")

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
        """Process audio while listening for command after wake word."""
        # Check for timeout first
        elapsed = time.time() - self._command_listen_start_time
        if elapsed > SPEECH_TIMEOUT:
            logger.warning(f"Command listening timed out after {elapsed:.1f}s")

            # Use last known partial if final result is empty
            final_result = self.recognizer.FinalResult()
            result = json.loads(final_result)
            if not result.get('text', '').strip() and self._last_command_partial:
                logger.info(f"Using last partial as command: '{self._last_command_partial}'")
                self._handle_command_from_text(self._last_command_partial)
            else:
                self._handle_command_result(final_result)

            self.on_timeout()
            self._reset_to_wake_word_state()
            return

        if self.recognizer.AcceptWaveform(data):
            result_json = self.recognizer.Result()
            result = json.loads(result_json)
            logger.debug(f"AcceptWaveform result: {result}")

            # If final result is empty but we have a partial, use the partial
            if not result.get('text', '').strip() and self._last_command_partial:
                logger.info(f"Empty result, using last partial: '{self._last_command_partial}'")
                self._handle_command_from_text(self._last_command_partial)
            else:
                self._handle_command_result(result_json)
            self._reset_to_wake_word_state()
        else:
            # Log partial results and save for fallback
            partial_result_json = self.recognizer.PartialResult()
            partial_result = json.loads(partial_result_json)
            partial_text = partial_result.get("partial", "")
            if partial_text:
                logger.info(f"Command partial: '{partial_text}'")
                self._last_command_partial = partial_text

    def _handle_command_from_text(self, text):
        """Handle command from raw text (e.g., from partial result)."""
        logger.info(f"Command heard: '{text}'")

        # Strip wake word if present
        matched, end_idx = self._is_wake_word_match(text)
        if matched:
            command = text[end_idx:].strip()
        else:
            command = text.strip()

        if command:
            logger.info(f"Command extracted: '{command}'")
            self.on_command([command])
        else:
            logger.warning("No command after wake word.")
            self.on_command([])

    def _handle_command_result(self, result_json):
        """Parse result JSON and invoke on_command callback if text is found."""
        result = json.loads(result_json)
        main_text = result.get('text', '').strip()

        if main_text:
            logger.info(f"Command heard: '{main_text}'")
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

            logger.info(f"Command alternatives: {cleaned}")
            self.on_command(cleaned)
        else:
            logger.warning("No command text was recognized.")
            self.on_command([])

    def _reset_to_wake_word_state(self):
        """Resets recognizer and state back to listening for wake word."""
        self.recognizer.Reset()
        self._wake_word_pending = False
        self._last_command_partial = ""
        self.state = self.STATE_LISTENING_WAKE_WORD
        logger.info(f"State changed back to: {self.state}")

    def cleanup(self):
        """Clean up audio resources."""
        if self.stream and self.stream.is_active():
            self.stream.stop_stream()
            self.stream.close()
        if self.audio:
            self.audio.terminate()
        logger.info("Audio processor cleaned up.")
