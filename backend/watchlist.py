# backend/watchlist.py
from fastapi import Depends, HTTPException
from pydantic import BaseModel
from db import get_db
import sqlite3

class WatchItem(BaseModel):
    user_id: int
    movie_id: int
    title: str
    poster: str | None = None
    year: str | None = None
    rating: str | None = None
    description: str | None = None


def register_watchlist_routes(app):
    @app.post("/watchlist/add")
    def add_watchlist(item: WatchItem, db: sqlite3.Connection = Depends(get_db)):
        db.execute(
            """
            INSERT OR IGNORE INTO watchlist (user_id, movie_id, title, poster, year, rating, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (item.user_id, item.movie_id, item.title, item.poster, item.year, item.rating, item.description)
        )
        db.commit()
        return {"status": "added"}

    @app.get("/watchlist/{user_id}")
    def get_watchlist(user_id: int, db: sqlite3.Connection = Depends(get_db)):
        cur = db.execute("SELECT * FROM watchlist WHERE user_id = ?", (user_id,))
        return cur.fetchall()

    @app.delete("/watchlist/remove/{user_id}/{movie_id}")
    def remove_watchlist(user_id: int, movie_id: int, db: sqlite3.Connection = Depends(get_db)):
        db.execute("DELETE FROM watchlist WHERE user_id = ? AND movie_id = ?", (user_id, movie_id))
        db.commit()
        return {"status": "removed"}
