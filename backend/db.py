import sqlite3

DB_PATH = "app.db"


def get_connection():
    # one connection for each request
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # users table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        );
        """
    )

# watchlist table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tmdb_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            poster TEXT,
            year TEXT,
            rating TEXT,
            genre_label TEXT,
            language TEXT,
            description TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
    )

    # movie memory (for AI history) 
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS movie_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            prompt TEXT NOT NULL,
            suggestions TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
    )

    conn.commit()
    conn.close()
    




    