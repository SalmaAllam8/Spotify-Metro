SELECT
    p.playlist_id,
    p.name AS playlist_name,
    COUNT(DISTINCT pt.track_id) AS total_tracks,
    COUNT(DISTINCT ta.artist_id) AS unique_artists,
    COUNT(DISTINCT ag.genre_name) AS unique_genres,

    -- Artist Diversity Ratio (1.0 = Every single song is by a different artist)
    ROUND(COUNT(DISTINCT ta.artist_id) * 1.0 / NULLIF(COUNT(DISTINCT pt.track_id), 0), 2) AS artist_diversity_ratio,

    -- Genres per Track Ratio
    ROUND(COUNT(DISTINCT ag.genre_name) * 1.0 / NULLIF(COUNT(DISTINCT pt.track_id), 0), 2) AS genre_diversity_ratio,

    -- Eclecticism Bucket
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

GROUP BY p.playlist_id, p.name
ORDER BY unique_genres DESC;





SELECT
    p.user_id,

    -- Curation Origin
    CASE
        WHEN p.owner_id = p.user_id THEN 'Self-Curated (Owned)'
        WHEN LOWER(p.owner_id) IN ('spotify', 'spotifycharts') THEN 'Spotify Official / Editorial'
        ELSE 'External / Friend Curated'
    END AS curation_source,

    COUNT(DISTINCT p.playlist_id) AS playlist_count,
    SUM(p.track_count) AS total_tracks,
    ROUND(AVG(p.track_count), 1) AS avg_tracks_per_playlist,

    -- Percentage of total playlists in library
    ROUND(
        (COUNT(DISTINCT p.playlist_id) * 100.0) /
        (SELECT COUNT(*) FROM playlists),
        1
    ) AS pct_of_library_playlists

FROM playlists p
GROUP BY
    p.user_id,
    CASE
        WHEN p.owner_id = p.user_id THEN 'Self-Curated (Owned)'
        WHEN LOWER(p.owner_id) IN ('spotify', 'spotifycharts') THEN 'Spotify Official / Editorial'
        ELSE 'External / Friend Curated'
    END
ORDER BY playlist_count DESC;


