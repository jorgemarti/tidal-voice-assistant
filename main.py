#!/usr/bin/env python3
"""
Tidal Voice Assistant - Main Application
Voice-controlled Tidal music player for Google Nest Mini via Raspberry Pi
"""

from wake_word import WakeWordDetector
from speech_recognition import SpeechRecognizer
from command_parser import MusicCommandParser
from tidal_player import TidalPlayer
from config import setup_logging
import sys

logger = setup_logging(__name__)

def print_banner():
    """Print application banner"""
    print()
    print("=" * 60)
    print("  Tidal Voice Assistant for Raspberry Pi")
    print("=" * 60)
    print()

def print_instructions():
    """Print usage instructions"""
    print("Instructions:")
    print("  1. Say 'Hey Tidal' or 'Oye Tidal' (wake word)")
    print("  2. Speak your music command in Spanish:")
    print()
    print("     Music playback:")
    print("     - 'reproduce bohemian rhapsody'")
    print("     - 'pon música de queen'")
    print("     - 'reproduce el álbum a night at the opera'")
    print("     - 'reproduce la playlist rock clásico'")
    print()
    print("     Playback controls:")
    print("     - 'para' or 'stop' (stop playback)")
    print("     - 'pausa' (pause)")
    print("     - 'continúa' or 'sigue' (resume)")
    print("     - 'siguiente' or 'salta' (skip track)")
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
        logger.info("Initializing components...")

        wake_detector = WakeWordDetector()
        # Share the Vosk model to save RAM (~250MB)
        speech_recognizer = SpeechRecognizer(model=wake_detector.get_model())
        command_parser = MusicCommandParser()
        tidal_player = TidalPlayer()

        logger.info("All components initialized successfully")
        print()
        print("=" * 60)
        print("  All components initialized successfully!")
        print("=" * 60)
        print()

        print_instructions()
        logger.info("Ready! Listening for wake word...")
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
                    logger.warning("No command detected, listening for wake word again...")
                    continue

                logger.info(f"Command received: '{command_text}'")

                # Parse command
                parsed = command_parser.parse(command_text)

                if not parsed:
                    logger.warning("Could not understand music command")
                    print("Try: 'reproduce [canción]' or 'pon música de [artista]'")
                    continue

                logger.info(f"Parsed action: {parsed['action']}, query: '{parsed['query']}'")

                # Handle playback control commands
                if parsed['action'] == 'stop':
                    tidal_player.stop()
                    logger.info("Playback stopped")
                    continue
                elif parsed['action'] == 'pause':
                    tidal_player.pause()
                    logger.info("Playback paused")
                    continue
                elif parsed['action'] == 'resume':
                    tidal_player.play()
                    logger.info("Playback resumed")
                    continue
                elif parsed['action'] == 'skip':
                    tidal_player.skip()
                    logger.info("Skipped to next track")
                    continue

                # Execute music search and playback with phonetic matching
                search_type = command_parser.get_search_type(parsed['action'])
                success = tidal_player.phonetic_search_and_play(parsed['query'], search_type)

                if success:
                    logger.info("Music is playing!")
                else:
                    logger.error("Could not play music")

                logger.info("Listening for wake word...")

            except KeyboardInterrupt:
                raise  # Re-raise to exit cleanly
            except Exception as e:
                logger.error(f"Error processing command: {e}")
                logger.info("Listening for wake word...")
                continue

    except KeyboardInterrupt:
        print()
        logger.info("Shutting down...")
        wake_detector.cleanup()
        speech_recognizer.cleanup()
        tidal_player.cleanup()
        logger.info("Goodbye!")

    except FileNotFoundError as e:
        logger.error(f"Configuration error: {e}")
        print()
        print("Make sure you have:")
        print("  1. Downloaded the Spanish Vosk model")
        print("  2. Set up your .env file with credentials")
        print()
        sys.exit(1)

    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
