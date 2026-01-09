"""
Spanish speech recognition using Vosk
"""

import pyaudio
from vosk import Model, KaldiRecognizer
import json
from pathlib import Path
from config import VOSK_MODEL_PATH, SAMPLE_RATE, SPEECH_TIMEOUT, CHUNK_SIZE, setup_logging

logger = setup_logging(__name__)

class SpeechRecognizer:
    """
    Offline Spanish speech recognition using Vosk.
    Model: vosk-model-small-es-0.42 (Spanish from Spain)
    """

    def __init__(self, model_path=None, model=None):
        """
        Initialize speech recognizer with Spanish model.

        Args:
            model_path: Path to Vosk model directory (default: from config)
            model: Optional pre-loaded Vosk Model instance to share
        """
        if model:
            # Use shared model instance
            self.model = model
            self._owns_model = False
            logger.info("Using shared Vosk model for speech recognition")
        else:
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

            logger.info(f"Loading Spanish speech recognition model from: {model_path}")
            self.model = Model(str(model_dir))
            self._owns_model = True

        self.recognizer = KaldiRecognizer(self.model, SAMPLE_RATE)
        self.recognizer.SetMaxAlternatives(5)

        # Initialize PyAudio once and reuse
        self.audio = pyaudio.PyAudio()

        logger.info("Spanish speech recognizer initialized")
    
    def listen_for_command(self, timeout=None):
        """
        Listen for voice command after wake word.

        Args:
            timeout: Maximum seconds to listen (default: from config)

        Returns:
            A list of recognized text alternatives, with the best one first.
            Returns an empty list if no speech is detected.
        """
        timeout = timeout or SPEECH_TIMEOUT

        # Reset recognizer to ensure clean state for new command
        self.recognizer.Reset()

        stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )
        stream.start_stream()

        logger.info(f"Listening for command (timeout: {timeout}s)...")

        frames_read = 0
        max_frames = int(timeout * SAMPLE_RATE / CHUNK_SIZE)

        try:
            while frames_read < max_frames:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                frames_read += 1

                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    # Get all alternatives, starting with the main 'text'
                    main_text = result.get('text', '').strip()
                    if main_text:
                        # The 'alternatives' list already contains the main text as the first result
                        # with the highest confidence. We just need to extract the 'text' field.
                        alternatives = [alt['text'] for alt in result.get('alternatives', []) if alt.get('text')]
                        logger.info(f"Recognized alternatives: {alternatives}")
                        return alternatives

            # Get partial result if timeout reached
            result = json.loads(self.recognizer.FinalResult())
            main_text = result.get('text', '').strip()

            if main_text:
                alternatives = [alt['text'] for alt in result.get('alternatives', []) if alt.get('text')]
                # Ensure the main text is first if it's not in the alternatives list for some reason
                if main_text not in alternatives:
                    alternatives.insert(0, main_text)
                logger.info(f"Recognized (partial) alternatives: {alternatives}")
                return alternatives
            else:
                logger.warning("No speech detected")
                return []

        except Exception as e:
            logger.error(f"Error during speech recognition: {e}")
            return []
        finally:
            stream.stop_stream()
            stream.close()
    
    def listen_continuous(self, callback):
        """
        Continuously listen and call callback with recognized text.
        Useful for testing or alternative implementations.

        Args:
            callback: Function to call with recognized text
        """
        stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )

        logger.info("Listening continuously... (Press Ctrl+C to stop)")

        try:
            while True:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)

                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    text = result.get('text', '').strip()

                    if text:
                        callback(text)

        except KeyboardInterrupt:
            logger.warning("Continuous listening stopped")
        finally:
            stream.stop_stream()
            stream.close()

    def cleanup(self):
        """Clean up resources"""
        if hasattr(self, 'audio') and self.audio:
            self.audio.terminate()
            self.audio = None
        logger.info("Speech recognizer cleaned up")

if __name__ == "__main__":
    """Test Spanish speech recognition"""
    print("=" * 60)
    print("Spanish Speech Recognition Test")
    print("=" * 60)
    print()
    print("After starting, speak in Spanish for 5 seconds")
    print("Examples:")
    print("  - 'reproduce bohemian rhapsody'")
    print("  - 'pon música de queen'")
    print("  - 'reproduce el álbum de metallica'")
    print()
    input("Press Enter to start...")
    
    try:
        recognizer = SpeechRecognizer()
        alternatives = recognizer.listen_for_command()
        
        print()
        print("=" * 60)
        if alternatives:
            print(f"✅ Best guess: '{alternatives[0]}'")
            if len(alternatives) > 1:
                print("\nOther alternatives:")
                for i, alt in enumerate(alternatives[1:], 1):
                    print(f"  {i}. '{alt}'")
        else:
            print("❌ No speech recognized")
        print("=" * 60)
        
    except FileNotFoundError as e:
        print(f"\n❌ {e}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
