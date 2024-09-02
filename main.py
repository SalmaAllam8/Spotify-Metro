from flask import Flask, render_template
from flask_mysqldb import MySQL


app = Flask(__name__)
app.config['MYSQL_HOST'] = '127.0.0.1'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '1234'
app.config['MYSQL_DB'] = 'yourhistory'

mysql = MySQL(app)


@app.route('/')
def display_results():
    
    cursor = mysql.connection.cursor()

    # SQL Queries
    queries = {
        "TOP 5 ARTISTS": """
            SELECT artist AS 'TOP 5 ARTISTS'
            FROM tracks
            GROUP BY artist
            ORDER BY COUNT(artist) DESC
            LIMIT 5;
        """,
        "TOP 5 SONGS": """
            SELECT name_ AS 'TOP 5 SONGS'
            FROM tracks
            GROUP BY name_
            ORDER BY COUNT(name_) DESC
            LIMIT 5;
        """,
        "TOP 5 GENRES": """
            SELECT genres AS 'TOP 5 GENRES'
            FROM tracks
            GROUP BY genres
            HAVING genres <> 'unknown'
            ORDER BY COUNT(genres) DESC
            LIMIT 5;
        """,
        "TOP 5 ALBUMS": """
            SELECT album AS 'TOP 5 ALBUMS'
            FROM tracks
            GROUP BY album
            ORDER BY COUNT(album) DESC
            LIMIT 5;
        """,
        "TOTAL LISTENING TIME": """
            SELECT SEC_TO_TIME(SUM(duration_ms) / 1000) AS 'Total Listening Time'
            FROM tracks;
        """
    }

    results = {}

    # Execute each query and store the result
    for title, query in queries.items():
        cursor.execute(query)
        results[title] = cursor.fetchall()

    cursor.close()
    

    # Render the results to the HTML template
    return render_template('index.html', results=results)

if __name__ == '__main__':
    app.run(debug=True)

