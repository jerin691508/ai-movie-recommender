// src/pages/AiRecommendationPage.jsx
import { useState } from "react";
import { useWatchlist, useAuth } from "../App.jsx";

const TMDB_BASE = "https://api.themoviedb.org/3";
const IMG_BASE = "https://image.tmdb.org/t/p/w500";
const API_KEY = import.meta.env.VITE_TMDB_API_KEY;
const API_URL = "http://localhost:8000";

export default function AiRecommendationPage() {
  const [input, setInput] = useState("");
  const [movies, setMovies] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const { watchlist, addToWatchlist } = useWatchlist();
  const { user } = useAuth(); // <-- so we know whose history

  const generate = async () => {
    if (!input.trim()) return;

    setLoading(true);
    setError("");
    setMovies([]);

    try {
      // === Use the new retrieval-augmented backend API ===
      const response = await fetch(`${API_URL}/ai`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: user?.id || 1, // Fallback user ID if not logged in
          prompt: input,
        }),
      });

      if (!response.ok) {
        throw new Error("Backend API error");
      }

      const backendMovies = await response.json();

      // === Format movies for frontend display ===
      const formatted = backendMovies.map((m) => ({
        id: m.id,
        title: m.title,
        rating: m.vote_average?.toFixed(1),
        year: m.release_date?.slice(0, 4) || "—",
        description: m.overview,
        poster: m.poster_path ? `${IMG_BASE}${m.poster_path}` : "",
        ai_rank: m.ai_rank, // Show AI ranking if available
      }));

      setMovies(formatted);

    } catch (err) {
      console.error(err);
      setError("❌ Could not connect to backend API.");
    }

    setLoading(false);
  };

  return (
    <div>
      <h1> AI Movie Recommendation</h1>
      <p className="muted">Tell the AI what kind of movie vibe you want.</p>

      <textarea
        className="ai-textarea"
        placeholder="Example: I want emotional anime movies like Your Name..."
        value={input}
        onChange={(e) => setInput(e.target.value)}
      />

      <button className="btn-primary" onClick={generate} disabled={loading}>
        {loading ? "Thinking..." : "Recommend"}
      </button>

      {error && <p style={{ color: "red" }}>{error}</p>}

      <div className="movie-grid" style={{ marginTop: "20px" }}>
        {movies.map((m) => {
          const isAdded = Array.isArray(watchlist) &&
            watchlist.some((w) => w.tmdb_id === m.id || w.id === m.id);
          
          return (
            <div className="movie-card" key={m.id}>
              {isAdded && <span className="tick-indicator">✔</span>}
              {m.poster && <img src={m.poster} alt={m.title} />}
              <div className="movie-body">
                <h3>{m.title} {m.ai_rank && <span style={{color: '#1b4cff', fontWeight: 'bold'}}>#{m.ai_rank}</span>}</h3>
                <p className="meta">
                  {m.year} • ⭐ {m.rating}
                </p>
                <p className="desc">{m.description}</p>

                <div className="card-actions">
                  <button
                    className={`btn-primary btn-watchlist ${isAdded ? 'added' : ''}`}
                    onClick={() => addToWatchlist(m)}
                    disabled={isAdded}
                  >
                    {isAdded ? 'Added' : '➕ Add to Watchlist'}
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
