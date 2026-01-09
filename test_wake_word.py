#!/usr/bin/env python3
"""
Test and troubleshoot wake word detection
"""

import argparse
import sys
from audio_processor import AudioProcessor
from vosk import Model, KaldiRecognizer
import pyaudio
import json
from config import VOSK_MODEL_PATH, SAMPLE_RATE, CHUNK_SIZE, AUDIO_INPUT_DEVICE_INDEX, WAKE_WORDS

def test_basic_wake_word():
    """Test basic wake word detection"""
    print("=" * 60)
    print("Wake Word Detection Test")
    print("=" * 60)
    print()
    print("This test will listen for wake words:")
    for phrase in WAKE_WORDS:
        print(f"  - '{phrase}'")
    print()
    print("Speak clearly and allow 1-2 seconds for detection")
    print("Press Ctrl+C to stop")
    print()

    count = 0
    
    def on_wake_word_callback():
        nonlocal count
        count += 1
        print(f"✅ Wake word #{count} detected successfully!")
        print("Waiting for next wake word...")
        print()

    def on_command_callback(alternatives):
        pass # Not used in wake word test

    def on_timeout_callback():
        pass # Not used in wake word test

    audio_processor = None
    try:
        audio_processor = AudioProcessor(
            on_wake_word=on_wake_word_callback,
            on_command=on_command_callback,
            on_timeout=on_timeout_callback
        )
        audio_processor.stream.start_stream()

        print("🎤 Listening for wake word... (Press Ctrl+C to stop)")
        while True:
            data = audio_processor.stream.read(CHUNK_SIZE, exception_on_overflow=False)
            if audio_processor.recognizer.AcceptWaveform(data):
                result = json.loads(audio_processor.recognizer.Result())
                text = result.get('text', '').strip()
                if text and any(phrase in text.lower() for phrase in audio_processor.wake_phrases):
                    on_wake_word_callback()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False
    finally:
        if audio_processor:
            audio_processor.cleanup()

    print(f"\n\nTest completed. Total wake words detected: {count}")
    return True

def test_continuous_transcription():
    """
    Continuous transcription test - shows everything Vosk hears.
    Useful for troubleshooting why wake word isn't detected.
    """
    print("=" * 60)
    print("Continuous Transcription Test (Debug Mode)")
    print("=" * 60)
    print()
    print("This will show EVERYTHING the system hears.")
    print("Use this to troubleshoot if wake word detection isn't working.")
    print()
    print("Try saying:")
    print("  - 'Hey Tidal'")
    print("  - 'Oye Tidal'")
    print("  - Any other Spanish phrases")
    print()
    print("Press Ctrl+C to stop")
    print()

    p = None
    stream = None
    try:
        model = Model(VOSK_MODEL_PATH)
        recognizer = KaldiRecognizer(model, SAMPLE_RATE)

        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
            input_device_index=AUDIO_INPUT_DEVICE_INDEX
        )

        print("🎤 Listening... (speak now)")
        print()

        while True:
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)

            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get('text', '').strip()

                if text:
                    # Check if it contains wake words
                    text_lower = text.lower()
                    has_wake_word = any(phrase in text_lower for phrase in WAKE_WORDS)

                    if has_wake_word:
                        print(f"✅ WAKE WORD DETECTED: '{text}'")
                    else:
                        print(f"   Heard: '{text}'")

    except KeyboardInterrupt:
        print("\n\nTest completed")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False
    finally:
        if stream and stream.is_active():
            stream.stop_stream()
            stream.close()
        if p:
            p.terminate()

    return True

def test_microphone():
    """Test microphone input levels"""
    print("=" * 60)
    print("Microphone Test")
    print("=" * 60)
    print()
    print("This test will show your microphone input levels.")
    print("Speak normally and check if levels are responding.")
    print()
    print("Press Ctrl+C to stop")
    print()

    p = pyaudio.PyAudio()
    stream = None
    try:
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
            input_device_index=AUDIO_INPUT_DEVICE_INDEX
        )

        print("🎤 Monitoring microphone... (speak now)")
        print()

        import struct
        import time

        last_print = time.time()

        while True:
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)

            # Calculate audio level
            audio_data = struct.unpack(f"{len(data)//2}h", data)
            peak = max(abs(x) for x in audio_data)
            level_percent = int((peak / 32768.0) * 100)

            # Print level every 0.5 seconds
            if time.time() - last_print > 0.5:
                bar_length = level_percent // 2
                bar = "█" * bar_length + "░" * (50 - bar_length)
                print(f"\rLevel: [{bar}] {level_percent:3d}%", end='', flush=True)
                last_print = time.time()

    except KeyboardInterrupt:
        print("\n\nTest completed")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False
    finally:
        if stream and stream.is_active():
            stream.stop_stream()
            stream.close()
        if p:
            p.terminate()

    return True

def main():
    parser = argparse.ArgumentParser(
        description='Test and troubleshoot wake word detection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_wake_word.py                    # Basic wake word test
  python test_wake_word.py --debug            # Show all transcriptions
  python test_wake_word.py --mic              # Test microphone levels
  python test_wake_word.py --all              # Run all tests sequentially

Troubleshooting:
  If wake word not detected:
    1. Run --mic to check microphone is working
    2. Run --debug to see what the system hears
    3. Ensure you're speaking clearly in Spanish
    4. Check that Vosk model is downloaded (vosk-model-es/)
        """
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Show continuous transcription (debug mode)'
    )

    parser.add_argument(
        '--mic',
        action='store_true',
        help='Test microphone input levels'
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Run all tests sequentially'
    )

    args = parser.parse_args()

    # Default: basic wake word test
    if not (args.debug or args.mic or args.all):
        return test_basic_wake_word()

    # Run specific test
    if args.mic or args.all:
        if not test_microphone():
            return False

        if args.all:
            print("\n")
            input("Press Enter to continue to transcription test...")
            print("\n")

    if args.debug or args.all:
        if not test_continuous_transcription():
            return False

        if args.all:
            print("\n")
            input("Press Enter to continue to wake word test...")
            print("\n")

    if args.all:
        return test_basic_wake_word()

    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)
