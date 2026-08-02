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

from collections import Counter

from spotify import (
    SCOPES, get_user_profile, get_top_tracks, get_top_artists,
    get_playlists,
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-this")


def country_code_to_flag(code):
    """Convert a 2-letter ISO country code (e.g. 'US') into a flag emoji,
    using the Unicode 'regional indicator' letter trick — no image needed."""
    if not code or len(code) != 2:
        return ""
    return "".join(chr(0x1F1E6 + ord(c.upper()) - ord("A")) for c in code)


def compute_range_kpis(top_tracks):
    """Compute the 4 bottom KPI cards for one time range from its top tracks."""
    if not top_tracks:
        return {"hours": 0, "unique_artists": 0, "repeat_rate": 0, "mainstream_score": 0}

    total_ms = sum(t["duration_ms"] for t in top_tracks)
    artist_ids = [t["artists"][0]["id"] for t in top_tracks if t.get("artists")]
    unique_artists = len(set(artist_ids))
    # Proxy for "repeat rate": how much of the list shares an artist with
    # another track in it, rather than every track being a different artist.
    repeat_rate = round((1 - unique_artists / len(top_tracks)) * 100, 1) if top_tracks else 0
    mainstream_score = round(sum(t.get("popularity") or 0 for t in top_tracks) / len(top_tracks), 1)

    return {
        "hours": round(total_ms / 3600000, 1),
        "unique_artists": unique_artists,
        "repeat_rate": repeat_rate,
        "mainstream_score": mainstream_score,
    }


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
    top_tracks_by_range = get_top_tracks(sp)
    top_artists_by_range = get_top_artists(sp)
    # include_tracks=False here — the dashboard only needs a count/link, not
    # every track of every playlist, which is the slow, expensive part.
    playlists = get_playlists(sp, include_tracks=False)

    kpis_by_range = {
        range_key: compute_range_kpis(tracks)
        for range_key, tracks in top_tracks_by_range.items()
    }

    medium_artists = top_artists_by_range["medium_term"]
    favourite_artist = medium_artists[0]["name"] if medium_artists else "—"

    genre_counts = Counter(g for a in medium_artists for g in a.get("genres", []))
    favourite_genre = genre_counts.most_common(1)[0][0] if genre_counts else "—"

    data = {
        "display_name": profile["display_name"],
        "profile_image_url": profile.get("profile_image_url"),
        "country_flag": country_code_to_flag(profile.get("country")),
        "follower_count": profile.get("followers"),
        "favourite_artist": favourite_artist,
        "favourite_genre": favourite_genre,
        "playlist_count": len(playlists),
        "kpis_by_range": kpis_by_range,
    }
    return render_template("dashboard.html", data=data)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
