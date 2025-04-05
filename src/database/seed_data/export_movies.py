import csv
from sqlalchemy.orm import Session
from src.database.models.movies import MovieModel


def export_movies_to_csv(db_session: Session, file_path: str):
    movies = db_session.query(MovieModel).all()

    with open(file_path, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, delimiter=";")

        # names;year;time;imdb;votes;genre;description;stars;certification;gross;price;directors;meta_score
        writer.writerow(
            [
                "names",
                "year",
                "time",
                "imdb",
                "votes",
                "genres",
                "description",
                "stars",
                "certification",
                "gross",
                "price",
                "directors",
                "meta_score",
            ]
        )

        for movie in movies:
            movie_genres = ",".join([genre.name for genre in movie.genres])
            movie_stars = ",".join([star.name for star in movie.stars])
            movie_directors = ",".join([director.name for director in movie.directors])

            writer.writerow(
                [
                    movie.name,
                    movie.year,
                    movie.time,
                    movie.imdb,
                    movie.votes,
                    movie_genres,
                    movie.description,
                    movie_stars,
                    movie.certification.name,
                    movie.gross,
                    movie.price,
                    movie_directors,
                    movie.meta_score,
                ]
            )

    print(f"Movies have been exported to {file_path}")


if __name__ == "__main__":

    from src.database.session import (
        SessionLocal,
    )

    db_session = SessionLocal()

    file_path = "movies.csv"

    export_movies_to_csv(db_session, file_path)

    db_session.close()
