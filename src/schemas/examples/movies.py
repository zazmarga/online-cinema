movie_item_schema_example = {
    "id": 33,
    "uuid": "123e4567-e89b-12d3-a456-426614174000",
    "name": "The Swan Princess: A Royal Wedding",
    "year": 2020,
    "time": 70,
    "imdb": 7.8,
    "votes": 52,
    "meta_score": 88.0,  #  or None
    "gross": 12345678.90,  #  or None
    "description": "Princess Odette and Prince Derek are going to a wedding at Princess Mei Li and her beloved Chen. "
    "But evil forces are at stake and the wedding plans are tarnished and "
    "true love has difficult conditions.",
    "price": 5.99,
    "certification_id": 2,
}

movie_list_response_schema_example = {
    "movies": [movie_item_schema_example],
    "prev_page": "/movies/movies-list/?page=1&per_page=1",
    "next_page": "/movies/movies-list?page=3&per_page=1",
    "total_pages": 9933,
    "total_items": 9933,
}
