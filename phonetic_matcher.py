"""
Phonetic matching for fuzzy search of music titles.
"""

from g2p_en import G2p
from fuzzywuzzy import fuzz
import nltk
from config import setup_logging

logger = setup_logging(__name__)

class PhoneticMatcher:
    """
    Finds the best match for a spoken query from a list of candidates
    using phonetic similarity.
    """

    def __init__(self):
        """Initialize the phonetic converter and ensure NLTK resources are available."""
        self._ensure_nltk_resources()
        try:
            self.g2p = G2p()
            logger.info("Phonetic converter (g2p-en) initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize g2p-en: {e}")
            logger.error("Please make sure you have run: pip install -r requirements.txt")
            self.g2p = None

    def _ensure_nltk_resources(self):
        """
        Check if required NLTK resources are downloaded, and if not, download them.
        """
        try:
            # Check if the resource is available
            nltk.data.find('taggers/averaged_perceptron_tagger_eng.zip')
            logger.debug("NLTK resource 'averaged_perceptron_tagger_eng' found.")
        except LookupError:
            # If not, download it
            logger.warning("NLTK resource 'averaged_perceptron_tagger_eng' not found.")
            print("Downloading required NLTK model for phonetics...")
            try:
                nltk.download('averaged_perceptron_tagger', quiet=True)
                print("...download complete.")
                logger.info("NLTK resource downloaded successfully.")
            except Exception as e:
                logger.error(f"Failed to download NLTK resource: {e}")
                print("\nERROR: Failed to download NLTK resource.")
                print("Please check your internet connection and try again.")
                print("You can also try downloading it manually in a Python shell:")
                print(">>> import nltk")
                print(">>> nltk.download('averaged_perceptron_tagger')")


    def _get_phonemes(self, text):
        """
        Convert text to its phonetic representation.
        
        Args:
            text (str): The input text.

        Returns:
            str: A string of phonemes.
        """
        if not self.g2p:
            return ""
        
        # g2p can fail on strange characters, so wrap in a try-except block
        try:
            # The phonetic representation is a list of phonemes. Join them into a single string.
            phonemes = self.g2p(text)
            return "".join(phonemes)
        except Exception as e:
            logger.warning(f"Could not convert '{text}' to phonemes: {e}")
            return ""

    def find_best_match(self, query_text, candidates):
        """Find the best match for a query text from a list of candidate strings.

        Args:
            query_text (str): The (potentially mis-transcribed) text from speech recognition.
            candidates (list of str): A list of candidate strings from the search API.

        Returns:
            str: The best matching candidate string, or None if no suitable match is found.
        """
        if not self.g2p:
            logger.error("Phonetic converter not available. Cannot find best match.")
            # Fallback to the first candidate if phonetics are not available
            return candidates[0] if candidates else None

        if not candidates:
            return None

        logger.info(f"Finding best phonetic match for '{query_text}' among {len(candidates)} candidates.")

        query_phonemes = self._get_phonemes(query_text)
        if not query_phonemes:
            logger.warning("Could not generate phonemes for query text. Aborting phonetic match.")
            return candidates[0]  # Fallback to first result

        best_match = None
        highest_score = 0

        logger.debug(f"Query phonemes ('{query_text}'): {query_phonemes}")

        for candidate in candidates:
            candidate_phonemes = self._get_phonemes(candidate)
            if not candidate_phonemes:
                continue

            score = fuzz.ratio(query_phonemes, candidate_phonemes)
            logger.debug(f"  - Candidate: '{candidate}'")
            logger.debug(f"    Phonemes: {candidate_phonemes}")
            logger.debug(f"    Score: {score}")

            if score > highest_score:
                highest_score = score
                best_match = candidate
        
        # We can set a minimum threshold score to avoid bad matches
        MIN_SCORE_THRESHOLD = 30  # Adjust as needed
        if highest_score < MIN_SCORE_THRESHOLD:
            logger.warning(f"No good phonetic match found. Highest score ({highest_score}) is below threshold ({MIN_SCORE_THRESHOLD}).")
            logger.warning(f"Falling back to the first result from search: '{candidates[0]}'")
            return candidates[0]

        logger.info(f"Best phonetic match: '{best_match}' (Score: {highest_score})")
        return best_match

if __name__ == '__main__':
    """Test the phonetic matcher."""
    print("=" * 60)
    print("Phonetic Matcher Test")
    print("=" * 60)
    
    matcher = PhoneticMatcher()

    # Example 1: The original problem - "Bowie"
    spoken_query = "boui"
    tidal_candidates = ["David Bowie", "Bayside", "Boyce Avenue", "The Bows"]
    
    print(f"\nSpoken query: '{spoken_query}'")
    print(f"Candidates: {tidal_candidates}")
    best = matcher.find_best_match(spoken_query, tidal_candidates)
    print(f"--> Best match: '{best}'")
    assert best == "David Bowie"
    print("✅ Test passed!")

    # Example 2: Spanish pronunciation of English song
    spoken_query = "blaind in laits"
    tidal_candidates = ["Blinding Lights", "Blinded In Chains", "Blinded by the Light"]

    print(f"\nSpoken query: '{spoken_query}'")
    print(f"Candidates: {tidal_candidates}")
    best = matcher.find_best_match(spoken_query, tidal_candidates)
    print(f"--> Best match: '{best}'")
    assert best == "Blinding Lights"
    print("✅ Test passed!")

    # Example 3: A more complex case
    spoken_query = "smels laik tin spirit"
    tidal_candidates = ["Smells Like Teen Spirit", "American Spirit", "Spirit in the Sky"]
    
    print(f"\nSpoken query: '{spoken_query}'")
    print(f"Candidates: {tidal_candidates}")
    best = matcher.find_best_match(spoken_query, tidal_candidates)
    print(f"--> Best match: '{best}'")
    assert best == "Smells Like Teen Spirit"
    print("✅ Test passed!")
