from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import random
from datetime import datetime
import difflib

app = Flask(__name__)
DATABASE = 'Popular_Games.db'  # Your database file

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn

# Updated MASTER QUERY including the prices table.
GAME_SELECT = """
SELECT
    g.game_id,
    g.title,
    g.genre,
    g.release_date,
    g.metacritic_score,
    g.description,
    d.name AS developer,
    pub.name AS publisher,
    ar.rating AS age_rating,
    ar.reason AS age_rating_reason,
    i.cover_image,
    i.image_url,
    i.image_url2,
    i.image_url3,
    pr.price AS price,
    pr.currency AS currency,
    p1.platform_name AS platform_name1,
    p2.platform_name AS platform_name2,
    p3.platform_name AS platform_name3,
    p4.platform_name AS platform_name4,
    p5.platform_name AS platform_name5,
    p6.platform_name AS platform_name6,
    p7.platform_name AS platform_name7,
    p8.platform_name AS platform_name8
FROM games g
JOIN developers d          ON g.developer_id  = d.developer_id
JOIN publishers pub        ON g.publisher_id  = pub.publisher_id
JOIN age_ratings ar        ON g.age_rating_id = ar.age_rating_id
JOIN images i              ON g.game_id       = i.game_id
LEFT JOIN game_platforms gp ON g.game_id       = gp.game_id
LEFT JOIN prices pr         ON g.game_id       = pr.game_id
LEFT JOIN platforms p1      ON gp.platform_id   = p1.platform_id
LEFT JOIN platforms p2      ON gp.platform_id2  = p2.platform_id
LEFT JOIN platforms p3      ON gp.platform_id3  = p3.platform_id
LEFT JOIN platforms p4      ON gp.platform_id4  = p4.platform_id
LEFT JOIN platforms p5      ON gp.platform_id5  = p5.platform_id
LEFT JOIN platforms p6      ON gp.platform_id6  = p6.platform_id
LEFT JOIN platforms p7      ON gp.platform_id7  = p7.platform_id
LEFT JOIN platforms p8      ON gp.platform_id8  = p8.platform_id
"""

@app.route('/')
def home():
    """Home page: Show all games with their prices and other info."""
    conn = get_db_connection()
    games = conn.execute(GAME_SELECT).fetchall()
    conn.close()
    return render_template("index.html", all_games=games)

