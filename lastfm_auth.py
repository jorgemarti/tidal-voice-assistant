#!/usr/bin/env python3
"""
One-time Last.fm authorisation (desktop flow, no callback URL needed).

Prints a URL; open it, approve the application, and this script keeps polling until Last.fm
hands back a session key, which is saved to LASTFM_SESSION_FILE. Session keys do not expire.

    python lastfm_auth.py
"""

import json
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from config import LASTFM_SESSION_FILE  # noqa: E402

POLL_SECONDS = 5
TIMEOUT_SECONDS = 600


def main():
    key, secret = os.environ.get("LASTFM_API_KEY"), os.environ.get("LASTFM_API_SECRET")
    if not key or not secret:
        print("Set LASTFM_API_KEY and LASTFM_API_SECRET in .env first (https://www.last.fm/api/account/create)")
        sys.exit(1)
    import pylast

    network = pylast.LastFMNetwork(api_key=key, api_secret=secret)
    skg = pylast.SessionKeyGenerator(network)
    url = skg.get_web_auth_url()
    print(f"Open this URL and approve the application:\n\n  {url}\n", flush=True)
    deadline = time.time() + TIMEOUT_SECONDS
    while time.time() < deadline:
        try:
            session_key = skg.get_web_auth_session_key(url)
        except pylast.WSError:
            time.sleep(POLL_SECONDS)
            continue
        with open(LASTFM_SESSION_FILE, "w") as f:
            json.dump({"session_key": session_key}, f)
        os.chmod(LASTFM_SESSION_FILE, 0o600)
        user = pylast.LastFMNetwork(api_key=key, api_secret=secret, session_key=session_key).get_authenticated_user()
        print(f"Authorised as {user.get_name()}. Session saved to {LASTFM_SESSION_FILE}.")
        return
    print("Timed out waiting for approval.")
    sys.exit(1)


if __name__ == "__main__":
    main()
