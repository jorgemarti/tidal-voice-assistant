"""
Parse Spanish voice commands for music playback
"""

import re

class MusicCommandParser:
    """
    Parse Spanish voice commands into structured music actions.
    
    Supported patterns:
    Playback controls:
    - "para" / "stop" → stop playback
    - "pausa" → pause playback
    - "continúa" / "sigue" → resume playback

    Music commands:
    - "reproduce [canción]" → play song
    - "pon [canción]" → play song
    - "reproduce música de [artista]" → play artist
    - "pon canciones de [artista]" → play artist
    - "reproduce el álbum [nombre]" → play album
    """
    
    def __init__(self):
        # Patterns for different command types
        # These are ordered by specificity (most specific first)
        self.patterns = {
            # Playback controls (check first - no query needed)
            'stop': [
                r'^(para|detén|detente|stop|parar)$',
            ],
            'pause': [
                r'^(pausa|pausar)$',
            ],
            'resume': [
                r'^(continúa|continua|sigue|reanudar|play)$',
            ],
            'skip': [
                r'^(siguiente|salta|saltar|skip|próxima|proxima)$',
                r'pasa (?:la )?canción',
            ],
            # Music search commands
            'play_playlist': [
                r'(?:reproduce|reproducir) (?:la )?(?:playlist|lista) (.+)',
                r'pon (?:la )?(?:playlist|lista) (.+)',
            ],
            'play_album': [
                r'(?:reproduce|reproducir) (?:el )?álbum (?:de )?(.+)',
                r'pon (?:el )?álbum (?:de )?(.+)',
                r'(?:reproduce|reproducir) (?:el )?disco (?:de )?(.+)',
                r'pon (?:el )?disco (?:de )?(.+)',
            ],
            'play_artist': [
                r'(?:reproduce|reproducir) (?:música|canciones) de (.+)',
                r'pon (?:música|canciones) de (.+)',
                r'(?:reproduce|reproducir) algo de (.+)',
                r'pon algo de (.+)',
                r'(?:reproduce|reproducir) (.+)(?:el artista|la banda)',
            ],
            'play_song': [
                r'(?:reproduce|reproducir) (?:la canción )?(.+?)(?:\s+de\s+|$)',
                r'pon (?:la canción )?(.+?)(?:\s+de\s+|$)',
                r'(?:reproduce|reproducir) (.+)',
                r'pon (.+)',
            ],
        }
    
    def parse(self, text):
        """
        Parse voice command text into structured action.

        Args:
            text: Recognized speech text in Spanish

        Returns:
            dict with 'action' and 'query' keys, or None if no match
            {
                'action': 'play_song' | 'play_artist' | 'play_album',
                'query': 'extracted search term'
            }
        """
        if not text:
            return None

        text = text.lower().strip()

        # Fix common misrecognitions of "reproduce/reproducir"
        misrecognitions = [
            'reconocido', 'reconoce', 'reproduce el', 'reproductor',
            'reproducido', 'reproduciendo', 'reproducir el'
        ]
        for mis in misrecognitions:
            if text.startswith(mis):
                text = 'reproduce' + text[len(mis):]
                break
        
        # Try each pattern type in order
        for action, patterns in self.patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    # Control commands don't have a query (group 1)
                    if action in ['stop', 'pause', 'resume', 'skip']:
                        return {
                            'action': action,
                            'query': None,
                            'original_text': text
                        }

                    # Music commands have a query
                    query = match.group(1).strip()

                    # Clean up common artifacts
                    query = self._clean_query(query)

                    if query:  # Only return if we extracted something
                        return {
                            'action': action,
                            'query': query,
                            'original_text': text
                        }

        return None
    
    def _clean_query(self, query):
        """Clean up extracted query string"""
        # Remove trailing articles and prepositions
        query = re.sub(r'\s+(de|por|del|la|el|los|las)$', '', query, flags=re.IGNORECASE)
        
        # Remove double spaces
        query = re.sub(r'\s+', ' ', query)
        
        return query.strip()
    
    def get_search_type(self, action):
        """
        Convert action to Tidal search type.
        
        Returns:
            'track', 'artist', or 'album'
        """
        mapping = {
            'play_song': 'track',
            'play_artist': 'artist',
            'play_album': 'album',
            'play_playlist': 'playlist'
        }
        return mapping.get(action, 'track')

if __name__ == "__main__":
    """Test command parser with Spanish examples"""
    print("=" * 60)
    print("Spanish Command Parser Test")
    print("=" * 60)
    print()
    
    parser = MusicCommandParser()
    
    # Test cases
    test_commands = [
        # Song commands
        "reproduce bohemian rhapsody",
        "pon la canción todo de ti",
        "reproduce heroes del silencio de bunbury",
        "pon something",
        
        # Artist commands
        "reproduce música de queen",
        "pon canciones de metallica",
        "reproduce algo de rosalía",
        "pon música de bad bunny",
        
        # Album commands
        "reproduce el álbum a night at the opera",
        "pon el disco el madrileño",
        "reproduce el álbum de un verano sin ti",
        "pon el disco master of puppets",
    ]
    
    for i, command in enumerate(test_commands, 1):
        print(f"{i}. Input: '{command}'")
        result = parser.parse(command)
        
        if result:
            print(f"   ✅ Action: {result['action']}")
            print(f"   ✅ Query: '{result['query']}'")
            print(f"   ✅ Search type: {parser.get_search_type(result['action'])}")
        else:
            print(f"   ❌ No match found")
        
        print()
    
    # Interactive test
    print("=" * 60)
    print("Interactive Test")
    print("=" * 60)
    print("Enter Spanish music commands (or 'quit' to exit):")
    print()
    
    while True:
        try:
            command = input("Command: ").strip()
            if command.lower() in ['quit', 'exit', 'salir']:
                break
            
            if not command:
                continue
            
            result = parser.parse(command)
            if result:
                print(f"  Action: {result['action']}")
                print(f"  Query: '{result['query']}'")
                print(f"  Search: {parser.get_search_type(result['action'])}")
            else:
                print("  ❌ Could not parse command")
            print()
            
        except KeyboardInterrupt:
            print("\n")
            break
