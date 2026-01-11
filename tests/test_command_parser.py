"""
Unit tests for command_parser.py
"""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from command_parser import MusicCommandParser


class TestMusicCommandParser:
    """Tests for MusicCommandParser class."""

    @pytest.fixture
    def parser(self):
        """Create parser instance for tests."""
        return MusicCommandParser()

    # Playback control tests
    class TestPlaybackControls:
        """Tests for playback control commands."""

        @pytest.fixture
        def parser(self):
            return MusicCommandParser()

        @pytest.mark.parametrize("command", [
            "para", "stop", "detén", "detente", "parar"
        ])
        def test_stop_commands(self, parser, command):
            result = parser.parse(command)
            assert result is not None
            assert result['action'] == 'stop'
            assert result['query'] is None

        @pytest.mark.parametrize("command", [
            "pausa", "pausar"
        ])
        def test_pause_commands(self, parser, command):
            result = parser.parse(command)
            assert result is not None
            assert result['action'] == 'pause'
            assert result['query'] is None

        @pytest.mark.parametrize("command", [
            "continúa", "continua", "sigue", "reanudar", "play"
        ])
        def test_resume_commands(self, parser, command):
            result = parser.parse(command)
            assert result is not None
            assert result['action'] == 'resume'
            assert result['query'] is None

        @pytest.mark.parametrize("command", [
            "siguiente", "salta", "saltar", "skip", "próxima", "proxima"
        ])
        def test_skip_commands(self, parser, command):
            result = parser.parse(command)
            assert result is not None
            assert result['action'] == 'skip'
            assert result['query'] is None

    # Song playback tests
    class TestSongCommands:
        """Tests for song playback commands."""

        @pytest.fixture
        def parser(self):
            return MusicCommandParser()

        def test_reproduce_song(self, parser):
            result = parser.parse("reproduce bohemian rhapsody")
            assert result is not None
            assert result['action'] == 'play_song'
            assert 'bohemian rhapsody' in result['query'].lower()

        def test_pon_song(self, parser):
            result = parser.parse("pon la canción todo de ti")
            assert result is not None
            assert result['action'] == 'play_song'
            assert 'todo de ti' in result['query'].lower()

        def test_song_with_artist(self, parser):
            result = parser.parse("reproduce heroes del silencio")
            assert result is not None
            assert result['action'] == 'play_song'

    # Artist playback tests
    class TestArtistCommands:
        """Tests for artist playback commands."""

        @pytest.fixture
        def parser(self):
            return MusicCommandParser()

        def test_musica_de_artist(self, parser):
            result = parser.parse("reproduce música de queen")
            assert result is not None
            assert result['action'] == 'play_artist'
            assert 'queen' in result['query'].lower()

        def test_canciones_de_artist(self, parser):
            result = parser.parse("pon canciones de metallica")
            assert result is not None
            assert result['action'] == 'play_artist'
            assert 'metallica' in result['query'].lower()

        def test_algo_de_artist(self, parser):
            result = parser.parse("reproduce algo de rosalía")
            assert result is not None
            assert result['action'] == 'play_artist'
            assert 'rosalía' in result['query'].lower()

    # Album playback tests
    class TestAlbumCommands:
        """Tests for album playback commands."""

        @pytest.fixture
        def parser(self):
            return MusicCommandParser()

        def test_album_command(self, parser):
            result = parser.parse("reproduce el álbum a night at the opera")
            assert result is not None
            assert result['action'] == 'play_album'
            assert 'night at the opera' in result['query'].lower()

        def test_disco_command(self, parser):
            result = parser.parse("pon el disco el madrileño")
            assert result is not None
            assert result['action'] == 'play_album'
            assert 'madrileño' in result['query'].lower()

    # Playlist playback tests
    class TestPlaylistCommands:
        """Tests for playlist playback commands."""

        @pytest.fixture
        def parser(self):
            return MusicCommandParser()

        def test_playlist_command(self, parser):
            result = parser.parse("reproduce la playlist rock clásico")
            assert result is not None
            assert result['action'] == 'play_playlist'
            assert 'rock clásico' in result['query'].lower()

        def test_lista_command(self, parser):
            result = parser.parse("pon la lista mis favoritos")
            assert result is not None
            assert result['action'] == 'play_playlist'
            assert 'favoritos' in result['query'].lower()

    # Search type mapping tests
    class TestSearchTypeMapping:
        """Tests for get_search_type method."""

        @pytest.fixture
        def parser(self):
            return MusicCommandParser()

        def test_song_search_type(self, parser):
            assert parser.get_search_type('play_song') == 'track'

        def test_artist_search_type(self, parser):
            assert parser.get_search_type('play_artist') == 'artist'

        def test_album_search_type(self, parser):
            assert parser.get_search_type('play_album') == 'album'

        def test_playlist_search_type(self, parser):
            assert parser.get_search_type('play_playlist') == 'playlist'

        def test_unknown_defaults_to_track(self, parser):
            assert parser.get_search_type('unknown') == 'track'

    # Edge cases
    class TestEdgeCases:
        """Tests for edge cases and error handling."""

        @pytest.fixture
        def parser(self):
            return MusicCommandParser()

        def test_empty_string(self, parser):
            assert parser.parse("") is None

        def test_none_input(self, parser):
            assert parser.parse(None) is None

        def test_whitespace_only(self, parser):
            assert parser.parse("   ") is None

        def test_unrecognized_command(self, parser):
            result = parser.parse("hola como estas")
            # Should not match any pattern
            assert result is None or result['query'] is not None

        def test_case_insensitive(self, parser):
            result = parser.parse("REPRODUCE MÚSICA DE QUEEN")
            assert result is not None
            assert result['action'] == 'play_artist'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
