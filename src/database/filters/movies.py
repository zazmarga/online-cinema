from typing import Optional, List

from fastapi_filter.contrib.sqlalchemy import Filter
from pydantic import Field

from src.database.models.movies import MovieModel


class MovieFilter(Filter):
    name__ilike: Optional[str] = Field(
        None,
        alias="nameContains",
        description="Filter movies by name contains.. (case-insensitive)",
    )
    year__in: Optional[List[int]] = Field(
        None,
        alias="yearOfRelease",
        description="Filter movies by year/list(years) of release",
    )
    imdb__gte: Optional[float] = Field(
        None,
        alias="IMDbRatingFrom",
        description="Filter movies with IMDb rating greater than or equal to the specified value",
    )

    class Constants(Filter.Constants):
        model = MovieModel

    class Config:
        populate_by_name = True


def normalize_search_list(search_list: List[str]) -> List[str]:
    return [item.title() for item in search_list]
