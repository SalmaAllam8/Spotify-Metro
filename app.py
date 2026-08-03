"""
Main Flask application.

Now with real Spotify OAuth: each visitor gets their own login, and their
token is stored in their own browser session (not shared with other
visitors, not written to disk).
"""

import os
import spotipy
import mysql.connector
from itertools import groupby
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

DB_CONFIG = {
    "host": os.environ.get("MYSQL_HOST"),
    "port": os.environ.get("MYSQL_PORT", 3306),
    "user": os.environ.get("MYSQL_USER"),
    "password": os.environ.get("MYSQL_PASSWORD"),
    "database": os.environ.get("MYSQL_DATABASE", "spotify_data"),
}


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


# See artist_queries.sql for the fully commented versions of these, including
# what was wrong with the originals and why.

TASTE_ARCHETYPE_QUERY = """
    WITH top_track_stats AS (
        SELECT tt.user_id, ROUND(AVG(t.popularity), 1) AS avg_top_track_popularity
        FROM top_tracks tt JOIN tracks t ON tt.track_id = t.track_id
        WHERE tt.user_id = %s GROUP BY tt.user_id
    ),
    top_artist_stats AS (
        SELECT ta.user_id, ROUND(AVG(a.popularity), 1) AS avg_top_artist_popularity
        FROM top_artists ta JOIN artists a ON ta.artist_id = a.artist_id
        WHERE ta.user_id = %s GROUP BY ta.user_id
    ),
    saved_track_stats AS (
        SELECT st.user_id, ROUND(AVG(t.popularity), 1) AS avg_saved_track_popularity
        FROM saved_tracks st JOIN tracks t ON st.track_id = t.track_id
        WHERE st.user_id = %s GROUP BY st.user_id
    )
    SELECT
        u.user_id, u.display_name,
        tts.avg_top_track_popularity, tas.avg_top_artist_popularity, sts.avg_saved_track_popularity,
        ROUND((COALESCE(tts.avg_top_track_popularity, 0) + COALESCE(tas.avg_top_artist_popularity, 0) + COALESCE(sts.avg_saved_track_popularity, 0)) / 3, 1) AS overall_mainstream_score,
        CASE
            WHEN ((COALESCE(tts.avg_top_track_popularity, 0) + COALESCE(tas.avg_top_artist_popularity, 0) + COALESCE(sts.avg_saved_track_popularity, 0)) / 3) >= 75 THEN 'Chart Hopper (Extremely Mainstream)'
            WHEN ((COALESCE(tts.avg_top_track_popularity, 0) + COALESCE(tas.avg_top_artist_popularity, 0) + COALESCE(sts.avg_saved_track_popularity, 0)) / 3) >= 55 THEN 'Balanced Curation (Mainstream & Indie)'
            WHEN ((COALESCE(tts.avg_top_track_popularity, 0) + COALESCE(tas.avg_top_artist_popularity, 0) + COALESCE(sts.avg_saved_track_popularity, 0)) / 3) >= 35 THEN 'Underground & Niche Explorer'
            ELSE 'Deep Underground / Obscure'
        END AS taste_archetype
    FROM users u
    LEFT JOIN top_track_stats tts ON u.user_id = tts.user_id
    LEFT JOIN top_artist_stats tas ON u.user_id = tas.user_id
    LEFT JOIN saved_track_stats sts ON u.user_id = sts.user_id
    WHERE u.user_id = %s;
"""

ARTIST_POPULARITY_DONUT_QUERY = """
    SELECT
        CASE
            WHEN a.popularity >= 70 THEN 'Mainstream'
            WHEN a.popularity BETWEEN 40 AND 69 THEN 'Mid-tier'
            ELSE 'Niche'
        END AS popularity_tier,
        COUNT(DISTINCT a.artist_id) AS artist_count
    FROM top_artists ta JOIN artists a ON ta.artist_id = a.artist_id
    WHERE ta.user_id = %s
    GROUP BY popularity_tier;
"""

STABILITY_QUERY = """
    WITH artist_play_counts AS (
        SELECT ta_link.artist_id, COUNT(*) AS play_count
        FROM recently_played rp
        JOIN track_artists ta_link ON rp.track_id = ta_link.track_id AND ta_link.position = 0
        WHERE rp.user_id = %s
        GROUP BY ta_link.artist_id
    )
    SELECT
        CASE
            WHEN play_count = 1 THEN 'One-time'
            WHEN play_count BETWEEN 2 AND 4 THEN 'Returning'
            ELSE 'Core'
        END AS stability_tier,
        COUNT(*) AS artist_count
    FROM artist_play_counts
    GROUP BY stability_tier;
"""

