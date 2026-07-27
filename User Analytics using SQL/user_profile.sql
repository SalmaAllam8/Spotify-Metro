
SELECT
    display_name,
    email,
    country,
    followers,
    external_url
FROM users;



-- User Library Statistics

SELECT
    u.display_name,

    (SELECT COUNT(*) FROM saved_tracks st
     WHERE st.user_id = u.user_id) AS saved_tracks,

    (SELECT COUNT(*) FROM playlists p
     WHERE p.user_id = u.user_id) AS playlists,

    (SELECT COUNT(*) FROM top_tracks tt
     WHERE tt.user_id = u.user_id
       AND tt.time_range = 'medium_term') AS top_tracks,

    (SELECT COUNT(*) FROM top_artists ta
     WHERE ta.user_id = u.user_id
       AND ta.time_range = 'medium_term') AS top_artists

FROM users u;





-- Recently Played Summary

SELECT
    u.display_name,
    COUNT(*) AS recent_streams,
    COUNT(DISTINCT rp.track_id) AS unique_tracks
FROM users u
JOIN recently_played rp
    ON u.user_id = rp.user_id
GROUP BY
    u.user_id,
    u.display_name;





-- Saved Library Size

SELECT
    u.display_name,
    COUNT(st.track_id) AS saved_tracks,
    COUNT(DISTINCT ta.artist_id) AS unique_artists,
    COUNT(DISTINCT ag.genre_name) AS unique_genres
FROM users u
LEFT JOIN saved_tracks st
    ON u.user_id = st.user_id
LEFT JOIN track_artists ta
    ON st.track_id = ta.track_id
   AND ta.position = 0
LEFT JOIN artist_genres ag
    ON ta.artist_id = ag.artist_id
GROUP BY
    u.user_id,
    u.display_name;




-- Playlist Summary

SELECT
    user_id,
    COUNT(*) AS playlists,
    SUM(track_count) AS total_playlist_tracks,
    ROUND(AVG(track_count),1) AS average_playlist_size,
    MAX(track_count) AS largest_playlist,
    MIN(track_count) AS smallest_playlist
FROM playlists
GROUP BY user_id;





-- Profile Completeness

SELECT
    display_name,

    CASE
        WHEN profile_image_url IS NULL THEN 'No'
        ELSE 'Yes'
    END AS has_profile_picture,

    CASE
        WHEN email IS NULL THEN 'No'
        ELSE 'Yes'
    END AS email_available,

    followers
FROM users;





SELECT
    u.display_name,
    u.country,
    u.followers,

    (SELECT COUNT(*)
     FROM playlists p
     WHERE p.user_id=u.user_id) AS playlists,

    (SELECT COUNT(*)
     FROM saved_tracks st
     WHERE st.user_id=u.user_id) AS saved_tracks,

    (SELECT COUNT(*)
     FROM recently_played rp
     WHERE rp.user_id=u.user_id) AS recent_streams

FROM users u;