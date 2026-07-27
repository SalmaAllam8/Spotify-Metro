

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


def enrich_artists(artist_refs):
    """Given Spotify's list of {id, name, ...} artist stubs (from a track or
    album), fetch full details for each and return them in the same order."""
    out = []
    for ref in artist_refs:
        info = get_artist_info(ref["id"])
        out.append({
            "id": ref["id"],
            "name": info["name"],
            "genres": info.get("genres", []),
            "popularity": info.get("popularity"),
            "followers": info.get("followers", {}).get("total"),
            "image_url": info["images"][0]["url"] if info.get("images") else None,
        })
    return out


def enrich_track(track):
    """Pull a richer set of fields for a single track object, including every
    artist on the track and every artist on its album (not just the first)."""
    return {
        "name": track["name"],
        "id": track["id"],
        "artists": enrich_artists(track["artists"]),
        "album": track["album"]["name"],
        "album_id": track["album"]["id"],
        "album_type": track["album"].get("album_type"),
        "album_artists": enrich_artists(track["album"].get("artists", [])),
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
            "id": album["id"],
            "name": album["name"],
            "album_type": album.get("album_type"),
            "artists": enrich_artists(album.get("artists", [])),
            "release_date": album.get("release_date"),
            "total_tracks": album.get("total_tracks"),
            "image_url": album["images"][0]["url"] if album.get("images") else None,
            "added_at": item["added_at"],
        })
    return out


def get_playlist_tracks(playlist_id):
    """Fetch every track inside a single playlist, with pagination."""
    out = []
    offset = 0
    limit = 100
    while True:
        results = sp.playlist_items(
            playlist_id,
            limit=limit,
            offset=offset,
            fields="items(added_at,track),next",
        )
        items = results["items"]
        if not items:
            break

        for item in items:
            track = item.get("track")
            # Local files / removed tracks can come back as None or missing an id
            if not track or not track.get("id"):
                continue
            enriched = enrich_track(track)
            enriched["added_at"] = item.get("added_at")
            out.append(enriched)

        offset += limit
        if len(items) < limit:
            break

    return out


def get_playlists(include_tracks=True):
    out = []
    results = sp.current_user_playlists(limit=50)
    for pl in results["items"]:
        playlist_data = {
            "name": pl["name"],
            "id": pl["id"],
            "owner_id": pl["owner"]["id"],
            "owner_name": pl["owner"].get("display_name"),
            "track_count": pl["tracks"]["total"],
            "public": pl.get("public"),
            "image_url": pl["images"][0]["url"] if pl.get("images") else None,
        }
        if include_tracks:
            playlist_data["tracks"] = get_playlist_tracks(pl["id"])
        out.append(playlist_data)
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
    for time_range in ["short_term", "medium_term", "long_term"]:
        print(f"- {time_range}: {len(data['top_tracks'][time_range])} top tracks, "
              f"{len(data['top_artists'][time_range])} top artists")
    print(f"- {len(data['saved_tracks'])} saved tracks")
    print(f"- {len(data['saved_albums'])} saved albums")
    print(f"- {len(data['playlists'])} playlists")


if __name__ == "__main__":
    main()

