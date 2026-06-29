import { useEffect, useMemo, useState } from "react";
import { useWatchlist } from "../App.jsx";
import moodImage from "../assets/mood-template.png";

const TMDB_BASE = "https://api.themoviedb.org/3";
const IMG_BASE = "https://image.tmdb.org/t/p/w500";
const API_KEY = import.meta.env.VITE_TMDB_API_KEY;

// heuristic for "best actor award winning" – high rating + many votes
const AWARD_MIN_RATING = 6.5;
const AWARD_MIN_VOTES = 500;

const sections = [
  { key: "genre", label: "Genre" },
  { key: "award", label: "Best actor award winning" },
  { key: "animation", label: "Animation" },
  { key: "language", label: "Language" },
];

export default function RecommendationPage() {
  const [rawMovies, setRawMovies] = useState([]);
  const [genres, setGenres] = useState([]);
  const [activeSection, setActiveSection] = useState("genre");
  const [activeGenre, setActiveGenre] = useState("All");
  const [language, setLanguage] = useState("All");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const { watchlist, addToWatchlist } = useWatchlist();

  // fetch TMDB genres + movies once
  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        setError("");

        const genreRes = await fetch(
          `${TMDB_BASE}/genre/movie/list?api_key=${API_KEY}&language=en-US`
        );
        const genreJson = await genreRes.json();
        setGenres(genreJson.genres || []);

        const moviesRes = await fetch(
          `${TMDB_BASE}/discover/movie?api_key=${API_KEY}&language=en-US&sort_by=popularity.desc&page=1&include_adult=false`
        );
        const moviesJson = await moviesRes.json();
        setRawMovies(moviesJson.results || []);
      } catch (e) {
        console.error(e);
        setError("Failed to load movies from TMDB");
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  const genreMap = useMemo(() => {
    const map = {};
    genres.forEach((g) => {
      map[g.id] = g.name;
    });
    return map;
  }, [genres]);

  // normalize TMDB → our UI model
  const movies = useMemo(
    () =>
      rawMovies.map((m) => {
        const genreNames = (m.genre_ids || [])
          .map((id) => genreMap[id])
          .filter(Boolean);

        return {
          id: m.id,
          title: m.title || m.name,
          year: m.release_date ? m.release_date.slice(0, 4) : "—",
          genreLabel: genreNames.join(", ") || "Unknown",
          genreIds: m.genre_ids || [],
          language: m.original_language || "n/a",
          rating: m.vote_average ? m.vote_average.toFixed(1) : "0.0",
          voteCount: m.vote_count || 0,
          description: m.overview || "No description.",
          poster: m.poster_path ? `${IMG_BASE}${m.poster_path}` : "",
          isAnimation: (m.genre_ids || []).includes(16), // 16 = Animation
          isAwardWinningActor:
            (m.vote_average || 0) >= AWARD_MIN_RATING &&
            (m.vote_count || 0) >= AWARD_MIN_VOTES,
        };
      }),
    [rawMovies, genreMap]
  );

  const languages = useMemo(
    () => ["All", ...Array.from(new Set(movies.map((m) => m.language)))],
    [movies]
  );

  const genreFilters = useMemo(
    () => ["All", ...genres.map((g) => g.name)],
    [genres]
  );

  const filtered = useMemo(
    () =>
      movies.filter((m) => {
        if (activeSection === "genre") {
          if (activeGenre === "All") return true;
          return m.genreLabel.split(", ").includes(activeGenre);
        }

        if (activeSection === "award") {
          return m.isAwardWinningActor;
        }

        if (activeSection === "animation") {
          return m.isAnimation;
        }

        if (activeSection === "language") {
          if (language === "All") return true;
          return m.language === language;
        }

        return true;
      }),
    [movies, activeSection, activeGenre, language]
  );

  return (
    <div className="recommend-page">
      <section
        className="hero"
        style={{ backgroundImage: `url(${moodImage})` }}
      >
        <div className="hero-overlay" />
        <div className="hero-content">
          <h1>Movie Suggestions by Mood and Feeling</h1>
          <p className="muted">“I'm in the mood for something...”</p>

          <div className="chip-row">
            {sections.map((s) => (
              <button
                key={s.key}
                className={
                  "chip " + (activeSection === s.key ? "chip-active" : "")
                }
                onClick={() => setActiveSection(s.key)}
              >
                {s.label}
              </button>
            ))}
          </div>

          {activeSection === "genre" && (
            <div className="chip-row small-gap">
              {genreFilters.map((g) => (
                <button
                  key={g}
                  className={
                    "chip-outline " + (activeGenre === g ? "chip-active" : "")
                  }
                  onClick={() => setActiveGenre(g)}
                >
                  {g}
                </button>
              ))}
            </div>
          )}

          {activeSection === "language" && (
            <div className="chip-row small-gap">
              {languages.map((l) => (
                <button
                  key={l}
                  className={
                    "chip-outline " + (language === l ? "chip-active" : "")
                  }
                  onClick={() => setLanguage(l)}
                >
                  {l}
                </button>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="results-section">
        <h2>
          {activeSection === "genre" && `Genre: ${activeGenre}`}
          {activeSection === "award" && "Best actor award winning (high rated)"}
          {activeSection === "animation" && "Animation movies"}
          {activeSection === "language" && `Language: ${language}`}
        </h2>

        {loading && <p className="muted">Loading movies...</p>}
        {error && (
          <p className="muted" style={{ color: "red" }}>
            {error}
          </p>
        )}

        <div className="movie-grid">
          {filtered.map((m) => {
            const isAdded = Array.isArray(watchlist) &&
              watchlist.some((w) => w.tmdb_id === m.id || w.id === m.id);
            
            return (
              <article key={m.id} className="movie-card">
                {isAdded && <span className="tick-indicator">✔</span>}
                {m.poster && <img src={m.poster} alt={m.title} />}
                <div className="movie-body">
                  <h3>{m.title}</h3>
                  <p className="meta">
                    {m.genreLabel} · {m.year} · {m.language}
                  </p>
                  <p className="meta rating">⭐ {m.rating}</p>
                  <p className="desc">{m.description}</p>

                  <div className="card-actions">
                    <button
                      className={`btn-primary btn-watchlist ${isAdded ? 'added' : ''}`}
                      onClick={() => addToWatchlist(m)}
                      disabled={isAdded}
                    >
                      {isAdded ? '✓ Added' : '➕ Add to Watchlist'}
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
