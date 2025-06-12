# app.py

import sqlite3
import random
from datetime import datetime
import difflib
from flask import Flask, render_template, request, redirect, url_for, session, flash # Added session, flash
from werkzeug.security import generate_password_hash, check_password_hash # Added for password hashing
import os # Added for secret key generation

app = Flask(__name__)

# --- Database Paths ---
# Your existing games database
POPULAR_GAMES_DATABASE = 'Popular_Games.db'
# New database for user specific data (will be created in the same directory as app.py)
USER_DATABASE = 'user_data.db'

# --- Flask Secret Key for Sessions ---
# IMPORTANT: In a production environment, generate a strong, static key
# and store it securely (e.g., environment variable). For development, os.urandom(24) is fine.
app.secret_key = os.urandom(24)

# --- Database Connection Functions ---

def get_popular_games_db():
    """Connects to the existing popular games database."""
    conn = sqlite3.connect(POPULAR_GAMES_DATABASE)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn

def get_user_db():
    """Connects to the new user data database."""
    conn = sqlite3.connect(USER_DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_user_db():
    """Initializes the user data database with necessary tables."""
    with app.app_context(): # Ensure we are in the Flask app context
        user_db = get_user_db()
        cursor = user_db.cursor()
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                dob TEXT -- Date of Birth in YYYY-MM-DD format
            )
        ''')
        # Create user_game_list table to store games associated with each user
        # This will link to game IDs from POPULAR_GAMES.db
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_game_list (
                user_id INTEGER NOT NULL,
                game_id INTEGER NOT NULL,
                PRIMARY KEY (user_id, game_id),
                FOREIGN KEY (user_id) REFERENCES users(id)
                -- No FOREIGN KEY for game_id because it's in a different database.
                -- We rely on the game_id existing in POPULAR_GAMES.db
            )
        ''')
        user_db.commit()
        print("User database initialized successfully!")

# Call init_user_db() when the application starts
# This ensures tables are created if they don't exist
with app.app_context():
    init_user_db()


# Your existing GAME_SELECT query (no changes needed here)
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
LEFT JOIN platforms p1      ON gp.platform_id  = p1.platform_id
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
    conn = get_popular_games_db() # Use the specific function
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
    conn = get_popular_games_db() # Use the specific function
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
                # Duplicate selected_plats 8 times as per your existing query structure
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
    conn = get_popular_games_db() # Use the specific function
    query = GAME_SELECT + " WHERE g.game_id = ?"
    game = conn.execute(query, (game_id,)).fetchone()
    conn.close()
    if not game:
        return "Game not found", 404
    # Check if user is logged in to show "Add to My List" button
    # This uses the session, which is an advanced technique (modifying data stored in collections)
    return render_template("game_detail.html", game=game, logged_in='username' in session)

@app.route("/random")
def random_game():
    """Redirect to a random game's detail page."""
    conn = get_popular_games_db() # Use the specific function
    games = conn.execute("SELECT game_id FROM games").fetchall()
    conn.close()
    if not games:
        return "No games in database", 404
    random_id = random.choice(games)["game_id"]
    return redirect(url_for("game_detail", game_id=random_id))
# app.py (add this section somewhere after your @app.route('/register') function)

# --- User Authentication & Management Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    print("--- Login Route Accessed ---") # Debug print
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        print(f"Attempting login for username: '{username}'") # Debug print

        if not username or not password:
            flash('Username and password are required!', 'error')
            print("Validation: Username or password missing.") # Debug print
            return render_template('login.html')

        user_db = get_user_db()
        user = user_db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        user_db.close()

        if user:
            print(f"User '{username}' found in DB. Stored hash: {user['password']}") # Debug print
            print(f"Entered password: '{password}'") # Debug print
            if check_password_hash(user['password'], password):
                print("Password check: SUCCESS!") # Debug print
                session['user_id'] = user['id']
                session['username'] = user['username']
                flash('Logged in successfully!', 'success')
                print(f"Session after login: user_id={session.get('user_id')}, username={session.get('username')}") # Debug print
                return redirect(url_for('home'))
            else:
                print("Password check: FAILED.") # Debug print
                flash('Invalid username or password.', 'error')
        else:
            print("User NOT found in DB.") # Debug print
            flash('Invalid username or password.', 'error')

    print(f"Rendering login.html. Current session username: {session.get('username', 'None')}") # Debug print
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logs out the current user."""
    # This part will be implemented in a later commit
    session.pop('user_id', None) # Remove user_id from session
    session.pop('username', None) # Remove username from session
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    """Displays user profile and handles updates."""
    if 'user_id' not in session:
        flash('Please log in to view your profile.', 'info')
        return redirect(url_for('login'))

    user_db = get_user_db()
    user = user_db.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    user_db.close()

    if not user:
        flash('User not found. Please log in again.', 'error')
        session.pop('user_id', None)
        session.pop('username', None)
        return redirect(url_for('login'))

    # POST requests for profile page will be handled by specific update routes like /update_dob, /change_password
    return render_template('profile.html', user=user)


@app.route('/update_dob', methods=['POST'])
def update_dob():
    """Handles updating the user's date of birth."""
    if 'user_id' not in session:
        flash('Please log in to update your profile.', 'info')
        return redirect(url_for('login'))

    # This part will be implemented in a later commit
    flash('Date of birth update logic to be implemented.', 'warning') # Placeholder
    return redirect(url_for('profile'))

