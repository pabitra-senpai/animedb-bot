"""Realistic sample AniList `Media` payloads used across tests."""

ONE_PIECE_MEDIA = {
    "id": 21,
    "idMal": 21,
    "title": {"romaji": "One Piece", "english": "One Piece", "native": "ワンピース"},
    "synonyms": ["OP"],
    "description": "Gol D. Roger was known as the Pirate King...",
    "coverImage": {
        "extraLarge": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21-op.jpg",
        "large": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21-op-large.jpg",
        "color": "#e4a80c",
    },
    "bannerImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/21-banner.jpg",
    "trailer": {"id": "S5-vZfW1Cc4", "site": "youtube"},
    "averageScore": 87,
    "meanScore": 86,
    "popularity": 500000,
    "favourites": 120000,
    "rankings": [
        {"rank": 3, "type": "RATED", "context": "all time"},
        {"rank": 1, "type": "POPULAR", "context": "all time"},
    ],
    "genres": ["Action", "Adventure", "Fantasy"],
    "studios": {"nodes": [{"id": 18, "name": "Toei Animation"}]},
    "format": "TV",
    "status": "RELEASING",
    "season": "FALL",
    "seasonYear": 1999,
    "episodes": None,
    "duration": 24,
    "source": "MANGA",
    "countryOfOrigin": "JP",
}

# A minimal/edge-case record: no romaji title, no rankings, no studios.
MINIMAL_MEDIA = {
    "id": 999,
    "idMal": None,
    "title": {"romaji": None, "english": "Untitled Project", "native": None},
    "synonyms": [],
    "description": None,
    "coverImage": {"extraLarge": None, "large": None, "color": None},
    "bannerImage": None,
    "trailer": None,
    "averageScore": None,
    "meanScore": None,
    "popularity": 10,
    "favourites": 0,
    "rankings": [],
    "genres": [],
    "studios": {"nodes": []},
    "format": "TV",
    "status": "NOT_YET_RELEASED",
    "season": None,
    "seasonYear": None,
    "episodes": None,
    "duration": None,
    "source": None,
    "countryOfOrigin": "JP",
}

NO_TITLE_MEDIA = {
    "id": 1000,
    "title": {"romaji": None, "english": None, "native": None},
    "synonyms": [],
    "coverImage": {},
    "studios": {"nodes": []},
    "rankings": [],
    "genres": [],
}

MEDIA_WITH_STREAMING_EPISODES = dict(
    ONE_PIECE_MEDIA,
    streamingEpisodes=[
        {"title": "Episode 1 - Romance Dawn, the Great Swordsman!", "thumbnail": "https://example.com/1.jpg"},
        {"title": "Episode 2 - The Man They Call \"Straw Hat Luffy\"", "thumbnail": "https://example.com/2.jpg"},
        {"title": "Episode 1 - Duplicate of episode 1", "thumbnail": "https://example.com/1dup.jpg"},
        {"title": "Not an episode title at all", "thumbnail": "https://example.com/x.jpg"},
        {"title": "Episode 5", "thumbnail": None},
    ],
)

CHARACTERS_CONNECTION = {
    "pageInfo": {"hasNextPage": True},
    "edges": [
        {
            "role": "MAIN",
            "voiceActors": [
                {
                    "id": 1001,
                    "name": {"full": "Mayumi Tanaka", "native": "田中真弓"},
                    "image": {"large": "https://example.com/va1.jpg"},
                }
            ],
            "node": {
                "id": 40,
                "name": {"full": "Monkey D. Luffy", "native": "モンキー・D・ルフィ"},
                "image": {"large": "https://example.com/char40.jpg"},
            },
        },
        {
            "role": "SUPPORTING",
            "voiceActors": [],
            "node": {
                "id": 41,
                "name": {"full": "Nami", "native": "ナミ"},
                "image": {"large": None},
            },
        },
    ],
}

STAFF_CONNECTION = {
    "pageInfo": {"hasNextPage": False},
    "edges": [
        {
            "role": "Director",
            "node": {
                "id": 500,
                "name": {"full": "Konosuke Uda", "native": "宇田鋼之介"},
                "image": {"large": "https://example.com/staff500.jpg"},
            },
        },
        {
            "role": "Original Creator",
            "node": {
                "id": 501,
                "name": {"full": "Eiichiro Oda", "native": "尾田栄一郎"},
                "image": {"large": None},
            },
        },
    ],
}


def search_page(media_list: list[dict], total: int | None = None) -> dict:
    return {
        "pageInfo": {
            "total": total if total is not None else len(media_list),
            "currentPage": 1,
            "lastPage": 1,
            "hasNextPage": False,
        },
        "media": media_list,
    }
