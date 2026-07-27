
#Taste Evolution & Preference Drift


SELECT
    ag.genre_name,
    COUNT(CASE WHEN tt.time_range = 'short_term' THEN 1 END) AS short_term_occurrences,
    COUNT(CASE WHEN tt.time_range = 'long_term' THEN 1 END) AS long_term_occurrences,
    COUNT(*) AS total_occurrences
FROM top_tracks tt
JOIN track_artists ta ON tt.track_id = ta.track_id
JOIN artist_genres ag ON ta.artist_id = ag.artist_id
GROUP BY ag.genre_name
ORDER BY short_term_occurrences DESC, long_term_occurrences DESC;






SELECT
    ag.genre_name,

    COUNT(DISTINCT CASE
        WHEN tt.time_range = 'short_term'
        THEN tt.track_id
    END) AS short_term,

    COUNT(DISTINCT CASE
        WHEN tt.time_range = 'medium_term'
        THEN tt.track_id
    END) AS medium_term,

    COUNT(DISTINCT CASE
        WHEN tt.time_range = 'long_term'
        THEN tt.track_id
    END) AS long_term,

    COUNT(DISTINCT tt.track_id) AS total_tracks,

    COUNT(DISTINCT CASE
        WHEN tt.time_range = 'short_term'
        THEN tt.track_id
    END)
    -
    COUNT(DISTINCT CASE
        WHEN tt.time_range = 'long_term'
        THEN tt.track_id
    END) AS trend

FROM top_tracks tt

JOIN track_artists ta
    ON tt.track_id = ta.track_id
    AND ta.position = 0

JOIN artist_genres ag
    ON ta.artist_id = ag.artist_id

GROUP BY ag.genre_name

ORDER BY total_tracks DESC;





SELECT
    tt.time_range,
    ag.genre_name,
    COUNT(DISTINCT tt.track_id) AS track_count,
    SUM(51 - tt.rank_pos) AS weighted_genre_score,
    ROUND(AVG(tt.rank_pos), 2) AS average_rank
FROM top_tracks tt
JOIN track_artists ta
    ON tt.track_id = ta.track_id
    AND ta.position = 0
JOIN artist_genres ag
    ON ta.artist_id = ag.artist_id
WHERE tt.time_range IN ('short_term', 'long_term')
GROUP BY tt.time_range, ag.genre_name
ORDER BY tt.time_range, weighted_genre_score DESC;


