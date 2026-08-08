# 🎧 Spotify Listening Analytics

A personal Spotify analytics project that transforms Spotify listening data into a structured relational database and uses SQL to uncover patterns in listening behaviour, music taste, artist loyalty, genre diversity, playlist curation, and mainstream exposure.

The project combines **Spotify API data collection, relational data modelling, SQL analytics, and an interactive web dashboard** designed around a Spotify-inspired visual style.

---

## 📌 Project Overview

The goal of this project is to go beyond simply showing "top songs" and instead answer questions such as:

- What music do I listen to the most?
- Which artists are consistently present in my listening history?
- How repetitive is my listening behaviour?
- What genres define my music taste?
- Which genres are stable across different time periods?
- Am I discovering new artists or returning to familiar ones?
- How mainstream or niche is my music taste?
- How diverse are my playlists?
- Where does most of my listening come from?
- When do I listen to music the most?

The analysis is divided into four main areas:

1. **Genres**
2. **Artists**
3. **Playlists**
4. **Listening Activity**

A separate overview page summarizes the most important insights.

---

# 🗄️ Spotify Data Model

The Spotify data was organized into a relational database using **MySQL**.

The goal of the data model is to separate different types of Spotify information into logical tables while maintaining relationships between users, artists, tracks, playlists, and listening activity.

---

## 🧩 Database Structure

The database is divided into several main entities:

- Users
- Artists
- Tracks
-  Albums
-  Recently Played
- Saved Tracks
- Top Tracks
- Top Artists
- Artist Genres
- Track Artists
- Playlists
- Playlist Tracks

The model uses primary keys and foreign keys to connect these entities and avoid unnecessary duplication.

---

##  Entity Relationship Overview 

*this one was thought thoroughly made using drawdb*

<img width="4608" height="2620" alt="Untitled diagram_2026-07-27T00_58_52 477Z" src="https://github.com/user-attachments/assets/4a2fa93f-3ff1-47c1-a119-35dbbe0bb0e0" />
*this one was enhanced by AI for better representation and analysis*

<img width="1567" height="1004" alt="image" src="https://github.com/user-attachments/assets/93b0320d-0cb4-443f-8bb0-73bfe145d8d7" />


# Analytical Layers

The data model supports four main analytical areas:

---

###  Artist Analysis

**Tables Used:**
* `artists`
* `top_artists`
* `track_artists`
* `recently_played`

**Analytical Scope:**
* **Favorite Artists:** Identify overall top-streamed and top-ranked artists.
* **Artist Loyalty:** Track repeating engagement over extended time periods.
* **Rank Evolution:** Measure shifts in short-term, medium-term, and long-term artist preferences.
* **Artist Concentration:** Calculate how heavily listening time is concentrated among top artists.
* **Mainstream Exposure:** Analyze artist popularity scores and mainstream reach.

---

### Genre Analysis

**Tables Used:**
* `artist_genres`
* `track_artists`
* `top_tracks`
* `artists`

**Analytical Scope:**
* **Favorite Genres:** Determine top-ranking music genres based on listening volume.
* **Genre Diversity:** Evaluate the range and variety of distinct genres consumed.
* **Genre Overlap:** Uncover relationships and cross-genre listening patterns.
* **Genre Evolution:** Observe changes in genre preferences over time.
* **Weighted Genre Presence:** Measure genre representation weighted by track and artist frequencies.

---

###  Listening Activity

**Tables Used:**
* `recently_played`
* `tracks`

**Analytical Scope:**
* **Listening Time & Hours:** Quantify overall playback duration and peak activity hours.
* **Listening Days:** Map listening habits across days of the week and dates.
* **Repeat Rate:** Measure how frequently tracks or artists are replayed.
* **Single vs. Repeated Listening:** Distinguish between one-off streams and repeat favorites.
* **Heavy Rotation:** Identify tracks currently in continuous high play counts.
* **Monthly Listening Behavior:** Track monthly listening trends and fluctuations.

