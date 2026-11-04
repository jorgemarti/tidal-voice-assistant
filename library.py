"""
The household's music library: Tidal favourites (tracks, albums, artists, playlists), the user's own
playlists and the most listened tracks and artists of the last month according to Last.fm.

Most requests are for something already in here, so `TidalPlayer.smart_search_and_play` matches the
spoken query against the library first (fuzzy, zero tokens) and only then searches the Tidal
catalogue. The library is also sent to Gemini as a closed set of labels: the model may answer
`library_match` with one of them copied literally, and `lookup` only accepts labels that exist.

Refreshed every LIBRARY_REFRESH_HOURS in a daemon thread and cached in LIBRARY_FILE so a restart
does not wait for Tidal.
"""

import json
import os
import threading
import time
import unicodedata
from typing import Optional

from fuzzywuzzy import fuzz

from config import (LIBRARY_FILE, LIBRARY_REFRESH_HOURS, LIBRARY_HINT_TRACKS, LIBRARY_HINT_ALBUMS,
                    LIBRARY_HINT_ARTISTS, LASTFM_TOP_TRACKS, LASTFM_TOP_ARTISTS, setup_logging)

logger = setup_logging(__name__)

KINDS = ("track", "album", "artist", "playlist")
PAGE = 50
MAX_FAVOURITES = 500  # per kind, enough for this household and bounded for the prompt


def norm(text: str) -> str:
    """Lower-case, accent-stripped, punctuation replaced by spaces."""
    text = unicodedata.normalize('NFKD', text or '')
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return ' '.join(''.join(c if c.isalnum() or c.isspace() else ' ' for c in text.lower()).split())


def label_of(entry: dict) -> str:
    """The text an entry is shown as to Gemini, and the only form `lookup` accepts back."""
    if entry["kind"] in ("track", "album") and entry.get("artist"):
        return f"{entry['name']} ({entry['artist']})"
    return entry["name"]


