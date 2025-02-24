from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from src.schemas.examples.movies import (
    movie_item_schema_example,
    movie_list_response_schema_example,
)


class MovieBaseSchema(BaseModel):
    id: int
    uuid: str = Field(..., max_length=65)
    name: str = Field(..., max_length=255)
    year: int = Field(..., ge=1895)
    time: int = Field(..., ge=0)
    imdb: float = Field(..., ge=0)
    votes: int = Field(..., ge=0)
    meta_score: Optional[float] = Field(None, ge=0, le=100)
    gross: Optional[float] = Field(None)
    description: str
    price: float = Field(..., gt=0)
    certification_id: int = Field(..., gt=0)

    @field_validator("year")
    @classmethod
    def validate_date(cls, value):
        current_year = datetime.now().year
        if value.year > current_year + 1:
            raise ValueError(f"The 'year' cannot be greater than {current_year + 1}.")
        return value


class MovieListItemSchema(MovieBaseSchema):
    pass

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
