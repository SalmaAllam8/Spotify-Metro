CREATE  table yourhistory.tracks (
    id INT AUTO_INCREMENT PRIMARY KEY,
	name_ VARCHAR(255),
    artist VARCHAR(255),
    genres VARCHAR(255),
    album VARCHAR(255),
    duration_ms INT
);

select *
from  yourhistory.tracks;

select artist  'TOP 5 ARTISITS'
from yourhistory.tracks
group by artist
order by  count(artist) desc
limit 5 ;

select name_  as 'TOP 5 songs'
from yourhistory.tracks
group by name_
order by  count(name_) desc
limit 5 ;

select genres as 'TOP 5 genres'
from yourhistory.tracks 
group by genres 
having genres <> 'unknown'
order by count( genres) desc
limit 5; 

select album as 'TOP 5 albums'
from yourhistory.tracks
group by album
order by count(album)
limit 5;

SELECT 
    SEC_TO_TIME(SUM(duration_ms) / 1000) AS 'Total listening'
FROM 
    yourhistory.tracks;