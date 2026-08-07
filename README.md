# Spotify-Metro

A personal Spotify listening dashboard. Log in with Spotify, pull your listening
data into MySQL, and browse it across a set of themed dashboard pages
(Artists, Genres, Listening Activity, Playlists).

## Status

This is a working prototype, not a finished product. In particular:

- Logging in via the website fetches
  live data from Spotify for the main dashboard cards, but the deeper pages
  (Artists, Genres, Activity, Playlists) read from MySQL — which only gets
  populated when you manually run `spotify.py` +
  `mysql_connector.py`. Until those two flows are wired together, MySQL data
  can go stale even while you keep using the site. See **Known limitations**
  below.
- **Two placeholder videos and two placeholder images** are expected in
  `static/videos/` and `static/images/` 
- Not deployed anywhere yet — this only runs locally.

## Requirements

- Python 3.10+
- MySQL Server (locally or remote)
- A Spotify Developer app ([developer.spotify.com/dashboard](https://developer.spotify.com/dashboard))
- `uv` (or plain `pip`) for installing dependencies

## Setup

### 1. Install dependencies

```bash
uv pip install -r requirements.txt
```

### 2. Configure environment variables

Copy the example file and fill in real values:

```bash
cp .env.example .env
```

You'll need:

| Variable | Where to get it |
|---|---|
| `FLASK_SECRET_KEY` | Any random string |
| `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` | Your app in the Spotify Developer Dashboard |
| `SPOTIFY_REDIRECT_URI` | `http://127.0.0.1:5000/callback` — must be added **exactly** to your Spotify app's Redirect URIs list too, or login will fail with `redirect_uri: Not matching configuration` |
| `MYSQL_HOST` / `MYSQL_PORT` / `MYSQL_USER` / `MYSQL_PASSWORD` / `MYSQL_DATABASE` | Your local or remote MySQL instance |

### 3. Create the database schema

```bash
mysql -u root -p < schema.sql
```
(PowerShell users: `Get-Content schema.sql | mysql -u root -p`)

### 4. Populate MySQL with your listening data

```bash
uv run python spotify.py
uv run python mysql_connector.py
```

This fetches your Spotify data (top tracks/artists, saved tracks, playlists,
recently played) and loads it into the MySQL tables defined in `schema.sql`.
**Re-run this any time you want fresher data** — see Known limitations.

### 5. Add the placeholder media

- `static/videos/video1.mp4`, `video2.mp4`, `background.mp4`
- `static/images/genre.jpg`, `playlist.jpg`, `activity_left.jpg`, `activity_right.jpg`

(exact expected filenames are listed in the README.txt inside each folder)

### 6. Run the app

```bash
uv run python app.py
```

Visit `http://127.0.0.1:5000`.

## Project structure

```
app.py                      Flask routes, SQL queries, DB connection helper
spotify.py                  Pulls data from the Spotify API for one user
mysql_connector.py          Loads a collected JSON dump into MySQL
schema.sql                  MySQL table definitions
artist_queries.sql          Reference copy of the Artists page's SQL, with
                             comments explaining fixes made to the originals

templates/
    base.html                Shared layout
    index.html               Landing / login page
    dashboard.html            Main hub — 4 cards + KPIs (live Spotify data)
    artists.html              Taste archetype, stability, top artists, loyalty tiers
    genres.html                Genre diversity, weighted score, Aura, venn diagram
    activity.html              Time-of-day / weekday / repeat-rate histograms
    playlists.html             Curation sources, genre-diversity radar, mood

static/
    css/style.css             All styling
    videos/, images/          Placeholder media (see each folder's README.txt)
```

## Known limitations

- **`recently_played` is a snapshot, not a history.** Spotify's API only ever
  returns your last ~50 plays per request. Anything relying on this table
  (Stability chart, Listening Activity histograms, repeat-rate metrics) only
  becomes meaningful once `collect_spotify_data.py` has been run repeatedly
  over time — e.g. a daily scheduled job — so the table actually accumulates
  history rather than getting overwritten with the same recent snapshot.
- **MySQL data goes stale.** The live login flow doesn't call the loader
  automatically. Re-run step 4 manually to refresh, or wire `/callback` to
  call `load_data()` on every login (not yet implemented).
- **Spotify's Nov 2024 API changes** removed access to Audio Features,
  Audio Analysis, Recommendations, and Related Artists for apps created
  after that date. "Mood" on the Playlists page intentionally does **not**
  use audio features (valence/energy) — it reuses the genre-count-based
  `playlist_vibe_type` bucketing instead, since audio features may not be
  available depending on when your app was created.
- **Publishing publicly** requires applying to Spotify for Extended Quota
  Mode — Development Mode apps are capped at a handful of authorized users.

## Tech stack

Flask · Spotipy · MySQL · Chart.js (via CDN) · vanilla CSS (no framework)
