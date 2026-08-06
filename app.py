"""
Main Flask application.

Now with real Spotify OAuth: each visitor gets their own login, and their
token is stored in their own browser session (not shared with other
visitors, not written to disk).
"""

import os
import hashlib
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

# --- Genres page queries ---
#
# GENRE_WEIGHTED_SCORE_QUERY is your query, fixed: added the missing
# WHERE user_id filter (same bug class as the artist queries), and widened
# the time_range filter to include medium_term — the venn diagram and
# grouped bar chart both need all three ranges, not just short/long.
GENRE_WEIGHTED_SCORE_QUERY = """
    SELECT
        tt.time_range,
        ag.genre_name,
        COUNT(DISTINCT tt.track_id) AS track_count,
        SUM(51 - tt.rank_pos) AS weighted_genre_score,
        ROUND(AVG(tt.rank_pos), 2) AS average_rank
    FROM top_tracks tt
    JOIN track_artists ta ON tt.track_id = ta.track_id AND ta.position = 0
    JOIN artist_genres ag ON ta.artist_id = ag.artist_id
    WHERE tt.user_id = %s
    GROUP BY tt.time_range, ag.genre_name
    ORDER BY tt.time_range, weighted_genre_score DESC;
"""

# You sent this one as two bare fragments with no FROM/JOIN/WHERE visible —
# this is my reconstruction, not a fix of something I could see broken.
# Scope chosen: unique genres vs. unique tracks across ALL of top_tracks
# (all 3 ranges combined, deduplicated by track). If your original scoped
# this to a single range or to saved_tracks instead, swap the FROM/JOIN here.
GENRE_DIVERSITY_QUERY = """
    SELECT
        COUNT(DISTINCT ag.genre_name) AS unique_genre_count,
        COUNT(DISTINCT tt.track_id) AS unique_track_count,
        ROUND(
            COUNT(DISTINCT ag.genre_name) * 1.0 / NULLIF(COUNT(DISTINCT tt.track_id), 0),
            2
        ) AS genre_diversity_ratio,
        CASE
            WHEN COUNT(DISTINCT ag.genre_name) >= 15 THEN 'Eclectic / Wide Blend'
            WHEN COUNT(DISTINCT ag.genre_name) BETWEEN 6 AND 14 THEN 'Balanced Theme'
            WHEN COUNT(DISTINCT ag.genre_name) BETWEEN 1 AND 5 THEN 'Laser-Focused / Single Vibe'
            ELSE 'Empty / Unassigned'
        END AS playlist_vibe_type
    FROM top_tracks tt
    JOIN track_artists ta ON tt.track_id = ta.track_id AND ta.position = 0
    JOIN artist_genres ag ON ta.artist_id = ag.artist_id
    WHERE tt.user_id = %s;
"""


def genre_to_color(genre_name):
    """Deterministic color per genre: hash the name to a hue, keep
    saturation/lightness fixed so every genre gets an equally vivid,
    readable color — same genre always gets the same color, no lookup
    table to maintain by hand."""
    digest = int(hashlib.md5(genre_name.encode()).hexdigest(), 16)
    hue = digest % 360
    return hsl_to_hex(hue, 68, 55)


def hsl_to_hex(h, s, l):
    s /= 100
    l /= 100
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2
    if h < 60: r, g, b = c, x, 0
    elif h < 120: r, g, b = x, c, 0
    elif h < 180: r, g, b = 0, c, x
    elif h < 240: r, g, b = 0, x, c
    elif h < 300: r, g, b = x, 0, c
    else: r, g, b = c, 0, x
    r, g, b = [round((v + m) * 255) for v in (r, g, b)]
    return f"#{r:02X}{g:02X}{b:02X}"


def bucket_venn_regions(short_set, medium_set, long_set):
    """Split 3 genre sets into the 7 non-overlapping venn regions."""
    return {
        "short_only": sorted(short_set - medium_set - long_set),
        "medium_only": sorted(medium_set - short_set - long_set),
        "long_only": sorted(long_set - short_set - medium_set),
        "short_medium": sorted((short_set & medium_set) - long_set),
        "short_long": sorted((short_set & long_set) - medium_set),
        "medium_long": sorted((medium_set & long_set) - short_set),
        "all_three": sorted(short_set & medium_set & long_set),
    }


