#!/usr/bin/env python3
"""
Tidal Voice Assistant - Main Application (Refactored)
"""

from audio_processor import AudioProcessor
from command_parser import MusicCommandParser
from tidal_player import TidalPlayer
from config import setup_logging, CHROMECAST_PRECONNECT
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
    # Context-aware prompting:
    # - If music is playing, pause first and use short prompt
    # - If idle, use full prompt
    if tidal_player.is_playing():
        logger.debug("Music is playing - pausing for command")
        tidal_player.pause()
        tidal_player.speak("¿Sí?", wait=True)
    else:
        tidal_player.speak("¿Qué quieres escuchar?", wait=True)

def on_command_timeout():
    """Callback executed when command listening times out."""
    logger.warning("Command listening timed out.")
    tidal_player.play_audio_cue('timeout')
    # Resume playback if it was paused for command listening
    tidal_player.play()
    
def on_command_received(alternatives):
    """
    Callback executed when a command is recognized.
    This contains the main application logic.
    """
    if not alternatives:
        logger.warning("No command detected, resuming playback...")
        tidal_player.play()  # Resume if was paused
        return

    logger.debug(f"Command alternatives received: {alternatives}")

    # Parse command by trying each alternative
    parsed = None
    for command_text in alternatives:
        parsed_attempt = command_parser.parse(command_text)
        if parsed_attempt:
            parsed = parsed_attempt
            logger.debug(f"Using parsed command from: '{command_text}'")
            break

    if not parsed:
        logger.warning("Could not understand music command from any alternative.")
        tidal_player.play_audio_cue('error')
        tidal_player.speak("No entendí el comando.", wait=True)
        tidal_player.play()  # Resume if was paused
        return

    logger.debug(f"Parsed action: {parsed['action']}, query: '{parsed.get('query')}'")

    # Handle playback control commands
    action = parsed['action']
    if action == 'stop':
        # Stop first, then confirm (so TTS can be heard)
        tidal_player.stop()
        tidal_player.speak("Música parada.")
    elif action == 'pause':
        tidal_player.pause()
    elif action == 'resume':
        tidal_player.play()
    elif action == 'skip':
        tidal_player.skip()  # skip() handles playback of next track internally
    else:
        # It's a music search command
        # Stop current playback first so TTS announcement can be heard
        tidal_player.stop()

        search_type = command_parser.get_search_type(action)
        query = parsed.get('query')
        if query:
            # TTS announcement happens inside phonetic_search_and_play after identifying the song
            success = tidal_player.phonetic_search_and_play(query, search_type)
            if not success:
                logger.error(f"Failed to play '{query}'")
        else:
            logger.error("Music command received without a query.")

def main():
    """Main application entry point."""
    print_banner()

    try:
        # Pre-connect to Chromecast if enabled (reduces first-command latency)
        if CHROMECAST_PRECONNECT:
            logger.info("Pre-connecting to Chromecast...")
            if tidal_player.find_chromecast():
                logger.info(f"Chromecast ready: {tidal_player.cast_device.name}")
            else:
                logger.warning("Chromecast pre-connect failed. Will retry on first command.")

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