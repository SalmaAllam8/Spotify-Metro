import spotipy
from spotipy.oauth2 import SpotifyOAuth
import json
# Set up your credentials
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id='079cc4a1ad984de38b286a828f4aa103',
    client_secret='e6150d6a3c1a43568a18a96de0b52f67',
    redirect_uri='http://127.0.0.1:5000/'
))
recent_tracks = sp.current_user_recently_played(limit=50)


track_details = []

for item in recent_tracks['items']:
    track = item['track']
    artist_id = track['artists'][0]['id']
    artist_info = sp.artist(artist_id)
    first_genre = artist_info['genres'][0] if artist_info['genres'] else 'Unknown'

    track_info = {
        "name": track['name'],
        "artist": artist_info['name'],
        'genres': first_genre,
        "album": track['album']['name'],
        "duration_ms": track['duration_ms'],  
    }
    track_details.append(track_info)

with open('recent_tracks.json', 'w') as json_file:
    json.dump(track_details, json_file, indent=4)

