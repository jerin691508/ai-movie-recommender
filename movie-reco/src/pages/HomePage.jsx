// src/pages/HomePage.jsx
import { useNavigate } from "react-router-dom";
import { useAuth } from "../App.jsx";
import heroImg from "../assets/home-hero.jpg"; // your collage image

export default function HomePage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const handleStartRandom = () => navigate("/random");
  const handleStartAI = () => navigate("/ai");

  const handleStartRecommend = () => navigate("/recommend");

  const handleStartWatchlist = () => {
    if (!user) navigate("/login");
    else navigate("/watchlist");
  };

  const handleAuthClick = () => navigate(user ? "/home" : "/login");

  return (
    <div className="home-landing" style={{ backgroundImage: `url(${heroImg})` }}>
      <div className="home-landing-overlay" />

      <div className="home-landing-inner">
        {/* LEFT: Hero text + buttons */}
        <section className="home-landing-hero">
          <p className="badge">MovieReco · Smart movie discovery</p>

          <h1>
            Stop scrolling. <br />
            <span className="accent">Start watching.</span>
          </h1>

          <p className="hero-subtitle">
            Get instant random picks, AI-powered suggestions, and a personal
            watchlist. All in one place and powered by live TMDB data.
          </p>

          <div className="hero-buttons">
            <button className="btn-primary large" onClick={handleStartRandom}>
              🎲 Random movie
            </button>
            <button className="btn-ghost large" onClick={handleStartAI}>
              🤖 Ask AI
            </button>
          </div>

          <div className="hero-secondary-actions">
            <button className="link-button" onClick={handleStartRecommend}>
              Browse by mood &raquo;
            </button>
            <button className="link-button" onClick={handleStartWatchlist}>
              Open my watchlist &raquo;
            </button>
          </div>

          {!user && (
            <p className="hero-auth-hint">
              New here?{" "}
              <button className="link-inline" onClick={handleAuthClick}>
                Login or create an account to save movies.
              </button>
            </p>
          )}
        </section>

        {/* RIGHT: Feature cards */}
        <section className="home-landing-panel">
          <div className="feature-grid">
            <div className="feature-card">
              <h3>🎲 Random picks</h3>
              <p>
                One click gives you a highly-rated movie (7.0+), any genre,
                any year.
              </p>
            </div>
            <div className="feature-card">
              <h3>🤖 AI recommendations</h3>
              <p>
                Describe your mood or favourite film. Phi-3 + TMDB find similar
                gems.
              </p>
            </div>
            <div className="feature-card">
              <h3>📌 Personal watchlist</h3>
              <p>
                Save movies you like and come back later. Stored safely in the
                database for your account.
              </p>
            </div>
          </div>

          <div className="chip-row home-moods">
            <span className="chip-pill">Feel-good</span>
            <span className="chip-pill">Mind-blowing</span>
            <span className="chip-pill">Romantic</span>
            <span className="chip-pill">Thriller</span>
            <span className="chip-pill">Animation</span>
          </div>

          <div className="stats-row">
            <div className="stat-block">
              <span className="stat-number">7.0+</span>
              <span className="stat-label">TMDB rating filter</span>
            </div>
            <div className="stat-block">
              <span className="stat-number">AI</span>
              <span className="stat-label">Ollama Phi-3 powered</span>
            </div>
            <div className="stat-block">
              <span className="stat-number">24/7</span>
              <span className="stat-label">Local recommendations</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
