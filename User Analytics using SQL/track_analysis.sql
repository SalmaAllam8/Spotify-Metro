SELECT
    COUNT(*) AS streams,

    MIN(played_at) AS first_play,

    MAX(played_at) AS last_play,

    TIMESTAMPDIFF(
        DAY,
        MIN(played_at),
        MAX(played_at)
    ) AS coverage_days
FROM recently_played;




SELECT
    COUNT(*) AS streams,
    COUNT(DISTINCT track_id) AS unique_tracks,
    concat(
    ROUND(
        COUNT(DISTINCT track_id)/COUNT(*)*100,
        2
    ), "%")AS uniqueness_percentage
FROM recently_played;








