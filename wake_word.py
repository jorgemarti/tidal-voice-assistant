"""
Wake word detection using Vosk (fully offline)
"""

import pyaudio
from vosk import Model, KaldiRecognizer
import json
from pathlib import Path
from config import VOSK_MODEL_PATH, SAMPLE_RATE, CHUNK_SIZE

class WakeWordDetector:
    """
    Detects wake words using Vosk speech recognition.
    Fully offline, no external API dependencies.
    Default wake phrase: "hey tidal"
    """

    def __init__(self, wake_phrases=None, model_path=None):
        """
        Initialize wake word detector.

        Args:
            wake_phrases: List of wake phrase strings (default: ['hey tidal'])
            model_path: Path to Vosk model directory (default: from config)
        """
        model_path = model_path or VOSK_MODEL_PATH
        model_dir = Path(model_path)

        if not model_dir.exists():
            raise FileNotFoundError(
                f"Vosk model not found at: {model_path}\n"
                "Download it with:\n"
                "wget https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip\n"
                "unzip vosk-model-small-es-0.42.zip\n"
                "mv vosk-model-small-es-0.42 vosk-model-es"
            )

        # Wake phrases to detect (normalized to lowercase)
        self.wake_phrases = wake_phrases or ['hey tidal', 'oye tidal']
        self.wake_phrases = [phrase.lower().strip() for phrase in self.wake_phrases]

        print(f"Loading Vosk model for wake word detection from: {model_path}")
        self.model = Model(str(model_dir))
        self.recognizer = KaldiRecognizer(self.model, SAMPLE_RATE)

        self.audio = pyaudio.PyAudio()
        self.audio_stream = self.audio.open(
            rate=SAMPLE_RATE,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )

        print(f"✅ Wake word detector initialized (Vosk-based, fully offline)")
        print(f"   Listening for: {', '.join(self.wake_phrases)}")
        print(f"   Sample rate: {SAMPLE_RATE} Hz")

    def get_model(self):
        """
        Get the Vosk model instance for sharing with other components.

        Returns:
            Vosk Model instance
        """
        return self.model

    def _contains_wake_phrase(self, text):
        """
        Check if text contains any of the wake phrases.

        Args:
            text: Transcribed text to check

        Returns:
            True if wake phrase detected, False otherwise
        """
        text_lower = text.lower().strip()

        for phrase in self.wake_phrases:
            if phrase in text_lower:
                return True

        return False

    def listen(self):
        """
        Listen continuously for wake word.
        Returns True when wake word is detected.
        This is a blocking call.
        """
        try:
            while True:
                data = self.audio_stream.read(CHUNK_SIZE, exception_on_overflow=False)

                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    text = result.get('text', '').strip()

                    if text and self._contains_wake_phrase(text):
                        print(f"🎤 Wake word detected! (heard: '{text}')")
                        # Reset recognizer for next detection
                        self.recognizer = KaldiRecognizer(self.model, SAMPLE_RATE)
                        return True

        except KeyboardInterrupt:
            print("\n⚠️  Wake word detection interrupted")
            return False

    def cleanup(self):
        """Clean up resources"""
        if hasattr(self, 'audio_stream') and self.audio_stream:
            self.audio_stream.stop_stream()
            self.audio_stream.close()
        if hasattr(self, 'audio') and self.audio:
            self.audio.terminate()
        print("Wake word detector cleaned up")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

if __name__ == "__main__":
    """Test wake word detection"""
    print("=" * 60)
    print("Wake Word Detection Test")
    print("=" * 60)
    print()
    print("Say 'Hey Tidal' or 'Oye Tidal' to test wake word detection")
    print("Press Ctrl+C to exit")
    print()
    print("Note: Speak clearly and allow 1-2 seconds for detection")
    print()

    try:
        with WakeWordDetector() as detector:
            while True:
                detected = detector.listen()
                if detected:
                    print("✅ Wake word detected successfully!")
                    print("Waiting for next wake word...")
                    print()
    except KeyboardInterrupt:
        print("\n\nTest completed")
    except Exception as e:
        print(f"\n❌ Error: {e}")