ARTIST_LOYALTY_QUERY = """
    SELECT
        ta.user_id, a.artist_id, a.name AS artist_name, a.image_url,
        MAX(CASE WHEN ta.time_range = 'short_term' THEN ta.rank_pos END) AS short_term_rank,
        MAX(CASE WHEN ta.time_range = 'medium_term' THEN ta.rank_pos END) AS medium_term_rank,
        MAX(CASE WHEN ta.time_range = 'long_term' THEN ta.rank_pos END) AS long_term_rank,
        CASE
            WHEN SUM(CASE WHEN ta.time_range = 'short_term' THEN 1 ELSE 0 END) > 0 AND SUM(CASE WHEN ta.time_range = 'long_term' THEN 1 ELSE 0 END) > 0 THEN 'Core Loyalty'
            WHEN SUM(CASE WHEN ta.time_range = 'short_term' THEN 1 ELSE 0 END) > 0 AND SUM(CASE WHEN ta.time_range = 'long_term' THEN 1 ELSE 0 END) = 0 THEN 'Trending'
            WHEN SUM(CASE WHEN ta.time_range = 'short_term' THEN 1 ELSE 0 END) = 0 AND SUM(CASE WHEN ta.time_range = 'long_term' THEN 1 ELSE 0 END) > 0 THEN 'Legacy'
            ELSE 'Mid-Term'
        END AS artist_loyalty_tier
    FROM top_artists ta JOIN artists a ON ta.artist_id = a.artist_id
    WHERE ta.user_id = %s
    GROUP BY ta.user_id, a.artist_id, a.name, a.image_url
    ORDER BY FIELD(artist_loyalty_tier, 'Core Loyalty', 'Trending', 'Legacy', 'Mid-Term'), short_term_rank ASC, long_term_rank ASC;
"""

TOP_3_ARTISTS_QUERY = """
    SELECT a.artist_id, a.name, a.image_url, ta.rank_pos
    FROM top_artists ta JOIN artists a ON ta.artist_id = a.artist_id
    WHERE ta.user_id = %s AND ta.time_range = 'medium_term' AND ta.rank_pos <= 3
    ORDER BY ta.rank_pos;
"""


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

    sp = spotipy.Spotify(auth=sp_oauth.cache_handler.get_cached_token()["access_token"])
    session["user_id"] = sp.current_user()["id"]

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


@app.route("/dashboard/artists")
def artists_page():
    sp_oauth = make_spotify_oauth()
    token_info = sp_oauth.validate_token(sp_oauth.cache_handler.get_cached_token())

    if not token_info:
        return redirect(url_for("login"))

    user_id = session.get("user_id")
    if not user_id:
        # Session existed but predates us storing user_id at login — fetch
        # it once and cache it, rather than failing.
        sp = spotipy.Spotify(auth=token_info["access_token"])
        user_id = get_user_profile(sp)["id"]
        session["user_id"] = user_id

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(TASTE_ARCHETYPE_QUERY, (user_id, user_id, user_id, user_id))
    taste_row = cursor.fetchone()

    cursor.execute(TOP_3_ARTISTS_QUERY, (user_id,))
    top_3_artists = cursor.fetchall()

    cursor.execute(STABILITY_QUERY, (user_id,))
    stability_rows = cursor.fetchall()

    cursor.execute(ARTIST_POPULARITY_DONUT_QUERY, (user_id,))
    donut_rows = cursor.fetchall()

    cursor.execute(ARTIST_LOYALTY_QUERY, (user_id,))
    loyalty_rows = cursor.fetchall()

    cursor.close()
    conn.close()

    # Fill in zero for any tier that had no rows at all, so the charts
    # always show all categories rather than silently omitting empty ones.
    stability = {"One-time": 0, "Returning": 0, "Core": 0}
    for row in stability_rows:
        stability[row["stability_tier"]] = row["artist_count"]

    donut = {"Mainstream": 0, "Mid-tier": 0, "Niche": 0}
    for row in donut_rows:
        donut[row["popularity_tier"]] = row["artist_count"]

    # Group the loyalty rows into their 4 categories, top 5 each. The SQL
    # query already orders rows so each category's best-ranked artists come
    # first, so slicing [:5] here is safe.
    loyalty_by_tier = {
        tier: list(rows)[:5]
        for tier, rows in groupby(loyalty_rows, key=lambda r: r["artist_loyalty_tier"])
    }
    for tier in ["Core Loyalty", "Trending", "Legacy", "Mid-Term"]:
        loyalty_by_tier.setdefault(tier, [])

    data = {
        "taste_archetype": taste_row["taste_archetype"] if taste_row else None,
        "overall_mainstream_score": taste_row["overall_mainstream_score"] if taste_row else None,
        "top_3_artists": top_3_artists,
        "stability": stability,
        "donut": donut,
        "loyalty_by_tier": loyalty_by_tier,
    }
    return render_template("artists.html", data=data)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