---

### 📋 Playlist Analysis

**Tables Used:**
* `playlists`
* `playlist_tracks`
* `tracks`
* `track_artists`
* `artist_genres`

**Analytical Scope:**
* **Playlist Size:** Evaluate total tracks and overall duration per playlist.
* **Artist & Genre Diversity:** Measure artist and genre variance within individual playlists.
* **Playlist Vibe:** Infer overall tone, tempo, or aesthetic profile based on genre composition.
* **Curation Source:** Distinguish between user-curated, algorithmic, and external playlists.
* **Personal vs. External Playlists:** Compare engagement metrics across self-created vs. followed playlists.

---

##  Data Modelling Principles

The database adheres to key relational database design principles:

* **Primary Keys:** Every entity is uniquely identified across all tables.
* **Foreign Keys:** Enforce relational integrity between related entities.
* **Junction Tables:** Effectively resolve many-to-many relationships (e.g., track-to-artist, track-to-playlist, artist-to-genre).
* **Entity Separation:** Artist and genre data are normalized into distinct tables to eliminate redundancy.
* **Event Separation:** Discrete listening events (`recently_played`) are stored independently from static track metadata.
* **Explicit Time Horizons:** Short-term, medium-term, and long-term Spotify ranking windows are explicitly defined to track temporal shifts.

> **Note:** The model strictly separates raw Spotify ingestion data from analytical calculations, enabling SQL queries to derive complex metrics dynamically without mutating underlying datasets.
##  Key Analytical Questions

This project analyses personal listening habits, artist affinity, genre shifts, and curation patterns across several core dimensions:

---

###  Listening Behaviour
* **Timing Patterns:** When do I listen to music most frequently throughout the day or week?
* **Volume & Duration:** How much total music do I consume over given time horizons?
* **Repeat Rate:** Do I heavily replay specific tracks, or favour broad variety?

---

### 🎤 Artist Preferences
* **Core Artists:** Which artists maintain consistent, long-term importance in my listening history?
* **Rising Favourites:** Which artists are rapidly becoming more prominent in recent activity?
* **Declining Interest:** Which previously top-ranked artists have faded from recent rotation?

---

### 🎶 Genre Preferences
* **Core Identity:** What primary genres define my overall musical taste?
* **Persistence & Trends:** Which genres remain persistent over time versus those that are newly emerging?
* **Taste Diversity:** How diverse is my genre distribution across different listening windows?

---

### 🌐 Mainstream Exposure
* **Popularity Index:** How mainstream or niche are the track and artist popularity scores across my library?
* **Preference Profile:** Is my overall listening profile predominantly mainstream, balanced, or niche?

---

### 📋 Playlist Curation
* **Playlist Variance:** How diverse are my saved playlists in terms of tracks, artists, and genres?
* **Curation Origin:** Do I primarily curate my own playlists, or rely on algorithmic/external recommendations?
* **Library Composition:** How much of my library is self-created versus followed from Spotify or other users?

---
## ⚠️ Important Limitations

This analysis relies on Spotify API data and custom methodologies, which introduce specific analytical constraints:

---

### ⏱️ Temporal & Data Window Limitations
* **Limited Event Window:** The `recently_played` dataset captures a rolling window of discrete listening events rather than a full, lifetime playback history.
* **Predefined Time Horizons:** Short-term, medium-term, and long-term ranking windows are defined strictly by Spotify's API specifications rather than custom rolling periods.

---

### 🏷️ Metadata & Attribute Constraints
* **Artist-Level Genre Mapping:** Genre designations are inherited from Spotify’s artist-level metadata, meaning individual tracks may not strictly map to every assigned genre tag.
* **Popularity Index Nuance:** Popularity scores reflect Spotify's dynamic internal metric, serving as a proxy for current mainstream reach rather than an absolute measure of musical quality.