@app.route('/change_password', methods=['POST'])
def change_password():
    """Handles changing the user's password."""
    if 'user_id' not in session:
        flash('Please log in to change your password.', 'info')
        return redirect(url_for('login'))

    # This part will be implemented in a later commit
    flash('Password change logic to be implemented.', 'warning') # Placeholder
    return redirect(url_for('profile'))


@app.route('/my_games')
def my_games():
    """Displays the current user's list of games."""
    if 'user_id' not in session:
        flash('Please log in to view your game list.', 'info')
        return redirect(url_for('login'))

    user_db = get_user_db()
    user_id = session['user_id']
    game_ids = user_db.execute("SELECT game_id FROM user_game_list WHERE user_id = ?", (user_id,)).fetchall()
    user_db.close()

    # Extract game_ids into a list
    game_id_list = [row['game_id'] for row in game_ids]

    user_games = []
    if game_id_list:
        # Construct a query to fetch full game details from POPULAR_GAMES.db
        # This will use the game_id from the user's list
        placeholders = ','.join('?' for _ in game_id_list)
        popular_games_db = get_popular_games_db()
        # Use the master GAME_SELECT query but filter by game_id
        game_query = GAME_SELECT + f" WHERE g.game_id IN ({placeholders})"
        user_games = popular_games_db.execute(game_query, tuple(game_id_list)).fetchall()
        popular_games_db.close()

    return render_template('my_games.html', user_games=user_games)

@app.route('/add_to_list/<int:game_id>', methods=['GET', 'POST'])
def add_to_list(game_id):
    """Adds a game to the logged-in user's list."""
    if 'user_id' not in session:
        flash('Please log in to add games to your list.', 'info')
        return redirect(url_for('login'))

    user_db = get_user_db()
    user_id = session['user_id']
    try:
        # Check if the game is already in the list
        existing_entry = user_db.execute("SELECT 1 FROM user_game_list WHERE user_id = ? AND game_id = ?",
                                         (user_id, game_id)).fetchone()
        if existing_entry:
            flash('This game is already in your list!', 'warning')
        else:
            user_db.execute("INSERT INTO user_game_list (user_id, game_id) VALUES (?, ?)",
                            (user_id, game_id))
            user_db.commit()
            flash('Game added to your list!', 'success')
    except sqlite3.Error as e:
        flash(f'An error occurred: {e}', 'error')
        user_db.rollback()
    finally:
        user_db.close()
    return redirect(url_for('game_detail', game_id=game_id))


@app.route('/remove_from_list/<int:game_id>', methods=['POST'])
def remove_from_list(game_id):
    """Removes a game from the logged-in user's list."""
    if 'user_id' not in session:
        flash('Please log in to remove games from your list.', 'info')
        return redirect(url_for('login'))

    user_db = get_user_db()
    user_id = session['user_id']
    try:
        cursor = user_db.cursor()
        cursor.execute("DELETE FROM user_game_list WHERE user_id = ? AND game_id = ?",
                       (user_id, game_id))
        if cursor.rowcount > 0: # Check if any row was deleted
            user_db.commit()
            flash('Game removed from your list!', 'success')
        else:
            flash('Game not found in your list.', 'warning')
    except sqlite3.Error as e:
        flash(f'An error occurred: {e}', 'error')
        user_db.rollback()
    finally:
        user_db.close()
    return redirect(url_for('my_games')) # Redirect to the user's game list
@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles user registration."""
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        dob = request.form['dob'].strip() # Date of Birth

        # Basic validation
        if not username or not password or not dob:
            flash('All fields are required!', 'error')
            return render_template('register.html')

        # --- Advanced Technique: Modifying data stored in collections (Hashing password) ---
        # Hashing the password before storing it is crucial for security.
        hashed_password = generate_password_hash(password)

        user_db = get_user_db() # Get connection to user_data.db
        cursor = user_db.cursor()
        try:
            # Insert the new user into the 'users' table
            cursor.execute("INSERT INTO users (username, password, dob) VALUES (?, ?, ?)",
                           (username, hashed_password, dob))
            user_db.commit() # Save changes to the database
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login')) # Redirect to login page after successful registration
        except sqlite3.IntegrityError:
            # This error occurs if a UNIQUE constraint is violated (e.g., duplicate username)
            flash('Username already exists. Please choose a different one.', 'error')
            user_db.rollback() # Discard changes if there was an error
        finally:
            user_db.close() # Always close the database connection
    # If it's a GET request, or if there was an error on POST, render the registration form
    return render_template('register.html')



# --- NEW ROUTES WILL GO HERE IN SUBSEQUENT COMMITS ---
# Placeholder for new routes for register, login, my_games, profile, etc.

if __name__ == '__main__':
    # init_user_db() # We call this once globally now via app.app_context()
    app.run(debug=True)

    # Existing home route, now slightly modified to show session access