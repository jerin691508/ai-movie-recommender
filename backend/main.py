from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, field_validator
from db import init_db, get_connection
from auth import (
    create_user,
    get_user_by_username,
    get_user_by_email,
    get_user_by_id,
    verify_password,
)
from dotenv import load_dotenv
import os
import requests
import re
import spacy
from typing import List, Dict, Tuple

load_dotenv()

TMDB_KEY = os.getenv("TMDB_KEY", "YOUR_TMDB_API_KEY_HERE")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

init_db()
app = FastAPI(title="Movie Backend")

# Load spaCy model for NLP processing
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Warning: spaCy model not found. Using simple keyword extraction.")
    nlp = None

# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Pydantic models ----------

class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    confirm_password: str

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v, info):
        data = info.data
        if "password" in data and v != data["password"]:
            raise ValueError("Passwords do not match")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str


class WatchlistIn(BaseModel):
    user_id: int
    tmdb_id: int
    title: str
    poster: str | None = None
    year: str | None = None
    rating: str | None = None
    genreLabel: str | None = None
    language: str | None = None
    description: str | None = None


class WatchlistOut(BaseModel):
    id: int
    tmdb_id: int
    title: str
    poster: str | None
    year: str | None
    rating: str | None
    genreLabel: str | None
    language: str | None
    description: str | None


class AIRequest(BaseModel):
    user_id: int
    prompt: str


class HistoryRequest(BaseModel):
    user_id: int
    prompt: str
    suggestions: str


# ---------- Auth endpoints ----------

@app.post("/register")
def register_user(data: RegisterRequest):
    if get_user_by_username(data.username):
        raise HTTPException(status_code=400, detail="Username already exists")

    if get_user_by_email(data.email):
        raise HTTPException(status_code=400, detail="Email already exists")

    create_user(data.username, data.email, data.password, role="user")
    return {"message": "User registered"}


