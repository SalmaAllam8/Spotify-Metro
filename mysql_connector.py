import mysql.connector 
import json
import os

conn = mysql.connector.connect(
    host='127.0.0.1',
    port= '3306',
    password = '1234',
    user='root'
   )


with open('recent_tracks.json') as json_file:
    tracks = json.load(json_file)

cursor = conn.cursor()

for track in tracks:
    sql = """INSERT INTO yourhistory.tracks (name_, artist,genres, album, duration_ms) 
             VALUES (%s, %s, %s, %s,%s)"""
    values = (
        track['name'],
        track['artist'],
        track['genres'],
        track['album'],
        track['duration_ms']
    )
    cursor.execute(sql, values)

conn.commit()
cursor.close()
conn.close()
os.remove("recent_tracks.json")