# --- Listening Activity page queries ---
#
# All built fresh against recently_played, since none of the queries you've
# sent so far cover this page. Important caveat, same as the Stability chart
# on the Artists page: recently_played only ever holds Spotify's last ~50
# plays per fetch, so these numbers only become meaningful once
# collect_spotify_data.py has run repeatedly over time (e.g. a daily job)
# rather than a single one-off run.

ACTIVITY_KPI_QUERY = """
    SELECT
        COUNT(*) AS total_plays,
        COUNT(DISTINCT rp.track_id) AS unique_tracks,
        ROUND(SUM(t.duration_ms) / 60000.0, 0) AS listening_minutes,
        ROUND(AVG(t.duration_ms) / 60000.0, 1) AS avg_track_length_minutes,
        ROUND((COUNT(*) - COUNT(DISTINCT rp.track_id)) * 100.0 / NULLIF(COUNT(*), 0), 1) AS repeat_rate,
        MIN(rp.played_at) AS coverage_start,
        MAX(rp.played_at) AS coverage_end
    FROM recently_played rp
    JOIN tracks t ON rp.track_id = t.track_id
    WHERE rp.user_id = %s;
"""

TIME_OF_DAY_QUERY = """
    SELECT
        CASE
            WHEN HOUR(played_at) BETWEEN 5 AND 11 THEN 'Morning'
            WHEN HOUR(played_at) BETWEEN 12 AND 16 THEN 'Afternoon'
            WHEN HOUR(played_at) BETWEEN 17 AND 20 THEN 'Evening'
            ELSE 'Night'
        END AS time_bucket,
        COUNT(*) AS play_count
    FROM recently_played
    WHERE user_id = %s
    GROUP BY time_bucket;
"""

WEEKDAY_QUERY = """
    SELECT DAYNAME(played_at) AS weekday, COUNT(*) AS play_count
    FROM recently_played
    WHERE user_id = %s
    GROUP BY weekday, DAYOFWEEK(played_at)
    ORDER BY DAYOFWEEK(played_at);
"""

REPEAT_TIER_QUERY = """
    WITH track_play_counts AS (
        SELECT track_id, COUNT(*) AS play_count
        FROM recently_played
        WHERE user_id = %s
        GROUP BY track_id
    )
    SELECT
        CASE
            WHEN play_count = 1 THEN 'Single listen'
            WHEN play_count BETWEEN 2 AND 4 THEN 'Repeated'
            ELSE 'Heavy rotation'
        END AS repeat_tier,
        COUNT(*) AS track_count
    FROM track_play_counts
    GROUP BY repeat_tier;
"""

# --- Playlists page queries ---
#
# Both are your queries, fixed. See the earlier chat message for the full
# reasoning — short version: query 1 was missing WHERE user_id entirely;
# query 2 grouped by user_id (looked safe) but its "% of library" subquery
# counted every user's playlists as the denominator, not just the current
# user's — a bug that produces a believable-looking wrong number rather
# than an obviously broken one.
#
# No LIMIT here — pulled once for the whole page, then split in Python into
# "top 5 self-curated by genre diversity" (radar chart) and "all playlists,
# grouped by vibe type" (mood bar chart), rather than querying twice.

PLAYLIST_DIVERSITY_QUERY = """
    SELECT
        p.playlist_id,
        p.name AS playlist_name,
        p.owner_id,
        p.user_id,
        COUNT(DISTINCT pt.track_id) AS total_tracks,
        COUNT(DISTINCT ta.artist_id) AS unique_artists,
        COUNT(DISTINCT ag.genre_name) AS unique_genres,
        ROUND(COUNT(DISTINCT ta.artist_id) * 1.0 / NULLIF(COUNT(DISTINCT pt.track_id), 0), 2) AS artist_diversity_ratio,
        ROUND(COUNT(DISTINCT ag.genre_name) * 1.0 / NULLIF(COUNT(DISTINCT pt.track_id), 0), 2) AS genre_diversity_ratio,
        CASE
            WHEN COUNT(DISTINCT ag.genre_name) >= 15 THEN 'Eclectic / Wide Blend'
            WHEN COUNT(DISTINCT ag.genre_name) BETWEEN 6 AND 14 THEN 'Balanced Theme'
            WHEN COUNT(DISTINCT ag.genre_name) BETWEEN 1 AND 5 THEN 'Laser-Focused / Single Vibe'
            ELSE 'Empty / Unassigned'
        END AS playlist_vibe_type
    FROM playlists p
    JOIN playlist_tracks pt ON p.playlist_id = pt.playlist_id
    JOIN tracks t ON pt.track_id = t.track_id
    JOIN track_artists ta ON t.track_id = ta.track_id
    LEFT JOIN artist_genres ag ON ta.artist_id = ag.artist_id
    WHERE p.user_id = %s
    GROUP BY p.playlist_id, p.name, p.owner_id, p.user_id
    ORDER BY unique_genres DESC;
"""

