from types import SimpleNamespace

from lastfm_scrobbler import LastFmScrobbler, ScrobbleListener, should_scrobble


class FakeNetwork:
    def __init__(self):
        self.now_playing = []
        self.scrobbles = []

    def update_now_playing(self, artist, title, album=None, duration=None):
        self.now_playing.append((artist, title))

    def scrobble(self, artist, title, timestamp, album=None, duration=None):
        self.scrobbles.append((artist, title))


def wait_threads():
    import threading
    for t in threading.enumerate():
        if t is not threading.current_thread():
            t.join(timeout=2)


def test_should_scrobble_rules():
    assert not should_scrobble(None, 100)
    assert not should_scrobble(25, 25)
    assert not should_scrobble(200, 90)
    assert should_scrobble(200, 100)
    assert should_scrobble(900, 240)
    assert not should_scrobble(900, 239)


def test_scrobbles_once_played_enough():
    net = FakeNetwork()
    s = LastFmScrobbler(network=net)
    s.track_started("Bon dia", "Dàmaris Gelabert", "Bon dia", 180)
    s.track_progress(50)
    s.track_ended()
    s.track_started("Last Nite", "The Strokes", "Is This It", 200)
    s.track_progress(120)
    s.track_ended()
    wait_threads()
    assert net.now_playing == [("Dàmaris Gelabert", "Bon dia"), ("The Strokes", "Last Nite")]
    assert net.scrobbles == [("The Strokes", "Last Nite")]


def test_resume_does_not_double_scrobble():
    net = FakeNetwork()
    s = LastFmScrobbler(network=net)
    s.track_started("Last Nite", "The Strokes", None, 200)
    s.track_progress(130)
    s.track_ended()  # paused for a command
    s.track_started("Last Nite", "The Strokes", None, 200, position=130)
    s.track_progress(199)
    s.track_ended()
    wait_threads()
    assert net.scrobbles == [("The Strokes", "Last Nite")]


def test_listener_ignores_unknown_media_and_tracks_changes():
    net = FakeNetwork()
    s = LastFmScrobbler(network=net)
    known = {"Last Nite": {"title": "Last Nite", "artist": "The Strokes", "album": None, "duration": 200}}
    listener = ScrobbleListener(s, lambda title, artist: known.get(title))
    listener.new_media_status(SimpleNamespace(player_state="PLAYING", content_id="u1", title="Last Nite", artist=None, current_time=0))
    listener.new_media_status(SimpleNamespace(player_state="PLAYING", content_id="u1", title="Last Nite", artist=None, current_time=150))
    listener.new_media_status(SimpleNamespace(player_state="PLAYING", content_id="tts", title="No te he entendido", artist=None, current_time=0))
    listener.new_media_status(SimpleNamespace(player_state="IDLE", content_id=None, title=None, artist=None, current_time=0))
    wait_threads()
    assert net.now_playing == [("The Strokes", "Last Nite")]
    assert net.scrobbles == [("The Strokes", "Last Nite")]