class Library:
    def __init__(self, session=None, lastfm_network=None, path: str = LIBRARY_FILE):
        self.session = session
        self.lastfm = lastfm_network
        self.path = path
        self.entries: list = []  # {'kind','name','artist','id','source','plays'}
        self.refreshed_at: float = 0.0
        self._lock = threading.Lock()
        self._by_label: dict = {}

    # ---------------------------------------------------------------- loading

    def start(self):
        """Load the cache; refresh now if there is none, otherwise in the background when stale."""
        if not self.load():
            self.refresh()
        threading.Thread(target=self._loop, daemon=True, name="library-refresh").start()

    def _loop(self):
        while True:
            due = self.refreshed_at + LIBRARY_REFRESH_HOURS * 3600 - time.time()
            time.sleep(max(60, due))
            if time.time() >= self.refreshed_at + LIBRARY_REFRESH_HOURS * 3600:
                self.refresh()

    def load(self) -> bool:
        try:
            with open(self.path) as f:
                data = json.load(f)
            self._set(data.get("entries") or [], data.get("refreshed_at") or 0.0)
            logger.info(f"Library loaded from {self.path}: {self.summary()}")
            return bool(self.entries)
        except (OSError, ValueError):
            return False

    def save(self):
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w") as f:
                json.dump({"refreshed_at": self.refreshed_at, "entries": self.entries}, f, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError as e:
            logger.warning(f"Could not save library: {e}")

    def _set(self, entries: list, refreshed_at: float):
        with self._lock:
            self.entries = entries
            self.refreshed_at = refreshed_at
            self._by_label = {norm(label_of(e)): e for e in entries}

    def summary(self) -> str:
        counts = {k: sum(1 for e in self.entries if e["kind"] == k) for k in KINDS}
        return ", ".join(f"{v} {k}s" for k, v in counts.items())

    # --------------------------------------------------------------- refresh

    def refresh(self):
        """Fetch everything again. Failures of one source keep the others."""
        t0 = time.time()
        entries = []
        if self.session:
            entries += self._tidal_entries()
        if self.lastfm:
            entries += self._lastfm_entries()
        if not entries:
            logger.warning("Library refresh produced nothing, keeping the previous one")
            return
        entries = self._dedupe(entries)
        self._set(entries, time.time())
        self.save()
        logger.info(f"Library refreshed in {time.time() - t0:.0f}s: {self.summary()}")

    def _paged(self, getter):
        # Tidal drops unavailable items from each page, so a short page is not the last one:
        # only an empty page is.
        items, offset = [], 0
        while offset < MAX_FAVOURITES:
            page = getter(limit=PAGE, offset=offset) or []
            if not page:
                break
            items += page
            offset += PAGE
        return items

    def _tidal_entries(self) -> list:
        out = []
        fav = self.session.user.favorites
        sources = [
            ("track", lambda: self._paged(fav.tracks), lambda t: {"name": t.name, "artist": getattr(getattr(t, "artist", None), "name", None), "id": t.id}),
            ("album", lambda: self._paged(fav.albums), lambda a: {"name": a.name, "artist": getattr(getattr(a, "artist", None), "name", None), "id": a.id}),
            ("artist", lambda: self._paged(fav.artists), lambda a: {"name": a.name, "artist": None, "id": a.id}),
            ("playlist", lambda: self._paged(fav.playlists), lambda p: {"name": p.name, "artist": None, "id": p.id}),
            ("playlist", lambda: self.session.user.playlists(), lambda p: {"name": p.name, "artist": None, "id": p.id}),
        ]
        for kind, getter, to_entry in sources:
            try:
                for item in getter():
                    e = to_entry(item)
                    if e["name"]:
                        out.append(dict(e, kind=kind, source="tidal"))
            except Exception as e:
                logger.warning(f"Could not read Tidal favourite {kind}s: {e}")
        return out

    def _lastfm_entries(self) -> list:
        out = []
        try:
            import pylast
            user = self.lastfm.get_authenticated_user()
            for top in user.get_top_tracks(period=pylast.PERIOD_1MONTH, limit=LASTFM_TOP_TRACKS):
                track = top.item
                artist = getattr(getattr(track, "artist", None), "name", None)
                if track.title:
                    out.append({"kind": "track", "name": track.title, "artist": artist, "id": None, "source": "lastfm", "plays": int(top.weight or 0)})
            for top in user.get_top_artists(period=pylast.PERIOD_1MONTH, limit=LASTFM_TOP_ARTISTS):
                if top.item.name:
                    out.append({"kind": "artist", "name": top.item.name, "artist": None, "id": None, "source": "lastfm", "plays": int(top.weight or 0)})
        except Exception as e:
            logger.warning(f"Could not read Last.fm top tracks: {e}")
        return out

    @staticmethod
    def _dedupe(entries: list) -> list:
        """One entry per label; a Tidal id wins over a Last.fm entry, play counts are kept."""
        merged = {}
        for e in entries:
            key = (e["kind"], norm(label_of(e)))
            cur = merged.get(key)
            if cur is None:
                merged[key] = dict(e)
            else:
                if not cur.get("id") and e.get("id"):
                    cur["id"], cur["source"] = e["id"], e["source"]
                cur["plays"] = max(cur.get("plays", 0), e.get("plays", 0))
        return list(merged.values())

    # -------------------------------------------------------------- matching

    def match(self, query: str, kind: str, artist: Optional[str] = None):
        """Best entry of `kind` for the spoken query: (entry, score 0..100) or (None, -1)."""
        best, best_score = None, -1
        q = norm(query)
        if not q:
            return best, best_score
        with self._lock:
            candidates = [e for e in self.entries if e["kind"] == kind]
        for e in candidates:
            score = fuzz.token_set_ratio(q, norm(e["name"]))
            if artist and kind in ("track", "album"):
                score = 0.6 * score + 0.4 * fuzz.token_set_ratio(norm(artist), norm(e.get("artist") or ""))
            if score > best_score:
                best, best_score = e, score
        return best, best_score

    def lookup(self, label: Optional[str]) -> Optional[dict]:
        """The entry whose label Gemini copied back, or None: labels not in the library are refused."""
        if not label:
            return None
        with self._lock:
            return self._by_label.get(norm(label))

    def artist_names(self) -> list:
        with self._lock:
            names = [e["name"] for e in self.entries if e["kind"] == "artist"]
            names += [e["artist"] for e in self.entries if e["kind"] == "track" and e.get("artist")]
        return list(dict.fromkeys(n for n in names if n))

    def hint_text(self) -> str:
        """Compact closed set of labels for the Gemini prompt (most played first, bounded per kind)."""
        with self._lock:
            entries = list(self.entries)
        if not entries:
            return ""
        by_plays = lambda e: -e.get("plays", 0)
        parts = []
        for kind, title, cap in (("playlist", "Playlists", None), ("track", "Canciones", LIBRARY_HINT_TRACKS),
                                 ("album", "Álbumes", LIBRARY_HINT_ALBUMS), ("artist", "Artistas", LIBRARY_HINT_ARTISTS)):
            items = sorted((e for e in entries if e["kind"] == kind), key=by_plays)
            if cap:
                items = items[:cap]
            if items:
                parts.append(f"{title}: " + "; ".join(label_of(e) for e in items))
        return "\n".join(parts)
