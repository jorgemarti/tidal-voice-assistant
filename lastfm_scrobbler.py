"""
Last.fm scrobbling for tracks played on the Chromecast.

Tidal reports nothing about what the Pi plays, so the assistant scrobbles it itself, following the
Last.fm rules: a track counts once it has played half its length or four minutes, and only if it
is longer than 30 seconds. "Now playing" is sent as soon as a track starts.

Needs LASTFM_API_KEY and LASTFM_API_SECRET in .env and a session key in LASTFM_SESSION_FILE,
obtained once with `python lastfm_auth.py`.
"""

import json
import os
import threading
import time
from typing import Callable, Optional

from config import LASTFM_SCROBBLE, LASTFM_SESSION_FILE, setup_logging

logger = setup_logging(__name__)

MIN_TRACK_SECONDS = 30
SCROBBLE_CAP_SECONDS = 240


def load_session_key(path: str = LASTFM_SESSION_FILE) -> Optional[str]:
    try:
        with open(path) as f:
            return json.load(f).get("session_key")
    except (OSError, ValueError):
        return None


def should_scrobble(duration: Optional[int], played: float) -> bool:
    """Last.fm rule: longer than 30 s, and played half of it or 4 minutes, whichever comes first."""
    if not duration or duration <= MIN_TRACK_SECONDS:
        return False
    return played >= min(duration / 2, SCROBBLE_CAP_SECONDS)


class LastFmScrobbler:
    def __init__(self, network=None):
        """network: a pylast.LastFMNetwork, or None to build one from .env and the session file."""
        self.network = network
        self._current = None  # {'title','artist','album','duration','started','first_time','last_time'}
        self._last_scrobbled = None  # (title, artist, timestamp) guard against double scrobbles
        self._lock = threading.Lock()
        if network is None and LASTFM_SCROBBLE:
            self.network = self._connect()

    @staticmethod
    def _connect():
        key, secret = os.environ.get("LASTFM_API_KEY"), os.environ.get("LASTFM_API_SECRET")
        if not key or not secret:
            logger.info("Last.fm scrobbling off: LASTFM_API_KEY/LASTFM_API_SECRET not set")
            return None
        session_key = load_session_key()
        if not session_key:
            logger.warning("Last.fm scrobbling off: no session key, run `python lastfm_auth.py` once")
            return None
        try:
            import pylast
            network = pylast.LastFMNetwork(api_key=key, api_secret=secret, session_key=session_key)
            logger.info("Last.fm scrobbling ready")
            return network
        except Exception as e:
            logger.error(f"Could not init Last.fm: {e}")
            return None

    @property
    def enabled(self) -> bool:
        return self.network is not None

    def _bg(self, fn: Callable, *args):
        threading.Thread(target=self._safe, args=(fn,) + args, daemon=True).start()

    @staticmethod
    def _safe(fn, *args):
        try:
            fn(*args)
        except Exception as e:
            logger.warning(f"Last.fm call failed: {e}")

    def track_started(self, title: str, artist: str, album: Optional[str], duration: Optional[int], position: float = 0.0):
        """A track started (or resumed) on the speaker. Flushes the previous one first."""
        if not self.enabled:
            return
        self.track_ended()
        with self._lock:
            self._current = {"title": title, "artist": artist, "album": album, "duration": duration,
                             "started": int(time.time()), "first_time": position, "last_time": position}
        logger.debug(f"Last.fm now playing: {title} by {artist}")
        self._bg(lambda: self.network.update_now_playing(artist=artist, title=title, album=album, duration=duration))

    def track_progress(self, current_time: Optional[float]):
        if current_time is None:
            return
        with self._lock:
            if self._current:
                if self._current["duration"]:
                    current_time = min(current_time, self._current["duration"])
                if current_time > self._current["last_time"]:
                    self._current["last_time"] = current_time

    def track_ended(self):
        """The current track stopped, was skipped or finished: scrobble it if it played enough."""
        with self._lock:
            cur, self._current = self._current, None
        if not cur or not self.enabled:
            return
        played = cur["last_time"] - cur["first_time"]
        if not should_scrobble(cur["duration"], played):
            logger.debug(f"Not scrobbling {cur['title']}: played {played:.0f}s of {cur['duration']}s")
            return
        key = (cur["title"], cur["artist"])
        if self._last_scrobbled and self._last_scrobbled[:2] == key and cur["started"] - self._last_scrobbled[2] < (cur["duration"] or 0):
            logger.debug(f"Already scrobbled {cur['title']} for this play")
            return
        self._last_scrobbled = key + (cur["started"],)
        logger.info(f"Scrobbling: {cur['title']} by {cur['artist']} ({played:.0f}s)")
        self._bg(lambda: self.network.scrobble(artist=cur["artist"], title=cur["title"], timestamp=cur["started"], album=cur["album"], duration=cur["duration"]))


class ScrobbleListener:
    """pychromecast media status listener that feeds the scrobbler from what the speaker reports.

    resolve(title, artist) returns {'title','artist','album','duration'} for a title the player queued,
    or None for other media (TTS, cues), which are ignored.

    The Chromecast reports its status only on changes, not periodically, so a track that plays through
    uninterrupted reports a position of 0 until it ends. The position reached is therefore extrapolated
    from the previous status and the wall clock whenever a new status arrives.
    """

    def __init__(self, scrobbler: LastFmScrobbler, resolve: Callable[[str, Optional[str]], Optional[dict]], clock: Callable[[], float] = time.monotonic):
        self.scrobbler = scrobbler
        self.resolve = resolve
        self.clock = clock
        self._content_id = None
        self._last = None  # (current_time, clock reading, was playing) of the previous status

    def new_media_status(self, status):
        try:
            state = getattr(status, "player_state", None)
            content_id = getattr(status, "content_id", None)
            now = self.clock()
            if self._last and self._last[2]:
                # Position the previous status reached while playing, before this change is applied
                self.scrobbler.track_progress(self._last[0] + (now - self._last[1]))
            current = getattr(status, "current_time", None)
            self._last = (current, now, state == "PLAYING") if current is not None else None
            if state in ("PLAYING", "BUFFERING") and content_id and content_id != self._content_id:
                self._content_id = content_id
                title, artist = getattr(status, "title", None), getattr(status, "artist", None)
                info = self.resolve(title, artist)
                if not info and title and artist:
                    # Not in this process's queue (e.g. queued before a restart): trust the speaker's metadata
                    duration = getattr(status, "duration", None)
                    info = {"title": title, "artist": artist, "album": getattr(status, "album_name", None),
                            "duration": int(duration) if duration else None}
                if info:
                    self.scrobbler.track_started(position=getattr(status, "current_time", 0) or 0, **info)
                else:
                    self.scrobbler.track_ended()
            elif state == "IDLE":
                self._content_id = None
                self.scrobbler.track_ended()
            if state == "PLAYING":
                self.scrobbler.track_progress(getattr(status, "current_time", None))
        except Exception as e:
            logger.debug(f"Scrobble listener error: {e}")

    def load_queue_changed(self, queue_items):
        pass
