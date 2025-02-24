from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from src.schemas.examples.movies import (
    movie_item_schema_example,
    movie_list_response_schema_example,
    genre_schema_example,
    director_schema_example,
    star_schema_example,
    movie_detail_schema_example,
    movie_create_schema_example,
)


class MovieBaseSchema(BaseModel):
    uuid: str = Field(...)
    name: str = Field(..., max_length=255)
    year: int = Field(..., ge=1895)
    time: int = Field(..., ge=0)
    imdb: float = Field(..., ge=0, le=10)
    votes: int = Field(..., ge=0)
    meta_score: Optional[float] = Field(None, ge=0, le=100)
    gross: Optional[float] = Field(None)
    description: str
    price: float = Field(..., gt=0)
    certification_id: int = Field(..., gt=0)

    @field_validator("year")
    @classmethod
    def validate_date(cls, value):
        current_year = int(datetime.now().year)
        if value > current_year + 1:
            raise ValueError(f"The 'year' cannot be greater than {current_year + 1}.")
        return value


class MovieListItemSchema(BaseModel):
    id: int
    name: str
    year: int
    time: int
    imdb: float
    description: str
    price: float

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {"examples": [movie_item_schema_example]},
    }


class MovieListResponseSchema(BaseModel):
    movies: List[MovieListItemSchema]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {"examples": [movie_list_response_schema_example]},
    }


class GenreSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {"examples": [genre_schema_example]},
    }


class DirectorSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {"examples": [director_schema_example]},
    }


class StarSchema(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {"examples": [star_schema_example]},
    }


class MovieDetailSchema(MovieBaseSchema):
    id: int
    directors: List[DirectorSchema]
    stars: List[StarSchema]
    genres: List[GenreSchema]

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {"examples": [movie_detail_schema_example]},
    }


class MovieCreateSchema(BaseModel):
    name: str
    year: int = Field(..., ge=1895)
    time: int
    imdb: float = Field(..., ge=0, le=10)
    votes: int
    meta_score: Optional[float] = Field(None, ge=0, le=100)
    gross: Optional[float] = Field(None)
    description: str
    price: float = Field(..., gt=0)
    certification: str
    directors: List[str]
    genres: List[str]
    stars: List[str]

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {"examples": [movie_create_schema_example]},
    }

    @field_validator("directors", "genres", "stars", mode="before")
    @classmethod
    def normalize_list_fields(cls, value: List[str]) -> List[str]:
        return [item.title() for item in value]
