# Loyality


SELECT
    a.artist_id,
    a.name AS artist_name,

    -- Peak rank in short vs. long term
    MAX(CASE WHEN ta.time_range = 'short_term' THEN ta.rank_pos END) AS short_term_rank,
    MAX(CASE WHEN ta.time_range = 'medium_term' THEN ta.rank_pos END) AS medium_term_rank,
    MAX(CASE WHEN ta.time_range = 'long_term' THEN ta.rank_pos END) AS long_term_rank,

    -- Loyalty Categorization
    CASE
        WHEN SUM(CASE WHEN ta.time_range = 'short_term' THEN 1 ELSE 0 END) > 0
         AND SUM(CASE WHEN ta.time_range = 'long_term' THEN 1 ELSE 0 END) > 0
             THEN 'Core Loyalty (Present in both)'

        WHEN SUM(CASE WHEN ta.time_range = 'short_term' THEN 1 ELSE 0 END) > 0
         AND SUM(CASE WHEN ta.time_range = 'long_term' THEN 1 ELSE 0 END) = 0
             THEN 'Trending / New Discovery'

        WHEN SUM(CASE WHEN ta.time_range = 'short_term' THEN 1 ELSE 0 END) = 0
         AND SUM(CASE WHEN ta.time_range = 'long_term' THEN 1 ELSE 0 END) > 0
             THEN 'Legacy / Phased Out'

        ELSE 'Mid-Term Phase'
    END AS artist_loyalty_tier

FROM top_artists ta
JOIN artists a ON ta.artist_id = a.artist_id
GROUP BY a.artist_id, a.name
ORDER BY
    FIELD(artist_loyalty_tier, 'Core Loyalty (Present in both)', 'Trending / New Discovery', 'Legacy / Phased Out', 'Mid-Term Phase'),
    short_term_rank ASC,
    long_term_rank ASC;







SELECT
    a.artist_id,
    a.name AS artist_name,

    MIN(CASE WHEN ta.time_range='short_term'
        THEN ta.rank_pos END) AS short_rank,

    MIN(CASE WHEN ta.time_range='medium_term'
        THEN ta.rank_pos END) AS medium_rank,

    MIN(CASE WHEN ta.time_range='long_term'
        THEN ta.rank_pos END) AS long_rank,

    MAX(CASE WHEN ta.time_range='short_term'
        THEN 1 ELSE 0 END) AS in_short,

    MAX(CASE WHEN ta.time_range='medium_term'
        THEN 1 ELSE 0 END) AS in_medium,

    MAX(CASE WHEN ta.time_range='long_term'
        THEN 1 ELSE 0 END) AS in_long,

    (
        MAX(CASE WHEN ta.time_range='short_term' THEN 1 ELSE 0 END)
      + MAX(CASE WHEN ta.time_range='medium_term' THEN 1 ELSE 0 END)
      + MAX(CASE WHEN ta.time_range='long_term' THEN 1 ELSE 0 END)
    ) AS stability_score

FROM top_artists ta
JOIN artists a
ON ta.artist_id=a.artist_id

GROUP BY
a.artist_id,
a.name;