@app.post("/login", response_model=LoginResponse)
def login_user(data: LoginRequest):
    row = get_user_by_username(data.username)
    if row is None or not verify_password(data.password, row["password"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    return LoginResponse(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        role=row["role"],
    )


# ---------- Watchlist endpoints ----------

@app.get("/watchlist/{user_id}", response_model=list[WatchlistOut])
def get_watchlist(user_id: int):
    # Return empty list if user doesn't exist yet instead of 404
    if get_user_by_id(user_id) is None:
        return []

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, tmdb_id, title, poster, year, rating, genre_label, language, description
        FROM watchlist
        WHERE user_id = ?
        """,
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()

    return [
        WatchlistOut(
            id=row["id"],
            tmdb_id=row["tmdb_id"],
            title=row["title"],
            poster=row["poster"],
            year=row["year"],
            rating=row["rating"],
            genreLabel=row["genre_label"],
            language=row["language"],
            description=row["description"],
        )
        for row in rows
    ]


@app.post("/watchlist", response_model=WatchlistOut)
def add_watchlist(item: WatchlistIn):
    if get_user_by_id(item.user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO watchlist (user_id, tmdb_id, title, poster, year, rating, genre_label, language, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item.user_id,
            item.tmdb_id,
            item.title,
            item.poster,
            item.year,
            item.rating,
            item.genreLabel,
            item.language,
            item.description,
        ),
    )
    conn.commit()
    new_id = cur.lastrowid

    cur.execute(
        """
        SELECT id, tmdb_id, title, poster, year, rating, genre_label, language, description
        FROM watchlist
        WHERE id = ?
        """,
        (new_id,),
    )
    row = cur.fetchone()
    conn.close()

    return WatchlistOut(
        id=row["id"],
        tmdb_id=row["tmdb_id"],
        title=row["title"],
        poster=row["poster"],
        year=row["year"],
        rating=row["rating"],
        genreLabel=row["genre_label"],
        language=row["language"],
        description=row["description"],
    )


@app.delete("/watchlist/{user_id}/{item_id}")
def delete_watchlist(user_id: int, item_id: int):
    if get_user_by_id(user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM watchlist WHERE id = ? AND user_id = ?",
        (item_id, user_id),
    )
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Item not found")
    conn.commit()
    conn.close()
    return {"message": "Deleted"}


# ---------- Helper Functions for Intelligent NLP-based AI ----------

def detect_user_intent(prompt: str) -> Dict[str, any]:
    """
    Detect user intent: actor, similar movie, genre/mood, or year queries.
    """
    prompt_lower = prompt.lower()
    
    # Actor detection patterns
    actor_patterns = [
        r'(\w+)\s+movies',
        r'movies\s+of\s+(\w+(?:\s+\w+)*)',
        r'(\w+(?:\s+\w+)*)\s+movies',
        r'actor\s+(\w+(?:\s+\w+)*)',
        r'starring\s+(\w+(?:\s+\w+)*)'
    ]
    
    # Similar movie patterns
    similar_patterns = [
        r'movies?\s+like\s+(.+)',
        r'similar\s+to\s+(.+)',
        r'like\s+(.+)',
        r'movies?\s+similar\s+to\s+(.+)'
    ]
    
    # Check for actor queries
    for pattern in actor_patterns:
        match = re.search(pattern, prompt_lower)
        if match:
            actor_name = match.group(1).strip()
            return {"intent": "actor", "entity": actor_name}
    
    # Check for similar movie queries
    for pattern in similar_patterns:
        match = re.search(pattern, prompt_lower)
        if match:
            movie_title = match.group(1).strip()
            return {"intent": "similar", "entity": movie_title}
    
    # Check for year queries
    year_match = re.search(r'\b(19|20)\d{2}\b', prompt)
    if year_match:
        return {"intent": "year", "entity": year_match.group(), "keywords": intelligent_keyword_extraction(prompt)}
    
    # Default to genre/mood query
    return {"intent": "genre_mood", "keywords": intelligent_keyword_extraction(prompt)}

def intelligent_keyword_extraction(prompt: str) -> Dict[str, any]:
    """
    Advanced keyword extraction using spaCy NLP processing.
    Extracts genres, moods, themes, years, and similarity requests.
    """
    if nlp is None:
        # Fallback to simple extraction if spaCy is not available
        return extract_keywords_from_prompt(prompt)
    
    # Process the prompt with spaCy
    doc = nlp(prompt.lower())
    
    # Extract meaningful tokens (nouns, adjectives, proper nouns)
    meaningful_tokens = []
    for token in doc:
        if (token.pos_ in ['NOUN', 'ADJ', 'PROPN'] and 
            not token.is_stop and 
            not token.is_punct and 
            len(token.text) > 2):
            meaningful_tokens.append(token.lemma_)
    
    # Define comprehensive keyword mappings
    genre_keywords = {
        'action': ['action', 'adventure', 'thriller', 'explosive', 'fast-paced'],
        'comedy': ['comedy', 'funny', 'humor', 'laugh', 'hilarious'],
        'horror': ['horror', 'scary', 'terrifying', 'frightening', 'creepy'],
        'sci-fi': ['scifi', 'science fiction', 'space', 'future', 'alien', 'robot'],
        'romance': ['romance', 'romantic', 'love', 'relationship', 'dating'],
        'drama': ['drama', 'dramatic', 'emotional', 'serious', 'intense'],
        'thriller': ['thriller', 'suspense', 'tense', 'mystery', 'psychological'],
        'animation': ['animation', 'animated', 'cartoon', 'anime', 'drawn'],
        'crime': ['crime', 'criminal', 'heist', 'gangster', 'detective'],
        'war': ['war', 'military', 'battle', 'soldier', 'combat'],
        'fantasy': ['fantasy', 'magical', 'mythical', 'dragon', 'wizard'],
        'family': ['family', 'kids', 'children', 'family-friendly'],
        'documentary': ['documentary', 'documentary', 'real', 'factual']
    }
    
    mood_keywords = {
        'sad': ['sad', 'emotional', 'tearjerker', 'heartbreaking', 'melancholy'],
        'happy': ['happy', 'feel-good', 'uplifting', 'cheerful', 'joyful'],
        'dark': ['dark', 'grim', 'bleak', 'somber', 'serious'],
        'funny': ['funny', 'humorous', 'comical', 'amusing', 'witty'],
        'scary': ['scary', 'frightening', 'terrifying', 'horror', 'creepy'],
        'romantic': ['romantic', 'love', 'passionate', 'tender', 'sweet'],
        'inspiring': ['inspiring', 'motivational', 'uplifting', 'hopeful'],
        'relaxing': ['relaxing', 'calm', 'peaceful', 'soothing', 'gentle']
    }
    
    theme_keywords = {
        'space': ['space', 'galaxy', 'universe', 'planet', 'astronaut', 'cosmos'],
        'time travel': ['time travel', 'time machine', 'future', 'past', 'temporal'],
        'survival': ['survival', 'survive', 'stranded', 'wilderness', 'apocalypse'],
        'crime': ['crime', 'murder', 'investigation', 'mystery', 'detective'],
        'war': ['war', 'battle', 'military', 'soldier', 'combat'],
        'love': ['love', 'romance', 'relationship', 'dating', 'marriage'],
        'friendship': ['friendship', 'friends', 'buddy', 'companionship'],
        'revenge': ['revenge', 'vengeance', 'payback', 'retaliation'],
        'adventure': ['adventure', 'journey', 'quest', 'expedition', 'exploration']
    }
    
    # Extract keywords by matching tokens to our mappings
    extracted_genres = []
    extracted_moods = []
    extracted_themes = []
    
    # Check for genre keywords
    for genre, keywords in genre_keywords.items():
        if any(keyword in meaningful_tokens for keyword in keywords):
            extracted_genres.append(genre)
    
    # Check for mood keywords
    for mood, keywords in mood_keywords.items():
        if any(keyword in meaningful_tokens for keyword in keywords):
            extracted_moods.append(mood)
    
    # Check for theme keywords
    for theme, keywords in theme_keywords.items():
        if any(keyword in meaningful_tokens for keyword in keywords):
            extracted_themes.append(theme)
    
    # Extract years and decades
    years = re.findall(r'\b(19|20)\d{2}\b', prompt)
    decades = re.findall(r'\b\d{0,2}0s\b', prompt.lower())
    
    # Check for similarity requests ("movies like X")
    similarity_request = None
    similarity_patterns = [
        r'movies? like (.+)',
        r'similar to (.+)',
        r'like (.+)',
        r'movies? similar to (.+)'
    ]
    
    for pattern in similarity_patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            similarity_request = match.group(1).strip()
            break
    
    return {
        "genres": extracted_genres,
        "moods": extracted_moods,
        "themes": extracted_themes,
        "years": years,
        "decades": decades,
        "similarity_request": similarity_request,
        "meaningful_tokens": meaningful_tokens
    }

def search_actor_movies(actor_name: str, limit: int = 20) -> List[Dict]:
    """
    Search for movies by specific actor using TMDB person search and movie credits.
    """
    try:
        # Step 1: Find the actor
        person_response = requests.get(
            "https://api.themoviedb.org/3/search/person",
            params={
                "api_key": TMDB_KEY,
                "query": actor_name,
                "language": "en-US"
            }
        )
        person_response.raise_for_status()
        person_data = person_response.json()
        
        if not person_data.get("results"):
            return []
        
        actor = person_data["results"][0]
        actor_id = actor["id"]
        
        # Step 2: Get actor's movie credits
        credits_response = requests.get(
            f"https://api.themoviedb.org/3/person/{actor_id}/movie_credits",
            params={
                "api_key": TMDB_KEY,
                "language": "en-US"
            }
        )
        credits_response.raise_for_status()
        credits_data = credits_response.json()
        
        # Get cast movies (not crew)
        movies = []
        for movie in credits_data.get("cast", []):
            if movie.get("known_for_department") == "Acting" and movie.get("popularity", 0) > 1:
                movies.append({
                    "id": movie["id"],
                    "title": movie["title"],
                    "overview": movie.get("overview", ""),
                    "vote_average": movie.get("vote_average", 0),
                    "popularity": movie.get("popularity", 0),
                    "release_date": movie.get("release_date", ""),
                    "poster_path": movie.get("poster_path", ""),
                    "genre_ids": movie.get("genre_ids", []),
                    "character": movie.get("character", "")
                })
        
        # Sort by popularity and return top results
        movies.sort(key=lambda x: x.get("popularity", 0), reverse=True)
        return movies[:limit]
        
    except Exception as e:
        print(f"Error searching actor movies: {e}")
        return []

def search_similar_movies(movie_title: str, limit: int = 20) -> List[Dict]:
    """
    Search for movies similar to a specific movie using TMDB similar endpoint.
    """
    try:
        # Step 1: Find the movie
        movie_response = requests.get(
            "https://api.themoviedb.org/3/search/movie",
            params={
                "api_key": TMDB_KEY,
                "query": movie_title,
                "language": "en-US"
            }
        )
        movie_response.raise_for_status()
        movie_data = movie_response.json()
        
        if not movie_data.get("results"):
            return []
        
        movie = movie_data["results"][0]
        movie_id = movie["id"]
        
        # Step 2: Get similar movies
        similar_response = requests.get(
            f"https://api.themoviedb.org/3/movie/{movie_id}/similar",
            params={
                "api_key": TMDB_KEY,
                "language": "en-US",
                "page": 1
            }
        )
        similar_response.raise_for_status()
        similar_data = similar_response.json()
        
        # Format similar movies
        movies = []
        for movie in similar_data.get("results", []):
            movies.append({
                "id": movie["id"],
                "title": movie["title"],
                "overview": movie.get("overview", ""),
                "vote_average": movie.get("vote_average", 0),
                "popularity": movie.get("popularity", 0),
                "release_date": movie.get("release_date", ""),
                "poster_path": movie.get("poster_path", ""),
                "genre_ids": movie.get("genre_ids", [])
            })
        
        return movies[:limit]
        
    except Exception as e:
        print(f"Error searching similar movies: {e}")
        return []

def search_year_movies(year: str, keywords: Dict = None, limit: int = 20) -> List[Dict]:
    """
    Search movies by year with optional genre/mood filters.
    """
    try:
        params = {
            "api_key": TMDB_KEY,
            "language": "en-US",
            "sort_by": "popularity.desc",
            "primary_release_year": year,
            "include_adult": "false",
            "page": 1
        }
        
        # Add genre filters if keywords provided
        if keywords and keywords.get("genres"):
            genre_map = {
                "action": 28, "adventure": 12, "animation": 16, "comedy": 35,
                "crime": 80, "documentary": 99, "drama": 18, "family": 10751,
                "fantasy": 14, "horror": 27, "music": 10402, "mystery": 9648,
                "romance": 10749, "science fiction": 878, "thriller": 53,
                "war": 10752, "western": 37, "sci-fi": 878
            }
            
            genre_ids = []
            for genre in keywords["genres"]:
                if genre in genre_map:
                    genre_ids.append(genre_map[genre])
            
            if genre_ids:
                params["with_genres"] = ",".join(map(str, genre_ids))
        
        response = requests.get(
            "https://api.themoviedb.org/3/discover/movie",
            params=params
        )
        response.raise_for_status()
        data = response.json()
        
        movies = []
        for movie in data.get("results", []):
            movies.append({
                "id": movie["id"],
                "title": movie["title"],
                "overview": movie.get("overview", ""),
                "vote_average": movie.get("vote_average", 0),
                "popularity": movie.get("popularity", 0),
                "release_date": movie.get("release_date", ""),
                "poster_path": movie.get("poster_path", ""),
                "genre_ids": movie.get("genre_ids", [])
            })
        
        return movies[:limit]
        
    except Exception as e:
        print(f"Error searching year movies: {e}")
        return []

def get_movie_similarity_basis(movie_title: str) -> Dict[str, any]:
    """
    Get basis for similarity search by finding a movie and extracting its properties.
    """
    try:
        # Search for the movie in TMDB
        response = requests.get(
            "https://api.themoviedb.org/3/search/movie",
            params={
                "api_key": TMDB_KEY,
                "query": movie_title,
                "language": "en-US"
            }
        )
        response.raise_for_status()
        data = response.json()
        
        if not data.get("results"):
            return None
        
        movie = data["results"][0]
        
        # Get detailed movie info including genres and keywords
        details_response = requests.get(
            f"https://api.themoviedb.org/3/movie/{movie['id']}",
            params={
                "api_key": TMDB_KEY,
                "language": "en-US",
                "append_to_response": "keywords"
            }
        )
        details_response.raise_for_status()
        movie_details = details_response.json()
        
        return {
            "id": movie_details["id"],
            "title": movie_details["title"],
            "genres": [g["name"].lower() for g in movie_details.get("genres", [])],
            "keywords": [k["name"].lower() for k in movie_details.get("keywords", {}).get("keywords", [])],
            "vote_average": movie_details.get("vote_average", 0),
            "popularity": movie_details.get("popularity", 0),
            "release_date": movie_details.get("release_date", "")
        }
        
    except Exception as e:
        print(f"Error getting movie similarity basis: {e}")
        return None
        
        # Get detailed movie info including genres and keywords
        details_response = requests.get(
            f"https://api.themoviedb.org/3/movie/{movie['id']}",
            params={
                "api_key": TMDB_KEY,
                "language": "en-US",
                "append_to_response": "keywords"
            }
        )
        details_response.raise_for_status()
        movie_details = details_response.json()
        
        return {
            "id": movie_details["id"],
            "title": movie_details["title"],
            "genres": [g["name"].lower() for g in movie_details.get("genres", [])],
            "keywords": [k["name"].lower() for k in movie_details.get("keywords", {}).get("keywords", [])],
            "vote_average": movie_details.get("vote_average", 0),
            "popularity": movie_details.get("popularity", 0),
            "release_date": movie_details.get("release_date", "")
        }
        
    except Exception as e:
        print(f"Error getting movie similarity basis: {e}")
        return None

def map_keywords_to_tmdb_params(keywords: Dict[str, any]) -> Dict[str, any]:
    """
    Map extracted keywords to TMDB API parameters.
    """
    tmdb_params = {
        "api_key": TMDB_KEY,
        "language": "en-US",
        "sort_by": "popularity.desc",
        "include_adult": "false",
        "page": 1
    }
    
    # Genre mapping
    genre_map = {
        "action": 28, "adventure": 12, "animation": 16, "comedy": 35,
        "crime": 80, "documentary": 99, "drama": 18, "family": 10751,
        "fantasy": 14, "horror": 27, "music": 10402, "mystery": 9648,
        "romance": 10749, "science fiction": 878, "thriller": 53,
        "war": 10752, "western": 37, "sci-fi": 878
    }
    
    # Add genre filters
    if keywords.get("genres"):
        genre_ids = []
        for genre in keywords["genres"]:
            if genre in genre_map:
                genre_ids.append(genre_map[genre])
        
        if genre_ids:
            tmdb_params["with_genres"] = ",".join(map(str, genre_ids))
    
    # Add year filters
    if keywords.get("years"):
        tmdb_params["primary_release_year"] = keywords["years"][0]
    elif keywords.get("decades"):
        decade = keywords["decades"][0]
        start_year = int(decade.replace("s", ""))  
        end_year = start_year + 9
        tmdb_params["primary_release_date.gte"] = f"{start_year}-01-01"
        tmdb_params["primary_release_date.lte"] = f"{end_year}-12-31"
    
    # Add keyword search for themes and moods
    search_terms = []
    search_terms.extend(keywords.get("themes", []))
    search_terms.extend(keywords.get("moods", []))
    search_terms.extend(keywords.get("meaningful_tokens", []))
    
    if search_terms:
        # Limit search terms to avoid overly long queries
        tmdb_params["query"] = " ".join(search_terms[:3])
    
    return tmdb_params, search_terms

def retrieve_movies_from_tmdb_intelligent(keywords: Dict[str, any], limit: int = 20) -> List[Dict]:
    """
    Intelligent movie retrieval using NLP-extracted keywords and similarity search.
    """
    movies = []
    
    # Handle similarity requests first
    if keywords.get("similarity_request"):
        similarity_basis = get_movie_similarity_basis(keywords["similarity_request"])
        if similarity_basis:
            # Use the similar movie's genres and keywords for search
            enhanced_keywords = keywords.copy()
            enhanced_keywords["genres"] = list(set(enhanced_keywords.get("genres", []) + similarity_basis["genres"]))
            enhanced_keywords["meaningful_tokens"] = list(set(enhanced_keywords.get("meaningful_tokens", []) + similarity_basis["keywords"]))
            keywords = enhanced_keywords
    
    # Map keywords to TMDB parameters
    tmdb_params, search_terms = map_keywords_to_tmdb_params(keywords)
    
    # Only proceed if we have meaningful search criteria
    has_meaningful_criteria = bool(
        keywords.get("genres") or 
        keywords.get("themes") or 
        keywords.get("moods") or 
        keywords.get("years") or 
        keywords.get("decades") or
        keywords.get("similarity_request") or
        search_terms
    )
    
    if not has_meaningful_criteria:
        return []
    
    try:
        # Try discover endpoint first for better filtering
        if keywords.get("genres") or keywords.get("years") or keywords.get("decades"):
            response = requests.get(
                "https://api.themoviedb.org/3/discover/movie",
                params=tmdb_params
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("results"):
                movies = data["results"][:limit]
        
        # If we have search terms but no discover results, try search
        if not movies and search_terms:
            search_response = requests.get(
                "https://api.themoviedb.org/3/search/movie",
                params={
                    "api_key": TMDB_KEY,
                    "query": " ".join(search_terms[:3]),
                    "language": "en-US",
                    "sort_by": "popularity.desc",
                    "page": 1
                }
            )
            search_response.raise_for_status()
            search_data = search_response.json()
            if search_data.get("results"):
                movies = search_data["results"][:limit]
        
        # If we have similarity basis, filter for similar movies
        if keywords.get("similarity_request") and movies:
            similarity_basis = get_movie_similarity_basis(keywords["similarity_request"])
            if similarity_basis:
                movies = filter_similar_movies(movies, similarity_basis, limit)
        
        # Additional searches for themes/moods if needed
        if keywords.get("themes") or keywords.get("moods"):
            theme_movies = search_movies_by_themes_moods(keywords)
            movies = merge_and_deduplicate_movies(movies, theme_movies, limit)
    
    except requests.RequestException as e:
        print(f"TMDB API error: {e}")
        # Fallback to simple search
        movies = search_movies_by_keywords_fallback(keywords, limit)
    
    return movies

def filter_similar_movies(movies: List[Dict], similarity_basis: Dict[str, any], limit: int) -> List[Dict]:
    """
    Filter movies based on similarity to the reference movie.
    """
    scored_movies = []
    
    for movie in movies:
        score = 0
        
        # Genre similarity
        movie_genres = [str(g).lower() for g in movie.get("genre_ids", [])]
        for genre in similarity_basis.get("genres", []):
            if genre in movie_genres:
                score += 2
        
        # Keyword similarity (basic text matching)
        movie_text = f"{movie.get('title', '')} {movie.get('overview', '')}".lower()
        for keyword in similarity_basis.get("keywords", []):
            if keyword in movie_text:
                score += 1
        
        # Popularity and rating similarity
        rating_diff = abs(movie.get("vote_average", 0) - similarity_basis.get("vote_average", 0))
        if rating_diff < 2:  # Within 2 points
            score += 1
        
        scored_movies.append({"movie": movie, "score": score})
    
    # Sort by score and return top movies
    scored_movies.sort(key=lambda x: x["score"], reverse=True)
    return [item["movie"] for item in scored_movies[:limit]]

def search_movies_by_themes_moods(keywords: Dict[str, any], limit: int = 10) -> List[Dict]:
    """
    Search movies specifically for themes and moods.
    """
    movies = []
    search_terms = []
    
    # Theme-based search queries
    theme_queries = {
        "space": "space", "time travel": "time travel", "survival": "survival",
        "crime": "crime mystery", "war": "war battle", "love": "romance love",
        "friendship": "friendship", "revenge": "revenge", "adventure": "adventure"
    }
    
    # Mood-based search queries  
    mood_queries = {
        "sad": "emotional drama", "happy": "feel good comedy", "dark": "dark thriller",
        "funny": "comedy humor", "scary": "horror scary", "romantic": "romance love",
        "inspiring": "inspirational", "relaxing": "calm peaceful"
    }
    
    # Collect search terms
    for theme in keywords.get("themes", []):
        if theme in theme_queries:
            search_terms.append(theme_queries[theme])
    
    for mood in keywords.get("moods", []):
        if mood in mood_queries:
            search_terms.append(mood_queries[mood])
    
    # Search for each term
    for term in search_terms[:3]:  # Limit to avoid too many API calls
        try:
            response = requests.get(
                "https://api.themoviedb.org/3/search/movie",
                params={
                    "api_key": TMDB_KEY,
                    "query": term,
                    "language": "en-US",
                    "sort_by": "popularity.desc",
                    "page": 1
                }
            )
            response.raise_for_status()
            data = response.json()
            if data.get("results"):
                movies.extend(data["results"][:3])
        except requests.RequestException as e:
            print(f"Theme/mood search error for '{term}': {e}")
    
    return movies

def search_movies_by_keywords_fallback(keywords: Dict[str, any], limit: int = 20) -> List[Dict]:
    """
    Fallback search using combined keywords.
    """
    all_keywords = []
    all_keywords.extend(keywords.get("genres", []))
    all_keywords.extend(keywords.get("themes", []))
    all_keywords.extend(keywords.get("moods", []))
    all_keywords.extend(keywords.get("meaningful_tokens", []))
    
    if not all_keywords:
        return []
    
    search_query = " ".join(all_keywords[:5])  # Limit query length
    
    try:
        response = requests.get(
            "https://api.themoviedb.org/3/search/movie",
            params={
                "api_key": TMDB_KEY,
                "query": search_query,
                "language": "en-US",
                "sort_by": "popularity.desc",
                "page": 1
            }
        )
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])[:limit]
    except requests.RequestException as e:
        print(f"Keyword fallback search error: {e}")
        return []

def search_movies_by_mood_type(keywords: Dict[str, List[str]], limit: int = 10) -> List[Dict]:
    """
    Search movies using mood/type keywords when discover doesn't support them.
    """
    movies = []
    
    # Create search queries from moods and types
    search_terms = []
    
    mood_queries = {
        "happy": "feel good", "sad": "emotional", "exciting": "action",
        "relaxing": "calm", "scary": "horror", "funny": "comedy",
        "romantic": "romance", "thrilling": "thriller", "inspiring": "inspirational",
        "dark": "dark", "uplifting": "uplifting"
    }
    
    type_queries = {
        "blockbuster": "blockbuster", "indie": "indie", "classic": "classic",
        "modern": "recent", "animation": "animation", "superhero": "superhero"
    }
    
    for mood in keywords["moods"]:
        if mood in mood_queries:
            search_terms.append(mood_queries[mood])
    
    for mtype in keywords["types"]:
        if mtype in type_queries:
            search_terms.append(type_queries[mtype])
    
    # Search for each term and combine results
    for term in search_terms[:3]:  # Limit to avoid too many API calls
        try:
            response = requests.get(
                "https://api.themoviedb.org/3/search/movie",
                params={
                    "api_key": TMDB_KEY,
                    "query": term,
                    "language": "en-US",
                    "sort_by": "popularity.desc",
                    "page": 1
                }
            )
            response.raise_for_status()
            data = response.json()
            if data.get("results"):
                movies.extend(data["results"][:5])
        except requests.RequestException as e:
            print(f"Search error for term '{term}': {e}")
    
    return movies

def search_movies_by_keywords(keywords: Dict[str, List[str]], limit: int = 20) -> List[Dict]:
    """
    Fallback search using combined keywords.
    """
    all_keywords = []
    all_keywords.extend(keywords["genres"])
    all_keywords.extend(keywords["moods"]) 
    all_keywords.extend(keywords["types"])
    
    if not all_keywords:
        return []
    
    search_query = " ".join(all_keywords[:5])  # Limit query length
    
    try:
        response = requests.get(
            "https://api.themoviedb.org/3/search/movie",
            params={
                "api_key": TMDB_KEY,
                "query": search_query,
                "language": "en-US",
                "sort_by": "popularity.desc",
                "page": 1
            }
        )
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])[:limit]
    except requests.RequestException as e:
        print(f"Keyword search error: {e}")
        return []

def merge_and_deduplicate_movies(movies1: List[Dict], movies2: List[Dict], limit: int) -> List[Dict]:
    """
    Merge two movie lists and remove duplicates based on ID.
    """
    seen_ids = set()
    merged = []
    
    for movie in movies1:
        if movie.get("id") not in seen_ids:
            seen_ids.add(movie["id"])
            merged.append(movie)
    
    for movie in movies2:
        if movie.get("id") not in seen_ids:
            seen_ids.add(movie["id"])
            merged.append(movie)
    
    return merged[:limit]

# ---------- AI endpoint (backend does Ollama + TMDB + auto-history) ----------

@app.post("/ai")
def ai_recommend(data: AIRequest):
    if get_user_by_id(data.user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Step 1: Detect user intent
    intent_result = detect_user_intent(data.prompt)
    intent = intent_result["intent"]
    
    # Step 2: Retrieve movies based on intent
    candidate_movies = []
    
    if intent == "actor":
        candidate_movies = search_actor_movies(intent_result["entity"], limit=15)
    elif intent == "similar":
        candidate_movies = search_similar_movies(intent_result["entity"], limit=15)
    elif intent == "year":
        candidate_movies = search_year_movies(
            intent_result["entity"], 
            intent_result.get("keywords"), 
            limit=15
        )
    elif intent == "genre_mood":
        candidate_movies = retrieve_movies_from_tmdb_intelligent(intent_result["keywords"], limit=15)
    
    if not candidate_movies:
        # Fallback to original method if no movies found
        return ai_recommendation_fallback(data)
    
    # Step 3: Prepare movie list for AI ranking
    movie_list_for_ai = []
    for movie in candidate_movies:
        movie_info = {
            "id": movie.get("id"),
            "title": movie.get("title", ""),
            "overview": movie.get("overview", ""),
            "vote_average": movie.get("vote_average", 0),
            "popularity": movie.get("popularity", 0),
            "release_date": movie.get("release_date", ""),
            "genre_ids": movie.get("genre_ids", [])
        }
        movie_list_for_ai.append(movie_info)
    
    # Step 4: Send retrieved movie list to Ollama for ranking
    movies_text = "\n".join([
        f"{i+1}. {movie['title']} ({movie.get('release_date', 'Unknown')[:4]}) - Rating: {movie.get('vote_average', 'N/A')}"
        for i, movie in enumerate(movie_list_for_ai[:10])
    ])
    
    # Enhanced ranking prompt that considers the intent and extracted keywords
    ranking_prompt = f"""
    User Request: {data.prompt}
    
    Detected Intent: {intent}
    Search Entity: {intent_result.get('entity', 'N/A')}
    
    Available Movies:
    {movies_text}
    
    Instructions:
    1. Analyze the user's request and detected intent
    2. Consider the specific type of search (actor, similar movie, genre, year)
    3. Select and rank the TOP 5 movies that best match the user's preferences
    4. For actor searches, prioritize popular/known movies by that actor
    5. For similar movie searches, prioritize movies with similar themes/genres
    6. For genre/mood searches, prioritize movies that strongly match those characteristics
    7. For year searches, prioritize the best movies from that year
    8. Return ONLY the movie titles in order of preference, separated by commas
    9. Do NOT include any explanations or additional text
    10. Only use titles from the provided list
    
    Example response format: Movie Title 1, Movie Title 2, Movie Title 3
    """
    
    try:
        ollama_resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": "phi3",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a movie recommendation expert. Analyze user requests and rank provided movies based on detected intent. Return only movie titles separated by commas, no additional text.",
                    },
                    {"role": "user", "content": ranking_prompt},
                ],
                "stream": False,
            },
        )
        ollama_resp.raise_for_status()
        content = ollama_resp.json()["message"]["content"]
        ranked_titles = [t.strip() for t in content.split(",") if t.strip()]
        
        # Step 5: Filter and return ranked movies
        final_recommendations = []
        ranked_titles_lower = [title.lower() for title in ranked_titles]
        
        # Find movies that match the ranked titles
        for movie in candidate_movies:
            movie_title = movie.get("title", "").lower()
            if movie_title in ranked_titles_lower and len(final_recommendations) < 5:
                # Find the rank order
                rank_index = -1
                for i, ranked_title in enumerate(ranked_titles):
                    if ranked_title.lower() == movie_title:
                        rank_index = i
                        break
                
                if rank_index >= 0:
                    movie_copy = movie.copy()
                    movie_copy["ai_rank"] = rank_index + 1
                    final_recommendations.append(movie_copy)
        
        # Sort by AI rank
        final_recommendations.sort(key=lambda x: x.get("ai_rank", 999))
        
        # Save history in DB with enhanced information
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO movie_memory (user_id, prompt, suggestions) VALUES (?, ?, ?)",
            (data.user_id, data.prompt, ",".join([m.get("title", "") for m in final_recommendations])),
        )
        conn.commit()
        conn.close()
        
        return final_recommendations
        
    except requests.RequestException as e:
        print(f"Ollama error: {e}")
        # Fallback: return top popular movies from candidates
        return candidate_movies[:5]

def ai_recommendation_fallback(data: AIRequest):
    """
    Fallback to original method if retrieval fails.
    """
    try:
        ollama_resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": "phi3",
                "messages": [
                    {
                        "role": "system",
                        "content": "Return movie titles separated by commas. No extra text.",
                    },
                    {"role": "user", "content": data.prompt},
                ],
                "stream": False,
            },
        )
        ollama_resp.raise_for_status()
        content = ollama_resp.json()["message"]["content"]
        titles = [t.strip() for t in content.split(",") if t.strip()]

        # Call TMDB
        results = []
        for title in titles:
            r = requests.get(
                "https://api.themoviedb.org/3/search/movie",
                params={"api_key": TMDB_KEY, "query": title},
            )
            r.raise_for_status()
            js = r.json()
            if js.get("results"):
                results.append(js["results"][0])

        # Save history in DB
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO movie_memory (user_id, prompt, suggestions) VALUES (?, ?, ?)",
            (data.user_id, data.prompt, ",".join(titles)),
        )
        conn.commit()
        conn.close()

        return results
        
    except requests.RequestException as e:
        print(f"Fallback error: {e}")
        return []


# ---------- History (for frontend-Ollama or extra saves) ----------

@app.post("/history")
def save_history(data: HistoryRequest):
    if get_user_by_id(data.user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO movie_memory (user_id, prompt, suggestions) VALUES (?, ?, ?)",
        (data.user_id, data.prompt, data.suggestions),
    )
    conn.commit()
    conn.close()
    return {"status": "saved"}


@app.get("/history/{user_id}")
def get_history(user_id: int):
    if get_user_by_id(user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, prompt, suggestions, created_at
        FROM movie_memory
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "id": row["id"],
            "prompt": row["prompt"],
            "suggestions": row["suggestions"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


@app.delete("/history/{user_id}")
def delete_history(user_id: int):
    if get_user_by_id(user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM movie_memory WHERE user_id = ?",
        (user_id,),
    )
    conn.commit()
    conn.close()
    return {"message": "History cleared"}
