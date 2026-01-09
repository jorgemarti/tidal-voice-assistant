"""
Tidal authentication module
"""

import tidalapi
import json
import pychromecast
import urllib.parse
from datetime import datetime
from config import TIDAL_CONFIG, CHROMECAST_NAME, setup_logging
from pathlib import Path

logger = setup_logging(__name__)


def announce_auth_needed():
    """Announce on Chromecast that re-authentication is needed."""
    message = "Atención. La sesión de Tidal ha caducado. Por favor, ejecuta la autenticación manualmente."

    try:
        chromecasts, browser = pychromecast.get_listed_chromecasts(
            friendly_names=[CHROMECAST_NAME]
        )
        if not chromecasts:
            logger.warning(f"Chromecast '{CHROMECAST_NAME}' not found for announcement")
            return

        cast = chromecasts[0]
        cast.wait(timeout=10)

        tts_url = f"https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl=es&q={urllib.parse.quote(message)}"
        cast.media_controller.play_media(tts_url, 'audio/mp3')
        cast.media_controller.block_until_active()

        logger.debug("Announced auth needed on Chromecast")
        browser.stop_discovery()
    except Exception as e:
        logger.error(f"Failed to announce: {e}")

def authenticate_tidal():
    """
    Authenticate with Tidal using OAuth simple flow.
    """
    logger.debug("Starting Tidal authentication...")

    # Create session
    session = tidalapi.Session()

    # Use OAuth simple (TV) flow
    try:
        logger.debug("Initiating OAuth authentication...")
        print()
        print("A browser window will open for authorization.")
        print("If it doesn't open automatically, copy and paste the URL shown.")
        print()

        session.login_oauth_simple()

        logger.info("Tidal authentication successful!")
    except Exception as e:
        logger.error(f"Tidal authentication failed: {e}")
        raise

    # Save session for future use
    save_session(session)

    logger.debug(f"Session saved to: {TIDAL_CONFIG['session_file']}")
    return session

def save_session(session):
    """Save Tidal session to file"""
    session_data = {
        'token_type': session.token_type,
        'access_token': session.access_token,
        'refresh_token': session.refresh_token,
        'expiry_time': session.expiry_time.isoformat() if session.expiry_time else None
    }

    with open(TIDAL_CONFIG['session_file'], 'w') as f:
        json.dump(session_data, f, indent=2)

def load_tidal_session():
    """
    Load existing Tidal session from file or create new one.
    """
    session_file = Path(TIDAL_CONFIG['session_file'])

    # Try to load existing session
    if session_file.exists():
        try:
            with open(session_file, 'r') as f:
                data = json.load(f)

            session = tidalapi.Session()

            # Convert expiry_time string back to datetime object
            expiry_time_str = data.get('expiry_time')
            expiry_time = datetime.fromisoformat(expiry_time_str) if expiry_time_str else None

            # Load OAuth session
            session.load_oauth_session(
                data['token_type'],
                data['access_token'],
                data['refresh_token'],
                expiry_time
            )

            # Verify session is still valid (this also refreshes tokens if needed)
            if session.check_login():
                logger.debug("Loaded existing Tidal session")
                # Save refreshed tokens
                save_session(session)
                return session
            else:
                logger.warning("Session expired, re-authentication needed")
                announce_auth_needed()
                return None
        except Exception as e:
            logger.warning(f"Could not load existing session: {e}")
            announce_auth_needed()
            return None

    # No session file exists - need manual auth
    logger.error("No session file found. Run 'python tidal_auth.py' to authenticate.")
    announce_auth_needed()
    return None

if __name__ == "__main__":
    print("=" * 60)
    print("Tidal Authentication Setup")
    print("=" * 60)
    print()
    print("This will use OAuth device flow to authenticate with Tidal.")
    print("You'll need to visit a URL in your browser to authorize.")
    print()

    try:
        session = authenticate_tidal()

        # Test the session by getting user info
        user = session.user
        print()
        print("=" * 60)
        print(f"✅ Successfully logged in!")
        if user and hasattr(user, 'first_name') and user.first_name:
            print(f"User: {user.first_name} {user.last_name}")
        print(f"Country: {session.country_code}")
        print(f"User ID: {user.id if user else 'Unknown'}")
        print("=" * 60)
        print()
        print("Authentication successful! Session saved.")
        print("You can now run: python main.py")
        print()
    except Exception as e:
        print()
        print(f"❌ Authentication failed: {e}")
        print()
        print("Troubleshooting:")
        print("  - Make sure you have an active Tidal subscription")
        print("  - Check your internet connection")
        print("  - Try running the script again")
