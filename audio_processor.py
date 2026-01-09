"""
Centralized audio processing for voice assistant.
"""

import pyaudio
from vosk import Model, KaldiRecognizer
import json
import time
from config import (
    VOSK_MODEL_PATH, 
    SAMPLE_RATE, 
    CHUNK_SIZE, 
    WAKE_WORDS, 
    SPEECH_TIMEOUT,
    setup_logging
)
from pathlib import Path

logger = setup_logging(__name__)

class AudioProcessor:
    """
    Handles all audio input, state management, and speech recognition.
    This class owns the audio stream and switches between two recognizers:
    1. A grammar-based recognizer for the wake word.
    2. A general-purpose recognizer for commands.
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

        # Vosk Model
        model_path = VOSK_MODEL_PATH
        model_dir = Path(model_path)
        if not model_dir.exists():
            raise FileNotFoundError(f"Vosk model not found at: {model_path}")
        
        logger.info(f"Loading Vosk model from: {model_path}")
        self.model = Model(str(model_dir))

        # Wake Word Recognizer (Grammar-based)
        self.wake_phrases = [phrase.lower().strip() for phrase in WAKE_WORDS]
        grammar = json.dumps(self.wake_phrases + ['[unk]'])
        self.wake_word_recognizer = KaldiRecognizer(self.model, SAMPLE_RATE, grammar)
        logger.info(f"Using restricted grammar for wake word: {self.wake_phrases}")

        # Command Recognizer (Full model)
        self.command_recognizer = KaldiRecognizer(self.model, SAMPLE_RATE)
        self.command_recognizer.SetMaxAlternatives(5)

        # Audio Stream
        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(
            rate=SAMPLE_RATE,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=CHUNK_SIZE
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
            
    def _process_wake_word(self, data):
        if self.wake_word_recognizer.AcceptWaveform(data):
            result = json.loads(self.wake_word_recognizer.Result())
            text = result.get('text', '').strip()
            
            if text and any(phrase in text for phrase in self.wake_phrases):
                logger.info(f"Wake word detected! (heard: '{text}')")
                self.on_wake_word()
                
                # Transition to command listening state
                self.state = self.STATE_LISTENING_COMMAND
                self._command_listen_start_time = time.time()
                logger.info(f"State changed to: {self.state}")

    def _process_command(self, data):
        # Check for timeout first
        if time.time() - self._command_listen_start_time > SPEECH_TIMEOUT:
            logger.warning("Command listening timed out.")
            
            # Process any partial result before timing out
            self._handle_command_result(self.command_recognizer.FinalResult())
            
            self.on_timeout()
            self._reset_to_wake_word_state()
            return
            
        if self.command_recognizer.AcceptWaveform(data):
            result_json = self.command_recognizer.Result()
            self._handle_command_result(result_json)
            self._reset_to_wake_word_state()

    def _handle_command_result(self, result_json):
        """Parse result JSON and invoke on_command callback if text is found."""
        result = json.loads(result_json)
        main_text = result.get('text', '').strip()
        
        if main_text:
            alternatives = [alt['text'] for alt in result.get('alternatives', []) if alt.get('text')]
            if main_text not in alternatives:
                alternatives.insert(0, main_text)
            
            logger.info(f"Command alternatives received: {alternatives}")
            self.on_command(alternatives)
        else:
            # This can happen on timeout with no partial result
            logger.warning("No command text was recognized.")
            self.on_command([]) # Send empty list to signify no command heard

    def _reset_to_wake_word_state(self):
        """Resets recognizers and state back to listening for wake word."""
        self.wake_word_recognizer.Reset()
        self.command_recognizer.Reset()
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
