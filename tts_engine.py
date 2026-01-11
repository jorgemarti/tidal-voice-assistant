"""
Text-to-Speech engine with support for local (pyttsx3) and Google TTS.

For Chromecast playback:
- Local TTS: Generates audio file, serves via HTTP, casts URL
- Google TTS: Uses Google Translate TTS URL directly
"""

import os
import tempfile
import threading
import http.server
import socketserver
import socket
from contextlib import contextmanager
from pathlib import Path
from config import (
    TTS_ENGINE,
    TTS_LOCAL_RATE,
    TTS_LOCAL_VOICE,
    setup_logging
)

logger = setup_logging(__name__)


@contextmanager
def suppress_stderr():
    """Temporarily suppress stderr output (ALSA/JACK warnings)."""
    devnull = os.open(os.devnull, os.O_WRONLY)
    old_stderr = os.dup(2)
    os.dup2(devnull, 2)
    os.close(devnull)
    try:
        yield
    finally:
        os.dup2(old_stderr, 2)
        os.close(old_stderr)


# Try to import pyttsx3 for local TTS
PYTTSX3_AVAILABLE = False
try:
    with suppress_stderr():
        import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    logger.debug("pyttsx3 not available, local TTS disabled")


def get_local_ip() -> str:
    """Get the local IP address for serving files."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class QuietHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler that doesn't log to console."""

    def __init__(self, *args, directory=None, **kwargs):
        self.directory = directory
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format, *args):
        """Suppress HTTP server logging."""
        pass


class TTSServer:
    """Simple HTTP server for serving TTS audio files."""

    def __init__(self, port: int = 8766):
        self.port = port
        self.server = None
        self.thread = None
        self.temp_dir = tempfile.mkdtemp(prefix="tts_")
        self.local_ip = get_local_ip()

    def start(self):
        """Start the HTTP server in a background thread."""
        if self.server:
            return

        handler = lambda *args: QuietHTTPHandler(*args, directory=self.temp_dir)

        try:
            self.server = socketserver.TCPServer(("", self.port), handler)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            logger.debug(f"TTS server started on port {self.port}")
        except OSError as e:
            logger.warning(f"Could not start TTS server: {e}")
            self.server = None

    def stop(self):
        """Stop the HTTP server."""
        if self.server:
            self.server.shutdown()
            self.server = None

    def get_url(self, filename: str) -> str:
        """Get the URL for a file served by this server."""
        return f"http://{self.local_ip}:{self.port}/{filename}"

    def cleanup(self):
        """Clean up temp files."""
        import shutil
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass


class TTSEngine:
    """
    Text-to-Speech engine supporting local and Google TTS.

    Usage:
        engine = TTSEngine()
        url = engine.get_tts_url("Hola mundo", lang="es")
        # Cast url to Chromecast
    """

    def __init__(self):
        self.engine_type = TTS_ENGINE
        self.pyttsx_engine = None
        self.server = None
        self._file_counter = 0

        if self.engine_type == 'local' and PYTTSX3_AVAILABLE:
            try:
                with suppress_stderr():
                    self.pyttsx_engine = pyttsx3.init()
                    self.pyttsx_engine.setProperty('rate', TTS_LOCAL_RATE)

                # Set voice if specified
                if TTS_LOCAL_VOICE:
                    voices = self.pyttsx_engine.getProperty('voices')
                    for voice in voices:
                        if TTS_LOCAL_VOICE.lower() in voice.name.lower():
                            self.pyttsx_engine.setProperty('voice', voice.id)
                            break

                # Start HTTP server for serving audio files
                self.server = TTSServer()
                self.server.start()

                logger.debug("Local TTS engine initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize local TTS: {e}. Falling back to Google TTS.")
                self.engine_type = 'google'
        elif self.engine_type == 'local':
            logger.warning("pyttsx3 not available. Falling back to Google TTS.")
            self.engine_type = 'google'

    def get_tts_url(self, text: str, lang: str = 'es') -> str:
        """
        Get a URL for TTS audio.

        Args:
            text: Text to speak
            lang: Language code (default: 'es' for Spanish)

        Returns:
            URL that can be cast to Chromecast
        """
        if self.engine_type == 'local' and self.pyttsx_engine and self.server:
            return self._generate_local_tts(text)
        else:
            return self._get_google_tts_url(text, lang)

    def _generate_local_tts(self, text: str) -> str:
        """Generate TTS audio locally and return URL."""
        try:
            self._file_counter += 1
            filename = f"tts_{self._file_counter}.mp3"
            filepath = os.path.join(self.server.temp_dir, filename)

            # Generate audio file
            self.pyttsx_engine.save_to_file(text, filepath)
            self.pyttsx_engine.runAndWait()

            # Return URL to the file
            return self.server.get_url(filename)
        except Exception as e:
            logger.error(f"Local TTS failed: {e}. Falling back to Google.")
            return self._get_google_tts_url(text, 'es')

    def _get_google_tts_url(self, text: str, lang: str = 'es') -> str:
        """Get Google Translate TTS URL."""
        import urllib.parse
        return f"https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl={lang}&q={urllib.parse.quote(text)}"

    def cleanup(self):
        """Clean up resources."""
        if self.server:
            self.server.stop()
            self.server.cleanup()


# Singleton instance
_tts_engine = None


def get_tts_engine() -> TTSEngine:
    """Get the singleton TTS engine instance."""
    global _tts_engine
    if _tts_engine is None:
        _tts_engine = TTSEngine()
    return _tts_engine
