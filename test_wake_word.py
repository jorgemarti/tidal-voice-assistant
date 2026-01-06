#!/usr/bin/env python3
"""
Test and troubleshoot wake word detection
"""

import argparse
import sys
from wake_word import WakeWordDetector
from vosk import Model, KaldiRecognizer
import pyaudio
import json
from config import VOSK_MODEL_PATH, SAMPLE_RATE, CHUNK_SIZE

def test_basic_wake_word():
    """Test basic wake word detection"""
    print("=" * 60)
    print("Wake Word Detection Test")
    print("=" * 60)
    print()
    print("This test will listen for wake words:")
    print("  - 'Hey Tidal'")
    print("  - 'Oye Tidal'")
    print()
    print("Speak clearly and allow 1-2 seconds for detection")
    print("Press Ctrl+C to stop")
    print()

    try:
        with WakeWordDetector() as detector:
            count = 0
            while True:
                detected = detector.listen()
                if detected:
                    count += 1
                    print(f"✅ Wake word #{count} detected successfully!")
                    print("Waiting for next wake word...")
                    print()
    except KeyboardInterrupt:
        print(f"\n\nTest completed. Total wake words detected: {count}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

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

    try:
        model = Model(VOSK_MODEL_PATH)
        recognizer = KaldiRecognizer(model, SAMPLE_RATE)

        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
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
                    has_wake_word = ('hey tidal' in text_lower or 'oye tidal' in text_lower)

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
        stream.stop_stream()
        stream.close()
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

    try:
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
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
        stream.stop_stream()
        stream.close()
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
