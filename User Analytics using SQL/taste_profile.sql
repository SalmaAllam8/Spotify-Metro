

WITH top_track_stats AS (
    SELECT
        tt.user_id,
        ROUND(AVG(t.popularity), 1) AS avg_top_track_popularity
    FROM top_tracks tt
    JOIN tracks t
        ON tt.track_id = t.track_id
    GROUP BY tt.user_id
),

top_artist_stats AS (
    SELECT
        ta.user_id,
        ROUND(AVG(a.popularity), 1) AS avg_top_artist_popularity
    FROM top_artists ta
    JOIN artists a
        ON ta.artist_id = a.artist_id
    GROUP BY ta.user_id
),

saved_track_stats AS (
    SELECT
        st.user_id,
        ROUND(AVG(t.popularity), 1) AS avg_saved_track_popularity
    FROM saved_tracks st
    JOIN tracks t
        ON st.track_id = t.track_id
    GROUP BY st.user_id
)

SELECT
    u.user_id,
    u.display_name,

    tts.avg_top_track_popularity,
    tas.avg_top_artist_popularity,
    sts.avg_saved_track_popularity,

    ROUND(
        (
            COALESCE(tts.avg_top_track_popularity, 0) +
            COALESCE(tas.avg_top_artist_popularity, 0) +
            COALESCE(sts.avg_saved_track_popularity, 0)
        ) / 3,
        1
    ) AS overall_mainstream_score,

    CASE
        WHEN (
            (
                COALESCE(tts.avg_top_track_popularity, 0) +
                COALESCE(tas.avg_top_artist_popularity, 0) +
                COALESCE(sts.avg_saved_track_popularity, 0)
            ) / 3
        ) >= 75 THEN 'Chart Hopper (Extremely Mainstream)'

        WHEN (
            (
                COALESCE(tts.avg_top_track_popularity, 0) +
                COALESCE(tas.avg_top_artist_popularity, 0) +
                COALESCE(sts.avg_saved_track_popularity, 0)
            ) / 3
        ) >= 55 THEN 'Balanced Curation (Mainstream & Indie)'

        WHEN (
            (
                COALESCE(tts.avg_top_track_popularity, 0) +
                COALESCE(tas.avg_top_artist_popularity, 0) +
                COALESCE(sts.avg_saved_track_popularity, 0)
            ) / 3
        ) >= 35 THEN 'Underground & Niche Explorer'

        ELSE 'Deep Underground / Obscure'

    END AS taste_archetype

FROM users u

LEFT JOIN top_track_stats tts
    ON u.user_id = tts.user_id

LEFT JOIN top_artist_stats tas
    ON u.user_id = tas.user_id

LEFT JOIN saved_track_stats sts
    ON u.user_id = sts.user_id;







(
    SELECT
        'Most Niche' AS category,
        t.name AS track_name,
        a.name AS artist_name,
        t.popularity
    FROM saved_tracks st
    JOIN tracks t ON st.track_id = t.track_id
    JOIN track_artists ta ON t.track_id = ta.track_id AND ta.position = 0
    JOIN artists a ON ta.artist_id = a.artist_id
    ORDER BY t.popularity ASC
    LIMIT 5
)
UNION ALL
(
    SELECT
        'Most Mainstream' AS category,
        t.name AS track_name,
        a.name AS artist_name,
        t.popularity
    FROM saved_tracks st
    JOIN tracks t ON st.track_id = t.track_id
    JOIN track_artists ta ON t.track_id = ta.track_id AND ta.position = 0
    JOIN artists a ON ta.artist_id = a.artist_id
    ORDER BY t.popularity DESC
    LIMIT 5
);





SELECT
    CASE
        WHEN t.popularity >= 70 THEN 'Mainstream / Hits (70-100)'
        WHEN t.popularity BETWEEN 40 AND 69 THEN 'Mid-Tier / Popular (40-69)'
        ELSE 'Underground / Niche (0-39)'
    END AS popularity_tier,

    COUNT(DISTINCT st.track_id) AS track_count,
    ROUND(AVG(t.popularity), 1) AS avg_tier_popularity,
    ROUND(SUM(t.duration_ms) / 3600000.0, 2) AS total_hours

FROM saved_tracks st
JOIN tracks t ON st.track_id = t.track_id

GROUP BY popularity_tier
ORDER BY avg_tier_popularity DESC;


