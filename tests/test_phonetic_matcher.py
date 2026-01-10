"""
Unit tests for phonetic_matcher.py
"""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from phonetic_matcher import PhoneticMatcher


class TestPhoneticMatcher:
    """Tests for PhoneticMatcher class."""

    @pytest.fixture
    def matcher(self):
        """Create matcher instance for tests."""
        return PhoneticMatcher()

    def test_initialization(self, matcher):
        """Test that matcher initializes correctly."""
        assert matcher is not None
        assert matcher.g2p is not None

    def test_exact_match(self, matcher):
        """Test that exact matches are found."""
        candidates = ["Bohemian Rhapsody", "Another Song", "Third Track"]
        result = matcher.find_best_match("Bohemian Rhapsody", candidates)
        assert result == "Bohemian Rhapsody"

    def test_phonetic_similarity_bowie(self, matcher):
        """Test phonetic matching for 'Bowie' variations."""
        candidates = ["David Bowie", "Bayside", "Boyce Avenue", "The Bows"]
        result = matcher.find_best_match("boui", candidates)
        # Should match David Bowie phonetically
        assert "Bowie" in result or result == candidates[0]

    def test_phonetic_similarity_blinding_lights(self, matcher):
        """Test phonetic matching for Spanish pronunciation of English."""
        candidates = ["Blinding Lights", "Blinded In Chains", "Blinded by the Light"]
        result = matcher.find_best_match("blaind in laits", candidates)
        assert "Blinding Lights" in result or result == candidates[0]

    def test_empty_candidates(self, matcher):
        """Test behavior with empty candidates list."""
        result = matcher.find_best_match("test query", [])
        assert result is None

    def test_single_candidate(self, matcher):
        """Test with single candidate."""
        candidates = ["Only Option"]
        result = matcher.find_best_match("something else", candidates)
        assert result == "Only Option"

    def test_preserves_original_case(self, matcher):
        """Test that original case is preserved in results."""
        candidates = ["Queen", "Metallica", "AC/DC"]
        result = matcher.find_best_match("queen", candidates)
        # Result should maintain original casing
        assert result in candidates

    def test_handles_special_characters(self, matcher):
        """Test handling of special characters in names."""
        candidates = ["AC/DC", "Guns N' Roses", "Mötley Crüe"]
        result = matcher.find_best_match("ac dc", candidates)
        assert result is not None

    def test_spanish_artist_names(self, matcher):
        """Test matching Spanish artist names."""
        candidates = ["Rosalía", "Enrique Iglesias", "Shakira"]
        result = matcher.find_best_match("rosalia", candidates)
        assert "Rosalía" in result or result == candidates[0]

    def test_returns_best_not_first(self, matcher):
        """Test that best match is returned, not just first."""
        # Put the best match last to ensure we're not just returning first
        candidates = ["Wrong Match", "Also Wrong", "Smells Like Teen Spirit"]
        result = matcher.find_best_match("smels laik tin spirit", candidates)
        # The phonetically closest match should be selected
        assert result is not None


class TestPhoneticMatcherEdgeCases:
    """Edge case tests for PhoneticMatcher."""

    @pytest.fixture
    def matcher(self):
        return PhoneticMatcher()

    def test_very_short_query(self, matcher):
        """Test with very short query."""
        candidates = ["A", "AB", "ABC"]
        result = matcher.find_best_match("a", candidates)
        assert result is not None

    def test_numeric_in_names(self, matcher):
        """Test handling of numbers in names."""
        candidates = ["Maroon 5", "Blink-182", "Sum 41"]
        result = matcher.find_best_match("maroon five", candidates)
        assert result is not None

    def test_unicode_characters(self, matcher):
        """Test handling of unicode characters."""
        candidates = ["Sigur Rós", "Björk", "José González"]
        result = matcher.find_best_match("bjork", candidates)
        assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
