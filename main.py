#!/usr/bin/env python3
"""
Tidal Voice Assistant - Main Application (Refactored)
"""

from audio_processor import AudioProcessor
from command_parser import MusicCommandParser
from tidal_player import TidalPlayer
from llm_parser import LLMCommandParser, has_command_verb
from config import setup_logging, CHROMECAST_PRECONNECT, COMMAND_PARSER, PLAYBACK_CUES, SPEAK_NOT_UNDERSTOOD, VERSION
import re
import sys

# Setup global logger
logger = setup_logging(__name__)

if '--version' in sys.argv:
    print(VERSION)
    sys.exit(0)
logger.info(f"Tidal Voice Assistant v{VERSION} starting")

# Instantiate components that will be used in callbacks
command_parser = MusicCommandParser()
tidal_player = TidalPlayer()
llm_parser = LLMCommandParser(library=tidal_player.library) if COMMAND_PARSER == 'gemini' else None

def print_banner():
    """Print application banner"""
    print("\n" + "=" * 60)
    print(f"  Tidal Voice Assistant for Raspberry Pi  v{VERSION}")
    print("=" * 60 + "\n")

was_playing = False


def on_wake_word_detected():
    """Called as soon as the wake word is heard. Must be fast: the user may still be talking."""
    global was_playing
    was_playing = tidal_player.is_playing()
    if was_playing:
        logger.debug("Music is playing - pausing for command")
        tidal_player.pause()


def on_prompt():
    """Called when the user paused after the wake word: short cue so they know we are listening."""
    tidal_player.play_audio_cue('wake')


def resume_if_needed():
    if was_playing:
        tidal_player.play()


def on_command_timeout():
    """Callback executed when command listening times out."""
    logger.warning("Command listening timed out.")
    if PLAYBACK_CUES:
        tidal_player.play_audio_cue('timeout')
    resume_if_needed()


WAKE_RE = re.compile(r"\b(ok|okay|okey|oye)\s+m[uú]sica\b", re.IGNORECASE)


WAKE_NOISE_WORDS = {"ok", "okay", "okey", "oye", "o", "aunque", "hemos", "música", "musica", "musical", "muy", "sica", "y", "e"}


def _after_wake(text):
    """The text with the wake phrase and Vosk's usual renderings of it removed from the front."""
    rest = WAKE_RE.sub(' ', text or '')
    rest = re.sub(r"[^\wáéíóúüñ]+", ' ', rest, flags=re.IGNORECASE).strip().lower()
    toks = rest.split()
    while toks and toks[0] in WAKE_NOISE_WORDS:
        toks.pop(0)
    return ' '.join(toks)


def _control_from(text):
    """A stop/pause/resume/skip command found by the regex parser in a transcript, or None."""
    rest = _after_wake(text)
    if not rest:
        return None
    local = command_parser.parse(rest)
    return local if local and local['action'] in ('stop', 'pause', 'resume', 'skip') else None


CONTROL_WORDS = {"para", "stop", "pausa", "siguiente", "salta", "sigue", "continúa", "continua"}


def _leading_control(text):
    """A control command when the first word after the wake phrase is one ("okey música para, ... zapatos")."""
    toks = _after_wake(text).split()
    if toks and toks[0] in CONTROL_WORDS:
        return command_parser.parse(toks[0])
    return None


def _is_wake_or_stub(text):
    """True when Gemini heard nothing beyond the wake phrase or a single word."""
    return len(_after_wake(text).split()) <= 1


def on_command_received(command):
    """
    Callback executed with the captured command: {'audio': bytes, 'transcript': str, 'sample_rate': int}.
    Gemini parses the audio; the regex parser is the fallback on the local transcript.
    Returns 'reprompt' when only the wake phrase was heard, so the audio processor listens again.
    """
    parsed = None
    if llm_parser and llm_parser.available:
        parsed = llm_parser.parse(command)
        if parsed and parsed['action'] == 'unknown':
            heard = parsed.get('transcript') or ''
            logger.info(f"Gemini heard no music command: '{heard}'")
            local = _control_from(heard) or _control_from(command.get('transcript'))
            if local:
                # Gemini missed a short control word ("okey música para" transcribed but not parsed, or caught only by Vosk)
                logger.info(f"Using control command '{local['action']}' from the transcript")
                parsed = local
            elif _is_wake_or_stub(heard):
                if not command.get('reprompted'):
                    # Only the wake phrase (or a lone verb, the user hesitated): cue and listen again
                    return 'reprompt'
                # Already cued once and still nothing: give up quietly
                resume_if_needed()
                return None
            parsed = None
            command['transcript'] = ''  # do not let the local transcript second-guess the model
        elif parsed and parsed['action'] not in ('stop', 'pause', 'resume', 'skip'):
            lead = _leading_control(parsed.get('transcript'))
            if lead:
                # "okey música para" followed by someone else talking: the control word said first wins
                logger.info(f"Control word '{lead['action']}' right after the wake phrase overrides {parsed['action']}")
                parsed = lead
            elif not has_command_verb(parsed.get('transcript')):
                # No "reproduce"/"pon"/"play": a conversation sentence taken for a title, never play it
                logger.warning(f"No command verb in '{parsed.get('transcript')}': ignoring {parsed['action']} '{parsed.get('query')}'")
                resume_if_needed()
                return None
    transcript = (command.get('transcript') or '').strip()
    if not parsed and transcript:
        parsed = command_parser.parse(transcript)
        if parsed:
            logger.debug(f"Regex parser used on '{transcript}'")
        elif len(transcript.split()) >= 2:
            # Verb lost (often masked by the wake cue): treat the rest as a song search
            parsed = {'action': 'play_song', 'query': transcript}
            logger.debug(f"No verb found, searching transcript as song: '{transcript}'")

    if not parsed:
        logger.warning(f"Could not understand command (transcript: '{command.get('transcript')}')")
        if SPEAK_NOT_UNDERSTOOD:
            # No cue here: a cue and TTS back to back race on the Chromecast socket
            tidal_player.speak("No te he entendido.", wait=True)
        resume_if_needed()
        return

    logger.debug(f"Parsed action: {parsed['action']}, query: '{parsed.get('query')}'")

    # Handle playback control commands
    action = parsed['action']
    if action == 'stop':
        # No spoken confirmation: the silence is the feedback
        tidal_player.stop()
    elif action == 'pause':
        tidal_player.pause()
    elif action == 'resume':
        tidal_player.play()
    elif action == 'skip':
        tidal_player.skip()  # skip() handles playback of next track internally
    else:
        # It's a music search command
        # Stop current playback first so the new search starts clean
        tidal_player.stop()

        search_type = command_parser.get_search_type(action)
        query = parsed.get('query')
        if query:
            success = tidal_player.smart_search_and_play(query, search_type, artist=parsed.get('artist'), artist_alternatives=parsed.get('artist_alternatives'), library_match=parsed.get('library_match'))
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
            on_timeout=on_command_timeout,
            on_prompt=on_prompt
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