"""
Expanded Spotify data collector.

IMPORTANT: Do not hardcode your client_id/client_secret in this file if you're
going to share, commit, or publish it. Use environment variables instead
(see the bottom of this file for how that works with python-dotenv).

Also note: Audio Features / Audio Analysis / Recommendations / Related Artists
were restricted by Spotify for apps created/approved after Nov 27, 2024.
If your app predates that and already had access, they may still work for you.
This script does NOT rely on them, so it'll work regardless.
"""

import os
import json
import time
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
load_dotenv()
# ---- Auth setup -----------------------------------------------------------
# Use environment variables instead of hardcoding secrets.
CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:5000/")

SCOPES = " ".join([
    "user-read-private",
    "user-read-email",
    "user-read-recently-played",
    "user-top-read",
    "user-library-read",
    "playlist-read-private",
    "playlist-read-collaborative",
    "user-read-currently-playing",
    "user-read-playback-state",
])

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope=SCOPES,
))

# Cache artist lookups so we don't re-fetch the same artist repeatedly
_artist_cache = {}


def get_artist_info(artist_id):
    if artist_id not in _artist_cache:
        _artist_cache[artist_id] = sp.artist(artist_id)
        time.sleep(0.05)  # gentle on rate limits
    return _artist_cache[artist_id]


def enrich_track(track):
    """Pull a richer set of fields for a single track object."""
    artist_id = track["artists"][0]["id"]
    artist_info = get_artist_info(artist_id)

    return {
        "name": track["name"],
        "id": track["id"],
        "artist": artist_info["name"],
        "artist_genres": artist_info.get("genres", []),
        "artist_popularity": artist_info.get("popularity"),
        "artist_followers": artist_info.get("followers", {}).get("total"),
        "artist_image_url": (
            artist_info["images"][0]["url"] if artist_info.get("images") else None
        ),
        "album": track["album"]["name"],
        "album_release_date": track["album"].get("release_date"),
        "album_image_url": (
            track["album"]["images"][0]["url"] if track["album"].get("images") else None
        ),
        "duration_ms": track["duration_ms"],
        "popularity": track.get("popularity"),
        "explicit": track.get("explicit"),
        "preview_url": track.get("preview_url"),
        "external_url": track["external_urls"].get("spotify"),
    }


def get_recently_played(limit=50):
    results = sp.current_user_recently_played(limit=limit)
    out = []
    for item in results["items"]:
        enriched = enrich_track(item["track"])
        enriched["played_at"] = item["played_at"]
        out.append(enriched)
    return out


def get_top_tracks():
    """Top tracks across all three Spotify time ranges."""
    out = {}
    for time_range in ["short_term", "medium_term", "long_term"]:
        results = sp.current_user_top_tracks(limit=50, time_range=time_range)
        out[time_range] = [enrich_track(t) for t in results["items"]]
    return out


def get_top_artists():
    out = {}
    for time_range in ["short_term", "medium_term", "long_term"]:
        results = sp.current_user_top_artists(limit=50, time_range=time_range)
        out[time_range] = [
            {
                "name": a["name"],
                "id": a["id"],
                "genres": a.get("genres", []),
                "popularity": a.get("popularity"),
                "followers": a.get("followers", {}).get("total"),
                "image_url": a["images"][0]["url"] if a.get("images") else None,
            }
            for a in results["items"]
        ]
    return out


def get_saved_tracks(limit=50):
    out = []
    offset = 0
    while True:
        results = sp.current_user_saved_tracks(limit=limit, offset=offset)
        if not results["items"]:
            break
        for item in results["items"]:
            enriched = enrich_track(item["track"])
            enriched["added_at"] = item["added_at"]
            out.append(enriched)
        offset += limit
        if len(results["items"]) < limit:
            break
    return out


def get_saved_albums():
    out = []
    results = sp.current_user_saved_albums(limit=50)
    for item in results["items"]:
        album = item["album"]
        out.append({
            "name": album["name"],
            "artist": album["artists"][0]["name"],
            "release_date": album.get("release_date"),
            "total_tracks": album.get("total_tracks"),
            "added_at": item["added_at"],
        })
    return out


def get_playlists():
    out = []
    results = sp.current_user_playlists(limit=50)
    for pl in results["items"]:
        out.append({
            "name": pl["name"],
            "id": pl["id"],
            "owner": pl["owner"]["display_name"],
            "track_count": pl["tracks"]["total"],
            "public": pl.get("public"),
        })
    return out


def get_user_profile():
    """Basic profile info for the logged-in user, including profile picture."""
    me = sp.current_user()
    return {
        "display_name": me.get("display_name"),
        "id": me.get("id"),
        "email": me.get("email"),
        "country": me.get("country"),
        "followers": me.get("followers", {}).get("total"),
        "profile_image_url": me["images"][0]["url"] if me.get("images") else None,
        "external_url": me.get("external_urls", {}).get("spotify"),
    }


def main():
    data = {
        "user_profile": get_user_profile(),
        "recently_played": get_recently_played(),
        "top_tracks": get_top_tracks(),
        "top_artists": get_top_artists(),
        "saved_tracks": get_saved_tracks(),
        "saved_albums": get_saved_albums(),
        "playlists": get_playlists(),
    }

    with open("spotify_data.json", "w") as f:
        json.dump(data, f, indent=2)

    print("Saved spotify_data.json")
    print(f"- {len(data['recently_played'])} recently played tracks")
    print(f"- {len(data['top_tracks']['medium_term'])} medium-term top tracks")
    print(f"- {len(data['top_artists']['medium_term'])} medium-term top artists")
    print(f"- {len(data['saved_tracks'])} saved tracks")
    print(f"- {len(data['saved_albums'])} saved albums")
    print(f"- {len(data['playlists'])} playlists")


if __name__ == "__main__":
    main()
