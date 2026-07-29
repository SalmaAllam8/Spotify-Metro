"""
Main Flask application.

Now with real Spotify OAuth: each visitor gets their own login, and their
token is stored in their own browser session (not shared with other
visitors, not written to disk).
"""

import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler
from flask import Flask, render_template, redirect, url_for, session, request
from dotenv import load_dotenv

from collect_spotify_data import SCOPES, get_user_profile, get_top_tracks

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-this")


def make_spotify_oauth():
    """A fresh SpotifyOAuth tied to this visitor's own session, so their
    token never gets mixed up with another visitor's."""
    return SpotifyOAuth(
        client_id=os.environ.get("SPOTIFY_CLIENT_ID"),
        client_secret=os.environ.get("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.environ.get("SPOTIFY_REDIRECT_URI"),
        scope=SCOPES,
        cache_handler=FlaskSessionCacheHandler(session),
        show_dialog=True,
    )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login")
def login():
    """Send the visitor to Spotify's own login/authorize page."""
    sp_oauth = make_spotify_oauth()
    return redirect(sp_oauth.get_authorize_url())


@app.route("/callback")
def callback():
    """Spotify redirects here after the visitor approves (or denies) access."""
    sp_oauth = make_spotify_oauth()
    code = request.args.get("code")
    error = request.args.get("error")

    if error:
        # Visitor clicked "cancel" on Spotify's screen instead of approving
        return redirect(url_for("index"))

    sp_oauth.get_access_token(code)  # stores the token in this visitor's session
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    sp_oauth = make_spotify_oauth()
    token_info = sp_oauth.validate_token(sp_oauth.cache_handler.get_cached_token())

    if not token_info:
        # Not logged in (or session expired) — send them to log in first
        return redirect(url_for("login"))

    sp = spotipy.Spotify(auth=token_info["access_token"])

    profile = get_user_profile(sp)
    top_tracks = get_top_tracks(sp)["medium_term"][:10]

    data = {
        "display_name": profile["display_name"],
        "top_tracks": [
            {"name": t["name"], "artist": t["artists"][0]["name"], "popularity": t["popularity"]}
            for t in top_tracks
        ],
        # Real hours/total-tracks totals need the MySQL step (next up) —
        # left as placeholders for now so the page still renders cleanly.
        "total_hours": "—",
        "total_tracks": "—",
    }
    return render_template("dashboard.html", data=data)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
