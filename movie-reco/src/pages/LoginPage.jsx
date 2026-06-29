// src/pages/LoginPage.jsx
import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../App.jsx";

const API_URL = "http://localhost:8000";

export default function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    try {
      const res = await fetch(`${API_URL}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        const d = data?.detail;
        const msg = typeof d === "string" ? d : "Invalid username or password";
        setError(msg);
        return;
      }

      // { id, username, email, role }
      login(data);
    } catch (err) {
      console.error(err);
      setError("Cannot reach server");
    }
  };

  return (
    <div className="center-container">
      <div className="card auth-card">
        <h1>Welcome Back 👋</h1>
        <p className="muted">Login to continue</p>

        <form onSubmit={handleSubmit} className="form">
          <label>Username</label>
          <input
            type="text"
            placeholder="your username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />

          <label>Password</label>
          <input
            type="password"
            placeholder="********"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />

          <button className="btn-primary" type="submit">
            Login
          </button>
        </form>

        {error && (
          <p className="muted small-text" style={{ color: "red" }}>
            {error}
          </p>
        )}

        <p className="muted small-text">
          Don't have an account? <Link to="/register">Sign Up</Link>
        </p>
      </div>
    </div>
  );
}
