"""
Spanish speech recognition using Vosk
"""

import pyaudio
from vosk import Model, KaldiRecognizer
import json
from pathlib import Path
from config import VOSK_MODEL_PATH, SAMPLE_RATE, SPEECH_TIMEOUT, CHUNK_SIZE

class SpeechRecognizer:
    """
    Offline Spanish speech recognition using Vosk.
    Model: vosk-model-small-es-0.42 (Spanish from Spain)
    """
    
    def __init__(self, model_path=None):
        """
        Initialize speech recognizer with Spanish model.
        
        Args:
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
        
        print(f"Loading Spanish speech recognition model from: {model_path}")
        self.model = Model(str(model_dir))
        self.recognizer = KaldiRecognizer(self.model, SAMPLE_RATE)
        self.recognizer.SetWords(True)  # Enable word-level timestamps
        
        print("✅ Spanish speech recognizer initialized")
    
    def listen_for_command(self, timeout=None):
        """
        Listen for voice command after wake word.
        
        Args:
            timeout: Maximum seconds to listen (default: from config)
            
        Returns:
            Recognized text string in Spanish
        """
        timeout = timeout or SPEECH_TIMEOUT
        
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )
        stream.start_stream()
        
        print(f"🎤 Listening for command (timeout: {timeout}s)...")
        
        frames_read = 0
        max_frames = int(timeout * SAMPLE_RATE / CHUNK_SIZE)
        
        try:
            while frames_read < max_frames:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                frames_read += 1
                
                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    text = result.get('text', '').strip()
                    
                    if text:
                        print(f"✅ Recognized: '{text}'")
                        stream.stop_stream()
                        stream.close()
                        p.terminate()
                        return text
            
            # Get partial result if timeout reached
            result = json.loads(self.recognizer.FinalResult())
            text = result.get('text', '').strip()
            
            if text:
                print(f"✅ Recognized (partial): '{text}'")
            else:
                print("⚠️  No speech detected")
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            
            return text
            
        except Exception as e:
            print(f"❌ Error during speech recognition: {e}")
            stream.stop_stream()
            stream.close()
            p.terminate()
            return ""
    
    def listen_continuous(self, callback):
        """
        Continuously listen and call callback with recognized text.
        Useful for testing or alternative implementations.
        
        Args:
            callback: Function to call with recognized text
        """
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )
        
        print("🎤 Listening continuously... (Press Ctrl+C to stop)")
        
        try:
            while True:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                
                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    text = result.get('text', '').strip()
                    
                    if text:
                        callback(text)
                        
        except KeyboardInterrupt:
            print("\n⚠️  Continuous listening stopped")
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()

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
        text = recognizer.listen_for_command()
        
        print()
        print("=" * 60)
        if text:
            print(f"Final result: '{text}'")
        else:
            print("No speech recognized")
        print("=" * 60)
        
    except FileNotFoundError as e:
        print(f"\n❌ {e}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
