movie_item_schema_example = {
    "id": 33,
    "name": "The Godfather",
    "year": 1972,
    "time": 175,
    "imdb": 9.2,
    "description": "The aging patriarch of an organized crime dynasty transfers control "
    "of his clandestine empire to his reluctant son.",
    "price": 9.99,
}

movie_list_response_schema_example = {
    "movies": [movie_item_schema_example],
    "prev_page": "/movies/?page=1&per_page=1",
    "next_page": "/movies/?page=3&per_page=1",
    "total_pages": 930,
    "total_items": 930,
}

genre_schema_example = {"id": 1, "genre": "Gangster"}

director_schema_example = {"id": 1, "name": "Francis Ford Coppola"}

star_schema_example = {"id": 1, "name": "Al Pacino"}

movie_detail_schema_example = {
    **movie_item_schema_example,
    "uuid": "123e4567-e89b-12d3-a456-426614174000",
    "votes": 73,
    "meta_score": 99.0,  #  or None
    "gross": 250000000.00,  #  or None
    "certification_id": 2,
    "directors": [director_schema_example],
    "stars": [star_schema_example],
    "genres": [genre_schema_example],
}

movie_create_schema_example = {
    "name": "The Godfather",
    "year": 1972,
    "time": 175,
    "imdb": 9.2,
    "votes": 73,
    "meta_score": 99.0,  #  or None
    "gross": 250_000_000,  #  or None
    "price": 9.99,
    "certification": "R18+",
    "description": "The aging patriarch of an organized crime dynasty transfers control "
    "of his clandestine empire to his reluctant son.",
    "directors": ["Francis Ford Coppola"],
    "genres": ["Gangster", "Crime", "Drama"],
    "stars": ["Marlon Brando", "Al Pacino", "James Caan"],
}

movie_update_schema_example = {
    "name": "The Godfather",
    "year": 1972,
    "time": 175,
    "imdb": 9.2,
    "votes": 73,
    "meta_score": 99.0,
    "gross": 250_000_000,
    "price": 9.99,
    "certification": "R18+",
    "description": "The aging patriarch of an organized crime dynasty transfers control "
    "of his clandestine empire to his reluctant son.",
}

movie_genres_update_schema_example = {"genres": ["Gangster", "Crime", "Drama"]}

movie_directors_update_schema_example = {
    "directors": ["Lana Wachowski", "Lilly Wachowski"]
}

movie_stars_update_schema_example = {
    "stars": ["Marlon Brando", "Al Pacino", "James Caan"]
}

movie_detail_actions_schema_example = {
    "movie": {
        "id": 4,
        "name": "Matrix",
        "year": 1999,
        "time": 136,
        "imdb": 8.7,
        "description": "When a beautiful stranger leads computer hacker Neo to a forbidding underworld, he discovers the shocking truth--the life he knows is the elaborate deception of an evil cyber-intelligence.",
        "price": 14.99,
    },
    "is_favorite": True,  #  or None
    "is_liked": True,  #  or None
    "remove_like_dislike": "yes",  # or None
    "to_rate": 9,  # or None
}

movie_list_favorite_schema_example = {"movies": [movie_item_schema_example]}

list_comments_schema_example = {
    "movie": {
        "id": 3,
        "name": "Forrest Gump",
        "year": 1994,
        "time": 142,
        "imdb": 8.8,
        "description": "The history of the United States from the 1950s to the '70s unfolds from the perspective of an Alabama man with an IQ of 75, who yearns to be reunited with his childhood sweetheart.",
        "price": 8.99,
    },
    "comments": [{"id": 2, "user_id": 1, "content": "I liked this movie!"}],
}
