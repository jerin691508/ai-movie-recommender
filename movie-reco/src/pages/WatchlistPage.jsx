import { useWatchlist } from "../App.jsx";

export default function WatchlistPage() {
  const { watchlist, removeFromWatchlist } = useWatchlist();

  return (
    <div>
      <h1>Your watchlist</h1>
      {watchlist.length === 0 && <p className="muted">No movies saved.</p>}

      <div className="movie-grid">
        {watchlist.map((m) => (
          <article key={m.id} className="movie-card">
            {m.poster && <img src={m.poster} alt={m.title} />}
            <div className="movie-body">
              <h3>{m.title}</h3>
              <p className="meta">
                {m.genreLabel || "Movie"} · {m.year || "—"} · {m.language || ""}
              </p>
              <p className="meta rating">⭐ {m.rating || "—"}</p>
              <p className="desc">{m.description}</p>
              <button
                className="btn-secondary full"
                onClick={() => removeFromWatchlist(m.id)}
              >
                Remove
              </button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
