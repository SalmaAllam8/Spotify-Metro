-- ============================================================================
-- Queries for the "Your Favourite Artists" dashboard page.
-- All queries take %s as the current user's Spotify user_id.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Overall mainstream score + taste archetype (YOUR QUERY, fixed)
-- ----------------------------------------------------------------------------
-- Original bug: none structurally — it was already grouped by user_id.
-- Only change: added a WHERE so the app can ask for one user's row directly
-- instead of pulling the whole table and filtering in Python.
--
-- Judgment call kept as-is: a track/artist appearing in all 3 time ranges
-- gets averaged in 3 times (once per range) rather than once. That weights
-- the score toward artists you've stayed consistently into, which seems
-- like the right behavior for "taste archetype" — flagging it in case you
-- disagree and want it de-duplicated instead.

WITH top_track_stats AS (
    SELECT tt.user_id, ROUND(AVG(t.popularity), 1) AS avg_top_track_popularity
    FROM top_tracks tt
    JOIN tracks t ON tt.track_id = t.track_id
    WHERE tt.user_id = %s
    GROUP BY tt.user_id
),
top_artist_stats AS (
    SELECT ta.user_id, ROUND(AVG(a.popularity), 1) AS avg_top_artist_popularity
    FROM top_artists ta
    JOIN artists a ON ta.artist_id = a.artist_id
    WHERE ta.user_id = %s
    GROUP BY ta.user_id
),
saved_track_stats AS (
    SELECT st.user_id, ROUND(AVG(t.popularity), 1) AS avg_saved_track_popularity
    FROM saved_tracks st
    JOIN tracks t ON st.track_id = t.track_id
    WHERE st.user_id = %s
    GROUP BY st.user_id
)
SELECT
    u.user_id,
    u.display_name,
    tts.avg_top_track_popularity,
    tas.avg_top_artist_popularity,
    sts.avg_saved_track_popularity,
    ROUND((
        COALESCE(tts.avg_top_track_popularity, 0) +
        COALESCE(tas.avg_top_artist_popularity, 0) +
        COALESCE(sts.avg_saved_track_popularity, 0)
    ) / 3, 1) AS overall_mainstream_score,
    CASE
        WHEN ((COALESCE(tts.avg_top_track_popularity, 0) + COALESCE(tas.avg_top_artist_popularity, 0) + COALESCE(sts.avg_saved_track_popularity, 0)) / 3) >= 75
            THEN 'Chart Hopper (Extremely Mainstream)'
        WHEN ((COALESCE(tts.avg_top_track_popularity, 0) + COALESCE(tas.avg_top_artist_popularity, 0) + COALESCE(sts.avg_saved_track_popularity, 0)) / 3) >= 55
            THEN 'Balanced Curation (Mainstream & Indie)'
        WHEN ((COALESCE(tts.avg_top_track_popularity, 0) + COALESCE(tas.avg_top_artist_popularity, 0) + COALESCE(sts.avg_saved_track_popularity, 0)) / 3) >= 35
            THEN 'Underground & Niche Explorer'
        ELSE 'Deep Underground / Obscure'
    END AS taste_archetype
FROM users u
LEFT JOIN top_track_stats tts ON u.user_id = tts.user_id
LEFT JOIN top_artist_stats tas ON u.user_id = tas.user_id
LEFT JOIN saved_track_stats sts ON u.user_id = sts.user_id
WHERE u.user_id = %s;


