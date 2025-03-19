import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.config.settings import settings
from src.database.models.movies import MovieModel
from src.database.populate import CSVDatabaseSeeder

# Создаем сессию для работы с базой данных
engine = create_engine(f"sqlite:///{settings.PATH_TO_DB}")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def populate_movies():
    db_session = SessionLocal()
    # Проверяем, пустая ли таблица movies
    if not db_session.query(MovieModel).first():  # Если в таблице нет фильмов
        print("Database is empty, seeding with CSV data...")
        seeder = CSVDatabaseSeeder(settings.PATH_TO_DATA_MOVIES_CSV, db_session)
        seeder.seed()  # Заполняем базу данных из CSV
        print("Seeding completed.")
    else:
        print("Database already populated, skipping seeding.")
    db_session.close()


if __name__ == "__main__":
    try:
        populate_movies()
    except Exception as e:
        print(f"An error occurred while populating the database: {e}")
        sys.exit(1)
