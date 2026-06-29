// src/pages/RegisterPage.jsx
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useToast } from "../App.jsx";

const API_URL = "http://localhost:8000";

export default function RegisterPage() {
  const navigate = useNavigate();
  const { addToast } = useToast();

  const [form, setForm] = useState({
    username: "",
    email: "",
    password: "",
    confirm: "",
  });
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleChange = (e) =>
    setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    // Frontend validation
    if (!form.username || form.username.trim().length === 0) {
      setError("Username cannot be empty");
      return;
    }

    if (form.username.trim().length < 3) {
      setError("Username must be at least 3 characters");
      return;
    }

    if (!form.password || form.password.length === 0) {
      setError("Password cannot be empty");
      return;
    }

    if (form.password.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }

    if (form.password !== form.confirm) {
      setError("Passwords do not match");
      return;
    }

    setIsSubmitting(true);

    try {
      const res = await fetch(`${API_URL}/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: form.username,
          email: form.email,
          password: form.password,
          confirm_password: form.confirm, // must match backend
        }),
      });

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        let msg = "Registration failed";
        const d = data?.detail;
        if (typeof d === "string") msg = d;
        else if (Array.isArray(d) && d[0]?.msg) msg = d[0].msg;
        setError(msg);
        setIsSubmitting(false);
        return;
      }

      addToast("User registered successfully", "success");
      setTimeout(() => {
        navigate("/login");
      }, 2000);
    } catch (err) {
      console.error(err);
      setError("Cannot reach server");
      setIsSubmitting(false);
    }
  };

  return (
    <div className="center-container">
      <div className="card auth-card">
        <h1>Create Account ✨</h1>

        <form onSubmit={handleSubmit} className="form">
          <label>Username</label>
          <input
            name="username"
            value={form.username}
            onChange={handleChange}
            required
          />

          <label>Email</label>
          <input
            type="email"
            name="email"
            value={form.email}
            onChange={handleChange}
            required
          />

          <label>Password</label>
          <input
            type="password"
            name="password"
            value={form.password}
            onChange={handleChange}
            required
          />

          <label>Confirm Password</label>
          <input
            type="password"
            name="confirm"
            value={form.confirm}
            onChange={handleChange}
            required
          />

          <button className="btn-primary" type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Creating Account..." : "Sign Up"}
          </button>
        </form>

        {error && (
          <p className="muted small-text" style={{ color: "red" }}>
            {error}
          </p>
        )}

        <p className="muted small-text">
          Already have an account? <Link to="/">Login</Link>
        </p>
      </div>
    </div>
  );
}
