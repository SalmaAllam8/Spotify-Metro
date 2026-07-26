CREATE DATABASE IF NOT EXISTS spotify_data;
USE spotify_data;

CREATE TABLE IF NOT EXISTS users (
    user_id          VARCHAR(64) PRIMARY KEY,
    display_name     VARCHAR(255),
    email            VARCHAR(255),
    country           VARCHAR(10),
    followers        INT,
    profile_image_url TEXT,
    external_url     TEXT
);

CREATE TABLE IF NOT EXISTS artists (
    artist_id   VARCHAR(64) PRIMARY KEY,
    name        VARCHAR(255),
    genres      JSON,
    popularity  INT,
    followers   INT,
    image_url   TEXT
);

CREATE TABLE IF NOT EXISTS albums (
    album_id      VARCHAR(64) PRIMARY KEY,
    name          VARCHAR(255),
    artist_id     VARCHAR(64),
    release_date  VARCHAR(20),
    image_url     TEXT,
    FOREIGN KEY (artist_id) REFERENCES artists(artist_id)
);

CREATE TABLE IF NOT EXISTS tracks (
    track_id      VARCHAR(64) PRIMARY KEY,
    name          VARCHAR(255),
    artist_id     VARCHAR(64),
    album_id      VARCHAR(64),
    duration_ms   INT,
    popularity    INT,
    explicit      BOOLEAN,
    preview_url   TEXT,
    external_url  TEXT,
    FOREIGN KEY (artist_id) REFERENCES artists(artist_id),
    FOREIGN KEY (album_id) REFERENCES albums(album_id)
);

-- A user's listening history: same track can appear many times at different timestamps
CREATE TABLE IF NOT EXISTS recently_played (
    user_id    VARCHAR(64),
    track_id   VARCHAR(64),
    played_at  DATETIME,
    PRIMARY KEY (user_id, track_id, played_at),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (track_id) REFERENCES tracks(track_id)
);

CREATE TABLE IF NOT EXISTS top_tracks (
    user_id     VARCHAR(64),
    track_id    VARCHAR(64),
    time_range  ENUM('short_term', 'medium_term', 'long_term'),
    rank_pos    INT,
    PRIMARY KEY (user_id, track_id, time_range),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (track_id) REFERENCES tracks(track_id)
);

CREATE TABLE IF NOT EXISTS top_artists (
    user_id     VARCHAR(64),
    artist_id   VARCHAR(64),
    time_range  ENUM('short_term', 'medium_term', 'long_term'),
    rank_pos    INT,
    PRIMARY KEY (user_id, artist_id, time_range),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (artist_id) REFERENCES artists(artist_id)
);

CREATE TABLE IF NOT EXISTS saved_tracks (
    user_id   VARCHAR(64),
    track_id  VARCHAR(64),
    added_at  DATETIME,
    PRIMARY KEY (user_id, track_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (track_id) REFERENCES tracks(track_id)
);

CREATE TABLE IF NOT EXISTS playlists (
    playlist_id  VARCHAR(64) PRIMARY KEY,
    user_id      VARCHAR(64),
    name         VARCHAR(255),
    owner        VARCHAR(255),
    track_count  INT,
    is_public    BOOLEAN,
    image_url    TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS playlist_tracks (
    playlist_id  VARCHAR(64),
    track_id     VARCHAR(64),
    added_at     DATETIME,
    PRIMARY KEY (playlist_id, track_id),
    FOREIGN KEY (playlist_id) REFERENCES playlists(playlist_id),
    FOREIGN KEY (track_id) REFERENCES tracks(track_id)
);