@app.route('/search', methods=["GET", "POST"])
def search():
    """
    Multiple filter search route.
    The 'filter' hidden field indicates which filter is being used.
    Supports fuzzy text search, score filtering, date filtering, age rating filtering, and platform filtering.
    """
    conn = get_db_connection()
    # Retrieve lists for publishers and developers for hints.
    publishers = conn.execute("SELECT name FROM publishers").fetchall()
    developers = conn.execute("SELECT name FROM developers").fetchall()
    # For fuzzy text matching, get game titles, developer and publisher names.
    game_titles = [row["title"] for row in conn.execute("SELECT title FROM games").fetchall()]
    dev_names = [row["name"] for row in developers]
    pub_names = [row["name"] for row in publishers]

    row = conn.execute("SELECT MIN(metacritic_score) AS min_score FROM games").fetchone()
    min_score = row["min_score"] if row else 80  # Default minimum if none found
    all_platforms = conn.execute("SELECT platform_id, platform_name FROM platforms").fetchall()

    if request.method == "POST":
        filter_type = request.form.get("filter")
        query = GAME_SELECT + " WHERE 1=1 "
        params = []
        error = None

        if filter_type == "text":
            search_term = request.form.get("search_term", "").strip()
            if search_term:
                candidates = game_titles + dev_names + pub_names
                close_matches = difflib.get_close_matches(search_term, candidates, n=1, cutoff=0.6)
                if close_matches:
                    best_match = close_matches[0]
                    wildcard = f"%{best_match}%"
                else:
                    wildcard = f"%{search_term}%"
                query += """
                  AND (g.title LIKE ? COLLATE NOCASE
                       OR d.name LIKE ? COLLATE NOCASE
                       OR pub.name LIKE ? COLLATE NOCASE)
                """
                params.extend([wildcard, wildcard, wildcard])
            else:
                error = "Please enter a search term."

        elif filter_type == "score":
            score_min = request.form.get("score_min", "").strip()
            score_max = request.form.get("score_max", "").strip()
            try:
                if score_min:
                    query += " AND g.metacritic_score >= ? "
                    params.append(int(score_min))
                if score_max:
                    query += " AND g.metacritic_score <= ? "
                    params.append(int(score_max))
            except ValueError:
                error = "Invalid score values. Please enter numbers only (80-100)."

        elif filter_type == "date":
            date_min = request.form.get("date_min", "").strip()
            date_max = request.form.get("date_max", "").strip()
            try:
                if date_min and date_max:
                    date_min_obj = datetime.strptime(date_min, "%Y-%m-%d")
                    date_max_obj = datetime.strptime(date_max, "%Y-%m-%d")
                    allowed_min = datetime(2000, 1, 1)
                    allowed_max = datetime(2025, 1, 1)
                    if date_min_obj < allowed_min or date_max_obj > allowed_max:
                        error = "Dates must be between 2000-01-01 and 2025-01-01."
                    else:
                        query += " AND g.release_date >= ? AND g.release_date <= ? "
                        params.extend([date_min, date_max])
                else:
                    error = "Please provide both start and end dates."
            except ValueError:
                error = "Invalid date format. Use YYYY-MM-DD."

        elif filter_type == "age_rating":
            age_rating = request.form.get("age_rating", "").strip().upper()
            allowed_age_ratings = ["G", "PG", "M", "R13", "R16", "R18"]
            if age_rating and age_rating in allowed_age_ratings:
                query += " AND ar.rating = ? "
                params.append(age_rating)
            else:
                error = f"Invalid age rating. Allowed ratings: {', '.join(allowed_age_ratings)}."

        elif filter_type == "platform":
            selected_plats = request.form.getlist("platforms")
            if selected_plats:
                placeholders = ",".join("?" for _ in selected_plats)
                query += f"""
                  AND (
                    gp.platform_id  IN ({placeholders})
                    OR gp.platform_id2 IN ({placeholders})
                    OR gp.platform_id3 IN ({placeholders})
                    OR gp.platform_id4 IN ({placeholders})
                    OR gp.platform_id5 IN ({placeholders})
                    OR gp.platform_id6 IN ({placeholders})
                    OR gp.platform_id7 IN ({placeholders})
                    OR gp.platform_id8 IN ({placeholders})
                  )
                """
                for _ in range(8):
                    params.extend(selected_plats)
            else:
                error = "Please select at least one platform."

        if error:
            conn.close()
            return render_template("search.html", error=error,
                                   publishers=publishers,
                                   developers=developers,
                                   min_score=min_score,
                                   platforms=all_platforms)
        else:
            results = conn.execute(query, tuple(params)).fetchall()
            conn.close()
            return render_template("search_results.html",
                                   results=results,
                                   search_type=filter_type,
                                   search_value="")
    else:
        conn.close()
        return render_template("search.html",
                               publishers=publishers,
                               developers=developers,
                               min_score=min_score,
                               platforms=all_platforms)

@app.route("/game/<int:game_id>")
def game_detail(game_id):
    """Show details for a single game, including its price."""
    conn = get_db_connection()
    query = GAME_SELECT + " WHERE g.game_id = ?"
    game = conn.execute(query, (game_id,)).fetchone()
    conn.close()
    if not game:
        return "Game not found", 404
    return render_template("game_detail.html", game=game)

@app.route("/random")
def random_game():
    """Redirect to a random game's detail page."""
    conn = get_db_connection()
    games = conn.execute("SELECT game_id FROM games").fetchall()
    conn.close()
    if not games:
        return "No games in database", 404
    random_id = random.choice(games)["game_id"]
    return redirect(url_for("game_detail", game_id=random_id))

if __name__ == '__main__':
    app.run(debug=True)
