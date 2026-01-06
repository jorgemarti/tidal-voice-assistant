"""
Tidal authentication module using OAuth
"""

import tidalapi
import json
from config import TIDAL_CONFIG
from pathlib import Path

def authenticate_tidal():
    """
    Perform one-time Tidal OAuth authentication.
    This will open a browser or provide a link for authorization.
    """
    print("Starting Tidal authentication...")
    session = tidalapi.Session()
    
    # OAuth login - will provide a link to authorize
    session.login_oauth_simple()
    
    # Save session for future use
    save_session(session)
    
    print("✅ Tidal authentication successful!")
    print(f"Session saved to: {TIDAL_CONFIG['session_file']}")
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
    Load existing Tidal session from file.
    If session doesn't exist or is invalid, authenticate again.
    """
    session_file = Path(TIDAL_CONFIG['session_file'])
    
    if not session_file.exists():
        print("No existing Tidal session found. Authenticating...")
        return authenticate_tidal()
    
    try:
        with open(session_file, 'r') as f:
            data = json.load(f)
        
        session = tidalapi.Session()
        session.load_oauth_session(
            data['token_type'],
            data['access_token'],
            data['refresh_token'],
            data['expiry_time']
        )
        
        # Test if session is still valid
        try:
            session.check_login()
            print("✅ Loaded existing Tidal session")
            return session
        except Exception as e:
            print(f"⚠️  Existing session invalid: {e}")
            print("Re-authenticating...")
            return authenticate_tidal()
            
    except Exception as e:
        print(f"❌ Error loading session: {e}")
        return authenticate_tidal()

if __name__ == "__main__":
    print("=" * 60)
    print("Tidal Authentication Setup")
    print("=" * 60)
    print()
    print("This will open a browser or provide a link for authorization.")
    print("Follow the instructions and authorize the application.")
    print()
    
    session = authenticate_tidal()
    
    # Test the session by getting user info
    try:
        user = session.user
        print()
        print("=" * 60)
        print(f"Logged in as: {user.first_name} {user.last_name}")
        print(f"Subscription: {session.user.subscription.type}")
        print("=" * 60)
    except Exception as e:
        print(f"⚠️  Could not retrieve user info: {e}")
