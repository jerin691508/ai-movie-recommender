// src/App.jsx
import { createContext, useContext, useState, useCallback } from "react";
import { Routes, Route, Navigate, useNavigate, Link } from "react-router-dom";

import LoginPage from "./pages/LoginPage.jsx";
import RegisterPage from "./pages/RegisterPage.jsx";
import HomePage from "./pages/HomePage.jsx";
import WatchlistPage from "./pages/WatchlistPage.jsx";
import RecommendationPage from "./pages/RecommendationPage.jsx";
import AiRecommendationPage from "./pages/AiRecommendationPage.jsx";
import HistoryPage from "./pages/HistoryPage.jsx";
import RandomPage from "./pages/RandomPage.jsx";

const API_URL = "http://localhost:8000";

// -------- contexts --------
const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

const WatchlistContext = createContext(null);
export const useWatchlist = () => useContext(WatchlistContext);

const ToastContext = createContext(null);
export const useToast = () => useContext(ToastContext);
// --------------------------

function ProtectedRoute({ children, role }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (role && user.role !== role) return <Navigate to="/login" replace />;
  return children;
}

function ToastContainer() {
  const { toasts } = useToast();
  if (toasts.length === 0) return null;
  
  return (
    <div className="toast-container">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast ${toast.type}`}>
          <span className="toast-icon">{toast.type === 'success' ? '✓' : '✗'}</span>
          <span>{toast.message}</span>
        </div>
      ))}
    </div>
  );
}

function Layout({ children }) {
  const { user, logout } = useAuth();

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="logo">MovieReco</div>

        <nav className="nav-links">
          {/* public */}
          <Link to="/home">Home</Link>
          <Link to="/random">Random</Link>

          {/* only when logged in as normal user */}
          {user && user.role === "user" && (
            <>
              <Link to="/watchlist">Watchlist</Link>
              <Link to="/recommend">Recommendations</Link>
              <Link to="/ai">AI Recommendation</Link>
              <Link to="/history">History</Link>
            </>
          )}
        </nav>

        <div className="topbar-right">
          {!user && (
            <>
              <Link to="/login" className="btn-secondary">
                Login
              </Link>
              <Link to="/register" className="btn-primary">
                Sign up
              </Link>
            </>
          )}

          {user && (
            <>
              <span className="username">
                <svg
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  style={{
                    width: '16px',
                    height: '16px',
                    marginRight: '6px',
                    verticalAlign: 'middle',
                    display: 'inline-block'
                  }}
                >
                  <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                </svg>
                {user.username}
              </span>
              <button onClick={logout} className="btn-secondary">
                Logout
              </button>
            </>
          )}
        </div>
      </header>

      <ToastContainer />
      <main className="page">{children}</main>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [watchlist, setWatchlist] = useState([]);
  const [toasts, setToasts] = useState([]);
  const navigate = useNavigate();

  const addToast = useCallback((message, type = 'success') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 3000);
  }, []);

  const loadWatchlist = async (userId) => {
    if (!userId) return;
    try {
      const res = await fetch(`${API_URL}/watchlist/${userId}`);
      if (!res.ok) return;
      const data = await res.json();
      setWatchlist(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error("Failed to load watchlist", e);
    }
  };

  // userFromBackend = { id, username, email, role }
  const login = async (userFromBackend) => {
    setUser(userFromBackend);
    await loadWatchlist(userFromBackend.id);
    addToast("Login successful", "success");
    navigate("/home");
  };

  const logout = () => {
    setUser(null);
    setWatchlist([]);
    navigate("/home");
  };

  const addToWatchlist = async (movie) => {
    if (!user) {
      alert("Login to save movies to watchlist");
      return;
    }
    // Check if already in watchlist
    const exists = watchlist.some((w) => w.tmdb_id === movie.id || w.id === movie.id);
    if (exists) {
      return;
    }
    try {
      const res = await fetch(`${API_URL}/watchlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: user.id,
          tmdb_id: movie.id,
          title: movie.title,
          poster: movie.poster || null,
          year: movie.year || null,
          rating: movie.rating?.toString() || null,
          genreLabel: movie.genreLabel || null,
          language: movie.language || null,
          description: movie.description || null,
        }),
      });
      if (!res.ok) return;
      const saved = await res.json();
      setWatchlist((prev) =>
        prev.find((m) => m.id === saved.id) ? prev : [...prev, saved]
      );
    } catch (e) {
      console.error("Failed to add to watchlist", e);
    }
  };

  const removeFromWatchlist = async (itemId) => {
    if (!user) return;
    try {
      const res = await fetch(`${API_URL}/watchlist/${user.id}/${itemId}`, {
        method: "DELETE",
      });
      if (!res.ok) return;
      setWatchlist((prev) => prev.filter((m) => m.id !== itemId));
    } catch (e) {
      console.error("Failed to remove from watchlist", e);
    }
  };

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      <WatchlistContext.Provider
        value={{ watchlist, addToWatchlist, removeFromWatchlist }}
      >
        <ToastContext.Provider value={{ toasts, addToast }}>
          <Routes>
            {/* root shows home */}
            <Route
              path="/"
              element={
                <Layout>
                  <HomePage />
                </Layout>
              }
            />
            <Route
              path="/home"
              element={
                <Layout>
                  <HomePage />
                </Layout>
              }
            />
            <Route
              path="/random"
              element={
                <Layout>
                  <RandomPage />
                </Layout>
              }
            />
            <Route
              path="/login"
              element={
                <Layout>
                  <LoginPage />
                </Layout>
              }
            />
            <Route
              path="/register"
              element={
                <Layout>
                  <RegisterPage />
                </Layout>
              }
            />
            <Route
              path="/watchlist"
              element={
                <ProtectedRoute role="user">
                  <Layout>
                    <WatchlistPage />
                  </Layout>
                </ProtectedRoute>
              }
            />
            <Route
              path="/recommend"
              element={
                <ProtectedRoute role="user">
                  <Layout>
                    <RecommendationPage />
                  </Layout>
                </ProtectedRoute>
              }
            />
            <Route
              path="/ai"
              element={
                <ProtectedRoute role="user">
                  <Layout>
                    <AiRecommendationPage />
                  </Layout>
                </ProtectedRoute>
              }
            />
            <Route
              path="/history"
              element={
                <ProtectedRoute role="user">
                  <Layout>
                    <HistoryPage />
                  </Layout>
                </ProtectedRoute>
              }
            />
          </Routes>
        </ToastContext.Provider>
      </WatchlistContext.Provider>
    </AuthContext.Provider>
  );
}
