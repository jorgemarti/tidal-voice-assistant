import json

from library import Library, label_of, norm


def make(tmp_path):
    lib = Library(path=str(tmp_path / "library.json"))
    lib._set([
        {"kind": "track", "name": "En Patufet", "artist": "El Ruc Català", "id": 1, "source": "tidal", "plays": 3},
        {"kind": "track", "name": "Mi Caballo Percherón", "artist": "Canciones Infantiles", "id": None, "source": "lastfm", "plays": 9},
        {"kind": "album", "name": "Is This It", "artist": "The Strokes", "id": 2, "source": "tidal"},
        {"kind": "artist", "name": "Pearl Jam", "artist": None, "id": 3, "source": "tidal"},
        {"kind": "playlist", "name": "Rock clásico", "artist": None, "id": "p1", "source": "tidal"},
    ], 1000.0)
    return lib


def test_norm_and_label():
    assert norm("  Rock Clásico, (2)! ") == "rock clasico 2"
    assert label_of({"kind": "track", "name": "En Patufet", "artist": "El Ruc Català"}) == "En Patufet (El Ruc Català)"
    assert label_of({"kind": "playlist", "name": "Rock clásico"}) == "Rock clásico"


def test_match_by_kind(tmp_path):
    lib = make(tmp_path)
    entry, score = lib.match("patufet", "track")
    assert entry["name"] == "En Patufet" and score >= 80
    entry, score = lib.match("pearl jam", "artist")
    assert entry["name"] == "Pearl Jam" and score == 100
    entry, score = lib.match("la lista rock clasico", "playlist")
    assert entry["name"] == "Rock clásico" and score >= 80
    assert lib.match("bohemian rhapsody", "track")[1] < 80
    assert lib.match("", "track") == (None, -1)


def test_lookup_accepts_only_library_labels(tmp_path):
    lib = make(tmp_path)
    assert lib.lookup("en patufet (el ruc catala)")["id"] == 1
    assert lib.lookup("Rock clásico")["kind"] == "playlist"
    assert lib.lookup("En Patufet (El Pot Petit)") is None
    assert lib.lookup(None) is None


def test_hint_text_and_artist_names(tmp_path):
    lib = make(tmp_path)
    hint = lib.hint_text()
    assert hint.startswith("Playlists: Rock clásico")
    # most played first
    assert hint.index("Mi Caballo Percherón") < hint.index("En Patufet")
    assert "Álbumes: Is This It (The Strokes)" in hint
    assert set(lib.artist_names()) == {"Pearl Jam", "El Ruc Català", "Canciones Infantiles"}


def test_dedupe_prefers_tidal_id_and_keeps_plays():
    merged = Library._dedupe([
        {"kind": "track", "name": "En Patufet", "artist": "El Ruc Català", "id": None, "source": "lastfm", "plays": 7},
        {"kind": "track", "name": "en patufet", "artist": "el ruc català", "id": 1, "source": "tidal"},
    ])
    assert len(merged) == 1 and merged[0]["id"] == 1 and merged[0]["plays"] == 7


def test_save_and_load_roundtrip(tmp_path):
    lib = make(tmp_path)
    lib.save()
    other = Library(path=lib.path)
    assert other.load() and other.refreshed_at == 1000.0 and len(other.entries) == 5
    assert json.load(open(lib.path))["entries"][0]["name"] == "En Patufet"


def test_paged_keeps_going_after_short_pages():
    """Tidal hides unavailable items, so pages come back with 47-49 of 50: only an empty page ends the list."""
    data = list(range(140))
    pages = {0: data[0:48], 50: data[50:97], 100: data[100:140], 150: []}
    got = Library()._paged(lambda limit, offset: pages.get(offset, []))
    assert len(got) == 48 + 47 + 40


def test_paged_stops_when_the_offset_is_ignored():
    """Favourite playlists come back identical whatever the offset: stop instead of looping to the cap."""
    from types import SimpleNamespace
    page = [SimpleNamespace(id=f"p{i}") for i in range(36)]
    calls = []
    got = Library()._paged(lambda limit, offset: calls.append(offset) or page)
    assert len(got) == 36 and calls == [0, 50]