CURATION_SOURCE_QUERY = """
    SELECT
        CASE
            WHEN p.owner_id = p.user_id THEN 'Self-Curated (Owned)'
            WHEN LOWER(p.owner_id) IN ('spotify', 'spotifycharts') THEN 'Spotify Official / Editorial'
            ELSE 'External / Friend Curated'
        END AS curation_source,
        COUNT(DISTINCT p.playlist_id) AS playlist_count,
        SUM(p.track_count) AS total_tracks,
        ROUND(AVG(p.track_count), 1) AS avg_tracks_per_playlist,
        ROUND(
            (COUNT(DISTINCT p.playlist_id) * 100.0) /
            (SELECT COUNT(*) FROM playlists WHERE user_id = %s),
            1
        ) AS pct_of_library_playlists
    FROM playlists p
    WHERE p.user_id = %s
    GROUP BY curation_source
    ORDER BY playlist_count DESC;
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


@app.route("/dashboard/genres")
def genres_page():
    sp_oauth = make_spotify_oauth()
    token_info = sp_oauth.validate_token(sp_oauth.cache_handler.get_cached_token())

    if not token_info:
        return redirect(url_for("login"))

    user_id = session.get("user_id")
    if not user_id:
        sp = spotipy.Spotify(auth=token_info["access_token"])
        user_id = get_user_profile(sp)["id"]
        session["user_id"] = user_id

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(GENRE_WEIGHTED_SCORE_QUERY, (user_id,))
    weighted_rows = cursor.fetchall()

    cursor.execute(GENRE_DIVERSITY_QUERY, (user_id,))
    diversity_row = cursor.fetchone()

    cursor.close()
    conn.close()

    # --- genre sets per range, for the venn diagram ---
    genre_sets = {"short_term": set(), "medium_term": set(), "long_term": set()}
    for row in weighted_rows:
        genre_sets[row["time_range"]].add(row["genre_name"])
    venn_regions = bucket_venn_regions(
        genre_sets["short_term"], genre_sets["medium_term"], genre_sets["long_term"]
    )

    # --- total weighted score per genre, summed across all 3 ranges ---
    total_score_by_genre = {}
    for row in weighted_rows:
        total_score_by_genre[row["genre_name"]] = (
            total_score_by_genre.get(row["genre_name"], 0) + row["weighted_genre_score"]
        )
    ranked_genres = sorted(total_score_by_genre.items(), key=lambda kv: kv[1], reverse=True)

    # --- top 3 genres overall power the Aura gradient ---
    top_3_genres = [
        {"name": name, "color": genre_to_color(name)}
        for name, _ in ranked_genres[:3]
    ]

    # --- top 8 genres power the grouped horizontal bar chart ---
    top_genre_names = [name for name, _ in ranked_genres[:8]]
    score_by_genre_range = {
        (row["genre_name"], row["time_range"]): row["weighted_genre_score"]
        for row in weighted_rows
    }
    bar_chart_genres = [
        {
            "name": name,
            "color": genre_to_color(name),
            "short_term": score_by_genre_range.get((name, "short_term"), 0),
            "medium_term": score_by_genre_range.get((name, "medium_term"), 0),
            "long_term": score_by_genre_range.get((name, "long_term"), 0),
        }
        for name in top_genre_names
    ]

    data = {
        "unique_genre_count": diversity_row["unique_genre_count"] if diversity_row else 0,
        "genre_diversity_ratio": diversity_row["genre_diversity_ratio"] if diversity_row else 0,
        "playlist_vibe_type": diversity_row["playlist_vibe_type"] if diversity_row else "—",
        "top_3_genres": top_3_genres,
        "bar_chart_genres": bar_chart_genres,
        "venn_regions": venn_regions,
    }
    return render_template("genres.html", data=data)


@app.route("/dashboard/activity")
def activity_page():
    sp_oauth = make_spotify_oauth()
    token_info = sp_oauth.validate_token(sp_oauth.cache_handler.get_cached_token())

    if not token_info:
        return redirect(url_for("login"))

    user_id = session.get("user_id")
    if not user_id:
        sp = spotipy.Spotify(auth=token_info["access_token"])
        user_id = get_user_profile(sp)["id"]
        session["user_id"] = user_id

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(ACTIVITY_KPI_QUERY, (user_id,))
    kpi_row = cursor.fetchone()

    cursor.execute(TIME_OF_DAY_QUERY, (user_id,))
    time_of_day_rows = cursor.fetchall()

    cursor.execute(WEEKDAY_QUERY, (user_id,))
    weekday_rows = cursor.fetchall()

    cursor.execute(REPEAT_TIER_QUERY, (user_id,))
    repeat_rows = cursor.fetchall()

    cursor.close()
    conn.close()

    # Fill in zero for any bucket with no rows, so charts always show every
    # category rather than silently omitting empty ones.
    time_of_day = {"Morning": 0, "Afternoon": 0, "Evening": 0, "Night": 0}
    for row in time_of_day_rows:
        time_of_day[row["time_bucket"]] = row["play_count"]

    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday = {day: 0 for day in weekday_order}
    for row in weekday_rows:
        weekday[row["weekday"]] = row["play_count"]

    repeat_tiers = {"Single listen": 0, "Repeated": 0, "Heavy rotation": 0}
    for row in repeat_rows:
        repeat_tiers[row["repeat_tier"]] = row["track_count"]

    def format_date(dt):
        return f"{dt.month}-{dt.day}-{dt.year}" if dt else "—"

    data = {
        "streams": kpi_row["total_plays"] if kpi_row else 0,
        "unique_tracks": kpi_row["unique_tracks"] if kpi_row else 0,
        "listening_minutes": kpi_row["listening_minutes"] if kpi_row else 0,
        "avg_track_length": kpi_row["avg_track_length_minutes"] if kpi_row else 0,
        "repeat_rate": kpi_row["repeat_rate"] if kpi_row else 0,
        "coverage_start": format_date(kpi_row["coverage_start"]) if kpi_row else "—",
        "coverage_end": format_date(kpi_row["coverage_end"]) if kpi_row else "—",
        "time_of_day": time_of_day,
        "weekday": weekday,
        "repeat_tiers": repeat_tiers,
    }
    return render_template("activity.html", data=data)


@app.route("/dashboard/playlists")
def playlists_page():
    sp_oauth = make_spotify_oauth()
    token_info = sp_oauth.validate_token(sp_oauth.cache_handler.get_cached_token())

    if not token_info:
        return redirect(url_for("login"))

    user_id = session.get("user_id")
    if not user_id:
        sp = spotipy.Spotify(auth=token_info["access_token"])
        user_id = get_user_profile(sp)["id"]
        session["user_id"] = user_id

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(CURATION_SOURCE_QUERY, (user_id, user_id))
    curation_rows = cursor.fetchall()

    cursor.execute(PLAYLIST_DIVERSITY_QUERY, (user_id,))
    playlist_rows = cursor.fetchall()

    cursor.close()
    conn.close()

    curation_sources = ["Self-Curated (Owned)", "Spotify Official / Editorial", "External / Friend Curated"]
    curation_stats = {src: {"playlist_count": 0, "total_tracks": 0} for src in curation_sources}
    for row in curation_rows:
        curation_stats[row["curation_source"]] = {
            "playlist_count": row["playlist_count"],
            "total_tracks": row["total_tracks"] or 0,
        }

    # Top 5 self-curated playlists by genre diversity ratio, for the radar chart
    self_curated = [r for r in playlist_rows if r["owner_id"] == r["user_id"]]
    top_5_by_diversity = sorted(
        self_curated, key=lambda r: r["genre_diversity_ratio"] or 0, reverse=True
    )[:5]

    # Mood = playlist_vibe_type bucket counts across ALL playlists (not just
    # self-curated) — this is literally your vibe_type CASE, just counted
    # per bucket instead of shown per playlist.
    vibe_types = ["Eclectic / Wide Blend", "Balanced Theme", "Laser-Focused / Single Vibe", "Empty / Unassigned"]
    mood_counts = {vibe: 0 for vibe in vibe_types}
    for row in playlist_rows:
        mood_counts[row["playlist_vibe_type"]] += 1

    data = {
        "curation_stats": curation_stats,
        "radar_playlists": [
            {"name": r["playlist_name"], "genre_diversity_ratio": r["genre_diversity_ratio"] or 0}
            for r in top_5_by_diversity
        ],
        "mood_counts": mood_counts,
    }
    return render_template("playlists.html", data=data)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
