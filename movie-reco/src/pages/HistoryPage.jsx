// src/pages/HistoryPage.jsx
import { useEffect, useState } from "react";
import { useAuth } from "../App.jsx";

const API_URL = "http://localhost:8000";

export default function HistoryPage() {
  const { user } = useAuth();
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user) return;

    const fetchHistory = async () => {
      try {
        const res = await fetch(`${API_URL}/history/${user.id}`);
        if (!res.ok) throw new Error("Failed to fetch");
        const data = await res.json();
        setHistory(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error(err);
        setError("Failed to load history");
      }
    };

    fetchHistory();
  }, [user]);

  const clearHistory = async () => {
    if (!user) return;
    try {
      const res = await fetch(`${API_URL}/history/${user.id}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Failed to clear");
      setHistory([]);
    } catch (err) {
      console.error(err);
      setError("Failed to clear history");
    }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <div>
          <h1>🕒 AI Search History</h1>
          <p className="muted">Your previous movie recommendation prompts</p>
        </div>
        {history.length > 0 && (
          <button className="btn-secondary" onClick={clearHistory}>
            Clear Search History
          </button>
        )}
      </div>

      {error && <p style={{ color: "red" }}>{error}</p>}

      {history.length === 0 ? (
        <p className="muted">No AI history yet. Try using AI Recommendations.</p>
      ) : (
        <div className="history-container">
          {history.map((item) => (
            <div key={item.id} className="card" style={{ marginBottom: "1rem" }}>
              <p>
                <strong>Prompt:</strong> {item.prompt}
              </p>
              <p>
                <strong>Suggestions:</strong> {item.suggestions}
              </p>
              <small className="muted">{item.created_at}</small>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