-- ----------------------------------------------------------------------------
-- 2. Saved-track popularity tiers (YOUR QUERY, fixed)
-- ----------------------------------------------------------------------------
-- Bug: no WHERE user_id at all — this was mixing every user's saved tracks
-- together. Same class of bug we fixed in popularity_tiers_query.sql earlier.
-- Not used on the Artists page itself (the page's donut chart uses artist
-- popularity, query #4 below) — kept here fixed for whichever page ends up
-- showing saved-track tiers.

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
WHERE st.user_id = %s
GROUP BY popularity_tier
ORDER BY avg_tier_popularity DESC;


-- ----------------------------------------------------------------------------
-- 3. Artist loyalty tiers across time ranges (YOUR QUERY, fixed)
-- ----------------------------------------------------------------------------
-- Bug: this is the more serious one. GROUP BY was only (artist_id, name),
-- with no user_id anywhere — so if two different users both had the same
-- artist in their top_artists, this query silently merged their rank data
-- into one row. Fixed by adding user_id to the SELECT, GROUP BY, and a
-- WHERE clause. Powers the 4 bottom cards (Core Loyalty / Trending /
-- Legacy / Mid-Term) — "top 5 per category" is applied in Python after
-- this query returns everything, rather than in SQL.

SELECT
    ta.user_id,
    a.artist_id,
    a.name AS artist_name,
    a.image_url,
    MAX(CASE WHEN ta.time_range = 'short_term' THEN ta.rank_pos END) AS short_term_rank,
    MAX(CASE WHEN ta.time_range = 'medium_term' THEN ta.rank_pos END) AS medium_term_rank,
    MAX(CASE WHEN ta.time_range = 'long_term' THEN ta.rank_pos END) AS long_term_rank,
    CASE
        WHEN SUM(CASE WHEN ta.time_range = 'short_term' THEN 1 ELSE 0 END) > 0
         AND SUM(CASE WHEN ta.time_range = 'long_term' THEN 1 ELSE 0 END) > 0
            THEN 'Core Loyalty'
        WHEN SUM(CASE WHEN ta.time_range = 'short_term' THEN 1 ELSE 0 END) > 0
         AND SUM(CASE WHEN ta.time_range = 'long_term' THEN 1 ELSE 0 END) = 0
            THEN 'Trending'
        WHEN SUM(CASE WHEN ta.time_range = 'short_term' THEN 1 ELSE 0 END) = 0
         AND SUM(CASE WHEN ta.time_range = 'long_term' THEN 1 ELSE 0 END) > 0
            THEN 'Legacy'
        ELSE 'Mid-Term'
    END AS artist_loyalty_tier
FROM top_artists ta
JOIN artists a ON ta.artist_id = a.artist_id
WHERE ta.user_id = %s
GROUP BY ta.user_id, a.artist_id, a.name, a.image_url
ORDER BY
    FIELD(artist_loyalty_tier, 'Core Loyalty', 'Trending', 'Legacy', 'Mid-Term'),
    short_term_rank ASC,
    long_term_rank ASC;


-- ----------------------------------------------------------------------------
-- 4. NEW — Artist popularity donut (Mainstream / Mid-tier / Niche)
-- ----------------------------------------------------------------------------
-- Not one of your 3 queries — the wireframe's donut chart is artist-based
-- ("percentage of the popularity of each artist"), so this adapts the same
-- tier logic from query #2 but on top_artists instead of saved_tracks.
-- DISTINCT artist_id avoids triple-counting an artist that appears in all
-- 3 time ranges.

SELECT
    CASE
        WHEN a.popularity >= 70 THEN 'Mainstream'
        WHEN a.popularity BETWEEN 40 AND 69 THEN 'Mid-tier'
        ELSE 'Niche'
    END AS popularity_tier,
    COUNT(DISTINCT a.artist_id) AS artist_count
FROM top_artists ta
JOIN artists a ON ta.artist_id = a.artist_id
WHERE ta.user_id = %s
GROUP BY popularity_tier;


-- ----------------------------------------------------------------------------
-- 5. NEW — Stability histogram (Core / Returning / One-time)
-- ----------------------------------------------------------------------------
-- Not one of your 3 queries either. This is genuinely different from #3:
-- #3 measures presence across time-range *snapshots* (short/medium/long
-- term top lists). This measures actual play *frequency* from your
-- recently_played history, bucketed by how many times you've played that
-- artist's tracks. Thresholds (1 / 2-4 / 5+) are a starting point —
-- adjust freely once you see real numbers.
--
-- Important: recently_played only ever holds Spotify's last ~50 plays per
-- API call. This metric only becomes meaningful once collect_spotify_data.py
-- has been run repeatedly over time (e.g. a daily scheduled job) so the
-- table accumulates real history — a single one-off run won't have enough
-- data for "Core" to mean anything yet.

WITH artist_play_counts AS (
    SELECT ta_link.artist_id, COUNT(*) AS play_count
    FROM recently_played rp
    JOIN track_artists ta_link ON rp.track_id = ta_link.track_id AND ta_link.position = 0
    WHERE rp.user_id = %s
    GROUP BY ta_link.artist_id
)
SELECT
    CASE
        WHEN play_count = 1 THEN 'One-time'
        WHEN play_count BETWEEN 2 AND 4 THEN 'Returning'
        ELSE 'Core'
    END AS stability_tier,
    COUNT(*) AS artist_count
FROM artist_play_counts
GROUP BY stability_tier;
