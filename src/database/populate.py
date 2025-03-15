import uuid

import pandas as pd
from sqlalchemy import insert
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from tqdm import tqdm

from src.database.models.accounts import UserGroupModel, UserGroupEnum
from src.database.models.movies import (
    MovieModel,
    GenreModel,
    StarModel,
    DirectorModel,
    CertificationModel,
    MoviesGenresModel,
    StarsMoviesModel,
    DirectorsMoviesModel,
)
from src.tests.conftest import test_settings, db_session


class CSVDatabaseSeeder:
    def __init__(self, csv_file_path: str, db_session: Session):
        self._csv_file_path = csv_file_path
        self._db_session = db_session

    def is_db_populated(self) -> bool:
        return self._db_session.query(MovieModel).first() is not None

    def _seed_user_groups(self):
        """
        Seed UserGroup table with values from UserGroupEnum if the table is empty.
        """
        existing_groups = self._db_session.query(UserGroupModel).count()
        if existing_groups == 0:
            groups = [{"name": group.value} for group in UserGroupEnum]
            self._db_session.execute(insert(UserGroupModel).values(groups))
            self._db_session.flush()
            print("User groups seeded successfully.")

    def _preprocess_csv(self):
        data = pd.read_csv(
            self._csv_file_path, delimiter=";"
        )  #  quoting=csv.QUOTE_NONE
        # print(data.columns)
        # print(data.head())
        data = data.drop_duplicates(subset=["names", "year", "time"], keep="first")

        data["stars"] = data["stars"].fillna("Unknown")
        data["stars"] = data["stars"].str.replace(r"\s+", "", regex=True)
        data["stars"] = data["stars"].apply(
            lambda stars: (
                ",".join(sorted(set(stars.split(",")))) if stars != "Unknown" else stars
            )
        )
        data["genre"] = data["genre"].fillna("Unknown")
        data["genre"] = data["genre"].str.replace("\u00a0", "", regex=True)

        print("Preprocessing csv file")

        data.to_csv(self._csv_file_path, index=False, sep=";")
        print(f"File saved to {self._csv_file_path}")
        return data

    def _get_or_create_bulk(self, model, items: list, unique_field: str):
        existing = (
            self._db_session.query(model)
            .filter(getattr(model, unique_field).in_(items))
            .all()
        )
        existing_dict = {getattr(item, unique_field): item for item in existing}

        new_items = [item for item in items if item not in existing_dict]
        new_records = [{unique_field: item} for item in new_items]

        if new_records:
            self._db_session.execute(insert(model).values(new_records))
            self._db_session.flush()

            newly_inserted = (
                self._db_session.query(model)
                .filter(getattr(model, unique_field).in_(new_items))
                .all()
            )
            existing_dict.update(
                {getattr(item, unique_field): item for item in newly_inserted}
            )

        return existing_dict

    def seed(self):
        try:
            if self._db_session.in_transaction():
                print("Rolling back existing transaction.")
                self._db_session.rollback()

            self._seed_user_groups()

            data = self._preprocess_csv()

            certifications = data["certification"].unique()
            genres = set(
                genre.strip()
                for genres in data["genre"].dropna()
                for genre in genres.split(",")
                if genre.strip()
            )
            stars = set(
                star.strip()
                for stars in data["stars"].dropna()
                for star in stars.split(",")
                if star.strip()
            )
            directors = set(
                director.strip()
                for directors in data["directors"].dropna()
                for director in directors.split(",")
                if director.strip()
            )

            certification_map = self._get_or_create_bulk(
                CertificationModel, certifications, "name"
            )
            director_map = self._get_or_create_bulk(
                DirectorModel, list(directors), "name"
            )
            genre_map = self._get_or_create_bulk(GenreModel, list(genres), "name")
            star_map = self._get_or_create_bulk(StarModel, list(stars), "name")

            movies_data = []
            movie_genres_data = []
            movie_stars_data = []
            movie_directors_data = []

            for _, row in tqdm(
                data.iterrows(), total=data.shape[0], desc="Processing movies"
            ):
                certification = certification_map[row["certification"]]

                movie = {
                    "uuid": str(uuid.uuid4()),
                    "name": row["names"],
                    "year": int(row["year"]),
                    "time": int(row["time"]),
                    "imdb": float(row["imdb"]),
                    "votes": int(row["votes"]),
                    "meta_score": (
                        float(row["meta_score"]) if row["meta_score"] else None
                    ),
                    "gross": float(row["gross"]) if row["gross"] else None,
                    "description": row["description"],
                    "price": float(row["price"]),
                    "certification_id": certification.id,
                }
                movies_data.append(movie)

            result = self._db_session.execute(
                insert(MovieModel).returning(MovieModel.id), movies_data
            )
            movie_ids = result.scalars().all()

            for i, (_, row) in enumerate(
                tqdm(
                    data.iterrows(), total=data.shape[0], desc="Processing associations"
                )
            ):
                movie_id = movie_ids[i]

                for genre_name in row["genre"].split(","):
                    if genre_name.strip():
                        genre = genre_map[genre_name.strip()]
                        movie_genres_data.append(
                            {"movie_id": movie_id, "genre_id": genre.id}
                        )

                for star_name in row["stars"].split(","):
                    if star_name.strip():
                        star = star_map[star_name.strip()]
                        movie_stars_data.append(
                            {"movie_id": movie_id, "star_id": star.id}
                        )

                for director_name in row["directors"].split(","):
                    if director_name.strip():
                        director = director_map[director_name.strip()]
                        movie_directors_data.append(
                            {"movie_id": movie_id, "director_id": director.id}
                        )

            self._db_session.execute(
                insert(MoviesGenresModel).values(movie_genres_data)
            )
            self._db_session.execute(insert(StarsMoviesModel).values(movie_stars_data))
            self._db_session.execute(
                insert(DirectorsMoviesModel).values(movie_directors_data)
            )
            self._db_session.commit()

        except SQLAlchemyError as e:
            print(f"An error occurred: {e}")
            raise
        except Exception as e:
            print(f"Unexpected error: {e}")
            raise


def main():
    seeder = CSVDatabaseSeeder(test_settings.PATH_TO_MOVIES_CSV, db_session)

    if not seeder.is_db_populated():
        try:
            seeder.seed()
            print("Database seeding completed successfully.")
        except Exception as e:
            print(f"Failed to seed the database: {e}")
    else:
        print("Database is already populated. Skipping seeding.")


if __name__ == "__main__":
    main()
