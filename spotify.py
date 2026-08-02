"""
Spotify data collection functions.

IMPORTANT CHANGE: every function here now takes `sp` (an authenticated
spotipy.Spotify client) as its first argument, instead of using one
hardcoded global client. This is what lets the same functions serve many
different website visitors, each with their own Spotify login, rather than
only ever working for one hardcoded account.
"""

import os
import json
import time

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

# Artist details aren't specific to any one visitor, so this cache is safely
# shared across everyone using the app — if Visitor B has an artist Visitor A
# already triggered a lookup for, we skip the extra API call entirely.
_artist_cache = {}


def get_artist_info(sp, artist_id):
    if artist_id not in _artist_cache:
        _artist_cache[artist_id] = sp.artist(artist_id)
        time.sleep(0.05)  # gentle on rate limits
    return _artist_cache[artist_id]


def enrich_artists(sp, artist_refs):
    """Given Spotify's list of {id, name, ...} artist stubs (from a track or
    album), fetch full details for each and return them in the same order."""
    out = []
    for ref in artist_refs:
        info = get_artist_info(sp, ref["id"])
        out.append({
            "id": ref["id"],
            "name": info["name"],
            "genres": info.get("genres", []),
            "popularity": info.get("popularity"),
            "followers": info.get("followers", {}).get("total"),
            "image_url": info["images"][0]["url"] if info.get("images") else None,
        })
    return out


def enrich_track(sp, track):
    """Pull a richer set of fields for a single track object, including every
    artist on the track and every artist on its album (not just the first)."""
    return {
        "name": track["name"],
        "id": track["id"],
        "artists": enrich_artists(sp, track["artists"]),
        "album": track["album"]["name"],
        "album_id": track["album"]["id"],
        "album_type": track["album"].get("album_type"),
        "album_artists": enrich_artists(sp, track["album"].get("artists", [])),
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


def get_user_profile(sp):
    """Basic profile info for the logged-in visitor, including profile picture."""
    me = sp.current_user()
    return {
        "id": me.get("id"),
        "display_name": me.get("display_name"),
        "email": me.get("email"),
        "country": me.get("country"),
        "followers": me.get("followers", {}).get("total"),
        "profile_image_url": me["images"][0]["url"] if me.get("images") else None,
        "external_url": me.get("external_urls", {}).get("spotify"),
    }


def get_recently_played(sp, limit=50):
    results = sp.current_user_recently_played(limit=limit)
    out = []
    for item in results["items"]:
        track = item["track"]
        if track.get("type") != "track":  # skip podcast episodes
            continue
        enriched = enrich_track(sp, track)
        enriched["played_at"] = item["played_at"]
        out.append(enriched)
    return out


def get_top_tracks(sp):
    """Top tracks across all three Spotify time ranges."""
    out = {}
    for time_range in ["short_term", "medium_term", "long_term"]:
        results = sp.current_user_top_tracks(limit=50, time_range=time_range)
        out[time_range] = [enrich_track(sp, t) for t in results["items"]]
    return out


def get_top_artists(sp):
    out = {}
    for time_range in ["short_term", "medium_term", "long_term"]:
        results = sp.current_user_top_artists(limit=50, time_range=time_range)
        out[time_range] = [
            {
                "id": a["id"],
                "name": a["name"],
                "genres": a.get("genres", []),
                "popularity": a.get("popularity"),
                "followers": a.get("followers", {}).get("total"),
                "image_url": a["images"][0]["url"] if a.get("images") else None,
            }
            for a in results["items"]
        ]
    return out


def get_saved_tracks(sp, limit=50):
    out = []
    offset = 0
    while True:
        results = sp.current_user_saved_tracks(limit=limit, offset=offset)
        if not results["items"]:
            break
        for item in results["items"]:
            enriched = enrich_track(sp, item["track"])
            enriched["added_at"] = item["added_at"]
            out.append(enriched)
        offset += limit
        if len(results["items"]) < limit:
            break
    return out


def get_saved_albums(sp):
    out = []
    results = sp.current_user_saved_albums(limit=50)
    for item in results["items"]:
        album = item["album"]
        out.append({
            "id": album["id"],
            "name": album["name"],
            "album_type": album.get("album_type"),
            "artists": enrich_artists(sp, album.get("artists", [])),
            "release_date": album.get("release_date"),
            "total_tracks": album.get("total_tracks"),
            "image_url": album["images"][0]["url"] if album.get("images") else None,
            "added_at": item["added_at"],
        })
    return out


def get_playlist_tracks(sp, playlist_id):
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
            if not track or not track.get("id") or track.get("type") != "track":
                continue
            enriched = enrich_track(sp, track)
            enriched["added_at"] = item.get("added_at")
            out.append(enriched)

        offset += limit
        if len(items) < limit:
            break

    return out


def get_playlists(sp, include_tracks=True):
    out = []
    results = sp.current_user_playlists(limit=50)
    for pl in results["items"]:
        playlist_data = {
            "id": pl["id"],
            "name": pl["name"],
            "owner_id": pl["owner"]["id"],
            "owner_name": pl["owner"].get("display_name"),
            "track_count": pl["tracks"]["total"],
            "public": pl.get("public"),
            "image_url": pl["images"][0]["url"] if pl.get("images") else None,
        }
        if include_tracks:
            playlist_data["tracks"] = get_playlist_tracks(sp, pl["id"])
        out.append(playlist_data)
    return out


def collect_all_data(sp):
    """Run the full collection for whichever visitor `sp` is authenticated as."""
    return {
        "user_profile": get_user_profile(sp),
        "recently_played": get_recently_played(sp),
        "top_tracks": get_top_tracks(sp),
        "top_artists": get_top_artists(sp),
        "saved_tracks": get_saved_tracks(sp),
        "saved_albums": get_saved_albums(sp),
        "playlists": get_playlists(sp),
    }


def main():
    """Standalone local run for testing outside Flask — uses your own
    hardcoded credentials, same as the original single-user script."""
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    from dotenv import load_dotenv

    load_dotenv()

    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=os.environ.get("SPOTIFY_CLIENT_ID"),
        client_secret=os.environ.get("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:5000/"),
        scope=SCOPES,
    ))

    data = collect_all_data(sp)

    with open("spotify_data.json", "w") as f:
        json.dump(data, f, indent=2)

    print("Saved spotify_data.json")
    for time_range in ["short_term", "medium_term", "long_term"]:
        print(f"- {time_range}: {len(data['top_tracks'][time_range])} top tracks, "
              f"{len(data['top_artists'][time_range])} top artists")


if __name__ == "__main__":
    main()
