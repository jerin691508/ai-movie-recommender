// src/pages/RandomPage.jsx
import { useState } from "react";
import { useWatchlist, useAuth } from "../App.jsx";
import heroImg from "../assets/home-hero.jpg";

const TMDB_BASE = "https://api.themoviedb.org/3";
const IMG_BASE = "https://image.tmdb.org/t/p/w500";
const API_KEY = import.meta.env.VITE_TMDB_API_KEY;

export default function RandomPage() {
  const { watchlist, addToWatchlist } = useWatchlist();
  const { user } = useAuth();

  const [movie, setMovie] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const pickRandomMovie = async () => {
    setLoading(true);
    setError("");
    setMovie(null);

    try {
      // random page between 1 and 50
      const randomPage = Math.floor(Math.random() * 50) + 1;

      const res = await fetch(
        `${TMDB_BASE}/discover/movie?api_key=${API_KEY}&language=en-US&sort_by=vote_average.desc&vote_count.gte=200&vote_average.gte=7&include_adult=false&page=${randomPage}`
      );
      const data = await res.json();

      if (!data.results || data.results.length === 0) {
        setError("No movies found. Try again.");
        setLoading(false);
        return;
      }

      const randomIndex = Math.floor(Math.random() * data.results.length);
      const m = data.results[randomIndex];

      setMovie({
        id: m.id,
        title: m.title,
        year: m.release_date?.slice(0, 4) || "—",
        rating: m.vote_average ? m.vote_average.toFixed(1) : "—",
        description: m.overview,
        poster: m.poster_path ? `${IMG_BASE}${m.poster_path}` : "",
        language: m.original_language,
      });
    } catch (e) {
      console.error(e);
      setError("Failed to fetch random movie.");
    }

    setLoading(false);
  };

  const handleSave = () => {
    if (!user) {
      alert("Login to save this movie to your watchlist.");
      return;
    }
    if (movie) addToWatchlist(movie);
  };

  return (
    <div className="random-wrapper" style={{ backgroundImage: `url(${heroImg})` }}>
      <div className="home-hero-overlay" />
      <div className="random-inner">
        <div className="random-panel">
          <h1>Feeling indecisive?</h1>
          <p className="muted">
            Let the system pick a highly-rated movie for you. Any genre, any year,
            rating 7 or above.
          </p>

          <button className="random-button" onClick={pickRandomMovie} disabled={loading}>
            <span className="pulse-dot" />
            {loading ? "Finding a great movie..." : "Random Selection"}
          </button>

          {error && (
            <p style={{ color: "salmon", marginTop: "0.75rem" }}>
              {error}
            </p>
          )}

          {movie && (
            <div className="random-card">
              {movie.poster && (
                <img src={movie.poster} alt={movie.title} className="random-poster" />
              )}
              <div className="random-info">
                <h2>{movie.title}</h2>
                <p className="meta">
                  {movie.year} • ⭐ {movie.rating} • {movie.language?.toUpperCase()}
                </p>
                <p className="desc">{movie.description}</p>
                {(() => {
                  const isAdded = Array.isArray(watchlist) &&
                    watchlist.some((w) => w.tmdb_id === movie.id || w.id === movie.id);
                  return (
                    <button
                      className={`btn-primary btn-watchlist ${isAdded ? 'added' : ''}`}
                      onClick={handleSave}
                      disabled={isAdded}
                    >
                      {isAdded ? '✓ Added' : '➕ Add to Watchlist'}
                    </button>
                  );
                })()}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
