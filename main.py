#!/usr/bin/env python3
"""
Tidal Voice Assistant - Main Application (Refactored)
"""

from audio_processor import AudioProcessor
from command_parser import MusicCommandParser
from tidal_player import TidalPlayer
from config import setup_logging
import sys

# Setup global logger
logger = setup_logging(__name__)

# Instantiate components that will be used in callbacks
command_parser = MusicCommandParser()
tidal_player = TidalPlayer()

def print_banner():
    """Print application banner"""
    print("\n" + "=" * 60)
    print("  Tidal Voice Assistant for Raspberry Pi")
    print("=" * 60 + "\n")

def on_wake_word_detected():
    """Callback executed when wake word is detected."""
    tidal_player.play_activation_sound()

def on_command_timeout():
    """Callback executed when command listening times out."""
    logger.warning("Command listening timed out.")
    # You could have the assistant say "I'm still here" or similar
    
def on_command_received(alternatives):
    """
    Callback executed when a command is recognized.
    This contains the main application logic.
    """
    if not alternatives:
        logger.warning("No command detected, listening for wake word again...")
        return

    logger.info(f"Command alternatives received: {alternatives}")

    # Parse command by trying each alternative
    parsed = None
    for command_text in alternatives:
        parsed_attempt = command_parser.parse(command_text)
        if parsed_attempt:
            parsed = parsed_attempt
            logger.info(f"Using parsed command from: '{command_text}'")
            break

    if not parsed:
        logger.warning("Could not understand music command from any alternative.")
        tidal_player.speak("No entendí el comando.")
        return

    logger.info(f"Parsed action: {parsed['action']}, query: '{parsed.get('query')}'")

    # Handle playback control commands
    action = parsed['action']
    if action == 'stop':
        tidal_player.speak("Parando la música.")
        tidal_player.stop()
    elif action == 'pause':
        tidal_player.pause()
    elif action == 'resume':
        tidal_player.play()
    elif action == 'skip':
        tidal_player.skip()
    else:
        # It's a music search command, execute it
        search_type = command_parser.get_search_type(action)
        query = parsed.get('query')
        if query:
            # Announce what we're going to play
            search_type_spanish = {
                'track': 'la canción',
                'artist': 'música de',
                'album': 'el álbum',
                'playlist': 'la playlist'
            }.get(search_type, '')
            tidal_player.speak(f"Buscando {search_type_spanish} {query}.")

            success = tidal_player.phonetic_search_and_play(query, search_type)
            if not success:
                logger.error(f"Failed to play '{query}'")
        else:
            logger.error("Music command received without a query.")

def main():
    """Main application entry point."""
    print_banner()

    try:
        logger.info("Initializing audio processor...")
        
        # The AudioProcessor now orchestrates everything
        audio_processor = AudioProcessor(
            on_wake_word=on_wake_word_detected,
            on_command=on_command_received,
            on_timeout=on_command_timeout
        )
        
        logger.info("Initialization complete. Starting main loop...")
        
        # This is a blocking call that runs until KeyboardInterrupt
        audio_processor.run()

    except FileNotFoundError as e:
        logger.error(f"A required file was not found: {e}")
        print("\nERROR: Please ensure configuration is correct (e.g., .env file, Vosk model).")
        sys.exit(1)
        
    except Exception as e:
        logger.critical(f"A fatal error occurred: {e}", exc_info=True)
        sys.exit(1)

    print("\nApplication shut down gracefully.")

if __name__ == "__main__":
    main()