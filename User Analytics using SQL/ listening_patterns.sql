
#Peak Listening Hours & Days

#hours
SELECT
    HOUR(played_at) AS hour_of_day,
    COUNT(*) AS plays
FROM recently_played
GROUP BY hour_of_day
ORDER BY plays DESC;



#days
SELECT
    DAYNAME(played_at) AS weekday,
    COUNT(*) AS plays
FROM recently_played
GROUP BY weekday
ORDER BY plays DESC;

#days_by_names
SELECT
    DAYNAME(played_at) AS weekday,
    HOUR(played_at) AS hour,
    COUNT(*) AS plays
FROM recently_played
GROUP BY weekday, hour;



#Repeat vs. Single-Listen
SELECT
    t.track_id,
    t.name AS track_name,
    a.name AS artist_name,
    COUNT(*) AS play_count,
    CASE
        WHEN COUNT(*) = 1 THEN 'Single Listen'
        ELSE 'Repeat Stream'
    END AS stream_category
FROM recently_played rp
JOIN tracks t ON rp.track_id = t.track_id
JOIN track_artists ta ON t.track_id = ta.track_id AND ta.position = 0
JOIN artists a ON ta.artist_id = a.artist_id
GROUP BY t.track_id, t.name, a.name
ORDER BY play_count DESC;



#repeats


SELECT
    t.track_id,
    t.name AS track_name,
    a.name AS artist_name,
    COUNT(*) AS play_count,
    CASE
        WHEN COUNT(*) = 1 THEN 'One-time Listen'
        WHEN COUNT(*) BETWEEN 2 AND 4 THEN 'Repeated'
        ELSE 'Heavy Rotation'
    END AS listening_category
FROM recently_played rp
JOIN tracks t
    ON rp.track_id = t.track_id
JOIN track_artists ta
    ON t.track_id = ta.track_id
    AND ta.position = 0
JOIN artists a
    ON ta.artist_id = a.artist_id
GROUP BY
    t.track_id,
    t.name,
    a.name
ORDER BY
    play_count DESC,
    track_name;



SELECT
    COUNT(*) AS total_plays,
    COUNT(DISTINCT track_id) AS unique_tracks,
    COUNT(*) - COUNT(DISTINCT track_id) AS repeated_plays,
    ROUND(
        (COUNT(*) - COUNT(DISTINCT track_id))
        / COUNT(*) * 100,
        2
    ) AS repeat_rate_percentage
FROM recently_played;





SELECT
    listening_category,
    COUNT(*) AS number_of_tracks
FROM (
    SELECT
        CASE
            WHEN COUNT(*) = 1 THEN 'One-time Listen'
            WHEN COUNT(*) BETWEEN 2 AND 4 THEN 'Repeated'
            ELSE 'Heavy Rotation'
        END AS listening_category
    FROM recently_played
    GROUP BY track_id
) AS categories
GROUP BY listening_category;




#Aggregate Total Listening Time Across Timeframes

SELECT
    DATE_FORMAT(rp.played_at,'%Y-%m') AS month,

    COUNT(*) AS streams,

    COUNT(DISTINCT rp.track_id) AS unique_tracks,

    ROUND(SUM(t.duration_ms)/60000,1) AS listening_minutes,

    ROUND(AVG(t.duration_ms)/60000,2) AS avg_track_minutes,

    MIN(rp.played_at) AS first_stream,

    MAX(rp.played_at) AS last_stream

FROM recently_played rp
JOIN tracks t
ON rp.track_id=t.track_id

GROUP BY month

ORDER BY month DESC;

