#!/usr/bin/env python3
"""
Tidal Voice Assistant - Main Application
Voice-controlled Tidal music player for Google Nest Mini via Raspberry Pi
"""

from wake_word import WakeWordDetector
from speech_recognition import SpeechRecognizer
from command_parser import MusicCommandParser
from tidal_player import TidalPlayer
import time
import sys

def print_banner():
    """Print application banner"""
    print()
    print("=" * 60)
    print("🎵 Tidal Voice Assistant for Raspberry Pi")
    print("=" * 60)
    print()

def print_instructions():
    """Print usage instructions"""
    print("Instructions:")
    print("  1. Say 'Hey Tidal' or 'Oye Tidal' (wake word)")
    print("  2. Speak your music command in Spanish:")
    print("     - 'reproduce bohemian rhapsody'")
    print("     - 'pon música de queen'")
    print("     - 'reproduce el álbum a night at the opera'")
    print()
    print("For other commands (weather, timers), use:")
    print("  'Ok Google, ¿qué tiempo hace?'")
    print("  'Ok Google, pon un temporizador de 5 minutos'")
    print()
    print("Press Ctrl+C to exit")
    print()

def main():
    """Main application loop"""
    print_banner()

    try:
        # Initialize components
        print("Initializing components...")
        print()

        wake_detector = WakeWordDetector()
        # Share the Vosk model to save RAM (~250MB)
        speech_recognizer = SpeechRecognizer(model=wake_detector.get_model())
        command_parser = MusicCommandParser()
        tidal_player = TidalPlayer()
        
        print()
        print("=" * 60)
        print("✅ All components initialized successfully!")
        print("=" * 60)
        print()
        
        print_instructions()
        print("🎤 Ready! Listening for wake word...")
        print()
        
        # Main loop
        while True:
            try:
                # Wait for wake word
                wake_detected = wake_detector.listen()
                
                if not wake_detected:
                    continue
                
                # Listen for command
                command_text = speech_recognizer.listen_for_command()
                
                if not command_text:
                    print("⚠️  No command detected, listening for wake word again...")
                    print()
                    continue
                
                print(f"📝 Command: '{command_text}'")
                
                # Parse command
                parsed = command_parser.parse(command_text)
                
                if not parsed:
                    print("❌ Could not understand music command")
                    print("   Try: 'reproduce [canción]' or 'pon música de [artista]'")
                    print()
                    continue
                
                print(f"🎯 Action: {parsed['action']}")
                print(f"🔍 Query: '{parsed['query']}'")
                print()
                
                # Execute
                search_type = command_parser.get_search_type(parsed['action'])
                success = tidal_player.search_and_play(parsed['query'], search_type)
                
                if success:
                    print()
                    print("✅ Music is playing!")
                else:
                    print()
                    print("❌ Could not play music")
                
                print()
                print("🎤 Listening for wake word...")
                print()
                
            except KeyboardInterrupt:
                raise  # Re-raise to exit cleanly
            except Exception as e:
                print(f"❌ Error processing command: {e}")
                print("🎤 Listening for wake word...")
                print()
                continue
    
    except KeyboardInterrupt:
        print()
        print()
        print("=" * 60)
        print("Shutting down...")
        print("=" * 60)
        wake_detector.cleanup()
        speech_recognizer.cleanup()
        tidal_player.cleanup()
        print("✅ Goodbye!")
        print()
        
    except FileNotFoundError as e:
        print()
        print(f"❌ Error: {e}")
        print()
        print("Make sure you have:")
        print("  1. Downloaded the Spanish Vosk model")
        print("  2. Set up your .env file with credentials")
        print()
        sys.exit(1)
        
    except Exception as e:
        print()
        print(f"❌ Fatal error: {e}")
        print()
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
