
import os
import json
from datetime import datetime
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.environ.get("MYSQL_HOST"),
    "port": os.environ.get("MYSQL_PORT", 3306),
    "user": os.environ.get("MYSQL_USER"),
    "password": os.environ.get("MYSQL_PASSWORD"),
    "database": os.environ.get("MYSQL_DATABASE", "spotify_data"),
}


def parse_spotify_datetime(value):
    """Spotify gives ISO 8601 timestamps like '2026-07-20T12:34:56.789Z'."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def upsert_artist(cursor, artist_id, name, popularity, followers, image_url):
    sql = """
        INSERT INTO artists (artist_id, name, popularity, followers, image_url)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            name = VALUES(name),
            popularity = VALUES(popularity),
            followers = VALUES(followers),
            image_url = VALUES(image_url)
    """
    cursor.execute(sql, (artist_id, name, popularity, followers, image_url))


def link_artist_genres(cursor, artist_id, genres):
    """Ensure each genre exists, then link it to this artist. Doesn't remove
    links for genres the artist no longer has (Spotify's genre tags rarely
    shrink, so this is a reasonable tradeoff for simplicity)."""
    for genre in (genres or []):
        cursor.execute("INSERT IGNORE INTO genres (name) VALUES (%s)", (genre,))
        cursor.execute(
            "INSERT IGNORE INTO artist_genres (artist_id, genre_name) VALUES (%s, %s)",
            (artist_id, genre),
        )


def upsert_album(cursor, album_id, name, album_type, release_date, image_url):
    sql = """
        INSERT INTO albums (album_id, name, album_type, release_date, image_url)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            name = VALUES(name),
            album_type = VALUES(album_type),
            release_date = VALUES(release_date),
            image_url = VALUES(image_url)
    """
    cursor.execute(sql, (album_id, name, album_type, release_date, image_url))


def upsert_track(cursor, track):
    sql = """
        INSERT INTO tracks (track_id, name, album_id, duration_ms,
                             popularity, explicit, preview_url, external_url)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            name = VALUES(name),
            popularity = VALUES(popularity),
            preview_url = VALUES(preview_url)
    """
    cursor.execute(sql, (
        track["id"], track["name"], track.get("album_id"),
        track["duration_ms"], track.get("popularity"), track.get("explicit"),
        track.get("preview_url"), track.get("external_url"),
    ))


def link_artists(cursor, junction_table, fk_column, entity_id, artists):
    """Upsert each artist in the list, link their genres, and link them to
    the given track/album via the junction table, preserving their order
    (position 0 = primary/main artist)."""
    for position, artist in enumerate(artists or []):
        upsert_artist(cursor, artist["id"], artist["name"],
                     artist.get("popularity"), artist.get("followers"), artist.get("image_url"))
        link_artist_genres(cursor, artist["id"], artist.get("genres"))
        cursor.execute(f"""
            INSERT IGNORE INTO {junction_table} ({fk_column}, artist_id, position)
            VALUES (%s, %s, %s)
        """, (entity_id, artist["id"], position))


def load_track_with_relations(cursor, track):
    """A track carries its artists/album fields from enrich_track — insert
    the album and all artists first so the track's foreign keys are satisfied."""
    if track.get("album_id"):
        upsert_album(cursor, track["album_id"], track["album"], track.get("album_type"),
                     track.get("album_release_date"), track.get("album_image_url"))
        link_artists(cursor, "album_artists", "album_id", track["album_id"],
                    track.get("album_artists"))
    upsert_track(cursor, track)
    link_artists(cursor, "track_artists", "track_id", track["id"], track.get("artists"))


def load_data(cursor, data):
    # --- user ---
    user = data["user_profile"]
    cursor.execute("""
        INSERT INTO users (user_id, display_name, email, country, followers,
                            profile_image_url, external_url)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            display_name = VALUES(display_name), followers = VALUES(followers),
            profile_image_url = VALUES(profile_image_url)
    """, (user["id"], user["display_name"], user.get("email"), user.get("country"),
          user.get("followers"), user.get("profile_image_url"), user.get("external_url")))
    user_id = user["id"]

    # --- recently played ---
    for track in data["recently_played"]:
        load_track_with_relations(cursor, track)
        cursor.execute("""
            INSERT IGNORE INTO recently_played (user_id, track_id, played_at)
            VALUES (%s, %s, %s)
        """, (user_id, track["id"], parse_spotify_datetime(track["played_at"])))

    # --- top tracks / top artists (per time range) ---
    for time_range, tracks in data["top_tracks"].items():
        for rank, track in enumerate(tracks, start=1):
            load_track_with_relations(cursor, track)
            cursor.execute("""
                INSERT INTO top_tracks (user_id, track_id, time_range, rank_pos)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE rank_pos = VALUES(rank_pos)
            """, (user_id, track["id"], time_range, rank))

    for time_range, artists in data["top_artists"].items():
        for rank, artist in enumerate(artists, start=1):
            upsert_artist(cursor, artist["id"], artist["name"],
                         artist.get("popularity"), artist.get("followers"), artist.get("image_url"))
            link_artist_genres(cursor, artist["id"], artist.get("genres"))
            cursor.execute("""
                INSERT INTO top_artists (user_id, artist_id, time_range, rank_pos)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE rank_pos = VALUES(rank_pos)
            """, (user_id, artist["id"], time_range, rank))

    # --- saved tracks ---
    for track in data["saved_tracks"]:
        load_track_with_relations(cursor, track)
        cursor.execute("""
            INSERT IGNORE INTO saved_tracks (user_id, track_id, added_at)
            VALUES (%s, %s, %s)
        """, (user_id, track["id"], parse_spotify_datetime(track["added_at"])))

    # --- playlists + their tracks ---
    for pl in data["playlists"]:
        cursor.execute("""
            INSERT INTO playlists (playlist_id, user_id, name, owner_id, owner_name,
                                    track_count, is_public, image_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                name = VALUES(name), track_count = VALUES(track_count)
        """, (pl["id"], user_id, pl["name"], pl.get("owner_id"), pl.get("owner_name"),
              pl["track_count"], pl.get("public"), pl.get("image_url")))

        for track in pl.get("tracks", []):
            load_track_with_relations(cursor, track)
            cursor.execute("""
                INSERT IGNORE INTO playlist_tracks (playlist_id, track_id, added_at)
                VALUES (%s, %s, %s)
            """, (pl["id"], track["id"], parse_spotify_datetime(track.get("added_at"))))


def main():
    with open("spotify_data.json") as f:
        data = json.load(f)

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        load_data(cursor, data)
        conn.commit()
        print("Data loaded successfully.")
    except Exception as e:
        conn.rollback()
        print(f"Error loading data, rolled back: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
    #bugs

