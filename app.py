import sqlite3
import random
from datetime import datetime
import difflib
import re # For email validation
from flask import Flask, render_template, request, redirect, url_for, session, flash, g # Added g for app context
from werkzeug.security import generate_password_hash, check_password_hash
import os # For generating a secure secret key

app = Flask(__name__)

# --- Flask Secret Key for Sessions ---
# IMPORTANT: In a production environment, generate a strong, *static*, and secret key.
# For development, os.urandom(24) is convenient but will change on each restart.
# Replace 'your_super_secret_key_here' with a unique, long string for deployment.
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your_super_secret_key_here') # Use environment variable if available

# --- Database Paths ---
POPULAR_GAMES_DATABASE = 'Popular_Games.db' # Your existing games database
USER_DATABASE = 'user_data.db' # New database for user specific data

# --- Database Connection Functions ---

def get_popular_games_db():
    """
    Establishes a connection to the Popular_Games.db database.
    Stores the connection in Flask's global 'g' object to reuse it within a request.
    Configures the connection to return rows as sqlite3.Row objects,
    allowing column access by name (e.g., row['title']). This is crucial for robust column retrieval.
    """
    db = getattr(g, '_popular_games_database', None)
    if db is None:
        db = g._popular_games_database = sqlite3.connect(POPULAR_GAMES_DATABASE)
        db.row_factory = sqlite3.Row # Enable dictionary-like access to columns
    return db

def get_user_db():
    """
    Establishes a connection to the user_data.db database.
    Stores the connection in Flask's global 'g' object to reuse it within a request.
    Configures the connection to return rows as sqlite3.Row objects.
    """
    db = getattr(g, '_user_database', None)
    if db is None:
        db = g._user_database = sqlite3.connect(USER_DATABASE)
        db.row_factory = sqlite3.Row # Enable dictionary-like access to columns
    return db

def create_user_table():
    """
    Initializes the user data database with necessary tables:
    - 'users' table: Stores user authentication details (username, hashed password, email, DOB).
    - 'user_game_list' table: Stores which games a user has added to their personal list.
    This function is called once on application startup or within a @app.before_request context.
    """
    conn = get_user_db()
    cursor = conn.cursor() # Get a cursor object for executing SQL commands

    # Create 'users' table with username, password hash, email, and date of birth (dob)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,  -- Added email field
            dob TEXT                     -- Date of Birth in YYYY-MM-DD format
        )
    ''')

    # Create 'user_game_list' table to store games associated with each user
    # This acts as a many-to-many relationship table between users and games.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_game_list (
            user_id INTEGER NOT NULL,
            game_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, game_id), -- Composite primary key to prevent duplicate entries
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            -- No FOREIGN KEY for game_id because it's in a different database (Popular_Games.db).
            -- We rely on the game_id existing in Popular_Games.db for data integrity.
        )
    ''')
    conn.commit() # Commit the changes to the database
    print("User database (user_data.db) initialized successfully!")

# This function ensures all open database connections are closed at the end of each request
@app.teardown_appcontext
def close_db_connections(exception):
    """
    Closes database connections that were opened during the request.
    This is registered as a teardown function, meaning it runs after each request,
    regardless of whether an exception occurred.
    """
    db_pop_games = getattr(g, '_popular_games_database', None)
    if db_pop_games is not None:
        db_pop_games.close()
    db_user = getattr(g, '_user_database', None)
    if db_user is not None:
        db_user.close()
    # If you had other databases, you would close them here too.

# This runs before each request to ensure tables are created
# This is a good place for initial setup that needs to happen for every user session
@app.before_request
def before_request_setup():
    """
    This function runs before every incoming request.
    It ensures that the 'users' and 'user_game_list' tables exist in user_data.db.
    This provides robustness, especially during development or initial deployment.
    """
    create_user_table()


# --- SQL Query Definitions ---

# A comprehensive SELECT statement to fetch all relevant game details from Popular_Games.db
# This query was adapted from your provided structure. Note the multiple LEFT JOINs for platforms.
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
JOIN developers d                   ON g.developer_id   = d.developer_id
JOIN publishers pub                 ON g.publisher_id   = pub.publisher_id
JOIN age_ratings ar                 ON g.age_rating_id  = ar.age_rating_id
JOIN images i                       ON g.game_id        = i.game_id
LEFT JOIN prices pr                 ON g.game_id        = pr.game_id
LEFT JOIN game_platforms gp         ON g.game_id        = gp.game_id -- Join to the game_platforms linking table
LEFT JOIN platforms p1              ON gp.platform_id   = p1.platform_id
LEFT JOIN platforms p2              ON gp.platform_id2  = p2.platform_id
LEFT JOIN platforms p3              ON gp.platform_id3  = p3.platform_id
LEFT JOIN platforms p4              ON gp.platform_id4  = p4.platform_id
LEFT JOIN platforms p5              ON gp.platform_id5  = p5.platform_id
LEFT JOIN platforms p6              ON gp.platform_id6  = p6.platform_id
LEFT JOIN platforms p7              ON gp.platform_id7  = p7.platform_id
LEFT JOIN platforms p8              ON gp.platform_id8  = p8.platform_id
"""

# --- Flask Routes ---

@app.route('/')
def home():
    """
    Home page route.
    Displays a list of all games from the Popular_Games.db database.
    """
    conn = get_popular_games_db()
    games = conn.execute(GAME_SELECT).fetchall()
    # The connection is automatically closed by @app.teardown_appcontext
    return render_template("index.html", all_games=games)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handles user registration.
    - GET: Displays the registration form.
    - POST: Processes the registration form submission.
      - Validates input (all fields, password match, email format, unique username/email).
      - Hashes the password for security.
      - Inserts new user data into the 'users' table.
      - Uses Flask's 'flash' messaging for user feedback.
    """
    if 'user_id' in session: # If user is already logged in, redirect them
        flash('You are already logged in.', 'info')
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].lower().strip() # Standardize email to lowercase
        password = request.form['password'].strip()
        confirm_password = request.form['confirm_password'].strip()
        dob = request.form['dob'].strip() # Date of Birth in YYYY-MM-DD format

        # Input Validation
        if not username or not email or not password or not confirm_password or not dob:
            flash('All fields are required!', 'error')
            return render_template('register.html')
        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return render_template('register.html')
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email): # Simple email regex validation
            flash('Invalid email address format!', 'error')
            return render_template('register.html')
        
        # Basic password strength (can be expanded)
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('register.html')

        user_db = get_user_db()
        try:
            # Check for existing username or email to ensure uniqueness
            existing_user = user_db.execute("SELECT id FROM users WHERE username = ? OR email = ?",
                                            (username, email)).fetchone()
            if existing_user:
                flash('Username or Email already exists. Please choose a different one.', 'error')
                return render_template('register.html')

            hashed_password = generate_password_hash(password)
            user_db.execute("INSERT INTO users (username, password, email, dob) VALUES (?, ?, ?, ?)",
                            (username, hashed_password, email, dob))
            user_db.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.Error as e:
            # Catch general database errors (e.g., if the table creation somehow failed earlier)
            print(f"Database error during registration: {e}")
            flash(f'An unexpected error occurred during registration: {e}', 'error')
            user_db.rollback() # Rollback changes on error
        finally:
            user_db.close() # Ensure connection is closed by teardown, but good practice for immediate close

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles user login.
    - GET: Displays the login form.
    - POST: Processes the login form submission.
      - Authenticates user by username OR email.
      - Verifies password using hashing.
      - Sets up session variables ('user_id', 'username') upon successful login.
      - Uses Flask's 'flash' messaging for user feedback.
    """
    if 'user_id' in session: # If user is already logged in, redirect them
        flash('You are already logged in.', 'info')
        return redirect(url_for('home'))

    if request.method == 'POST':
        identifier = request.form['identifier'].lower().strip() # Can be username or email
        password = request.form['password'].strip()

        if not identifier or not password:
            flash('Username/Email and password are required!', 'error')
            return render_template('login.html')

        user_db = get_user_db()
        # Search for user by either username or email
        user = user_db.execute("SELECT * FROM users WHERE username = ? OR email = ?",
                               (identifier, identifier)).fetchone()
        user_db.close() # Ensure connection is closed

        if user and check_password_hash(user['password'], password):
            # Login successful: Store user info in session
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash(f'Welcome, {user["username"]}!', 'success')
            return redirect(url_for('my_games')) # Redirect to user's game list on successful login
        else:
            flash('Invalid username/email or password.', 'error')
            return render_template('login.html') # Stay on login page with error

    return render_template('login.html')

@app.route('/logout')
def logout():
    """
    Logs out the current user by clearing session variables.
    Flashes a confirmation message.
    """
    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/profile')
def profile():
    """
    Displays the logged-in user's profile information.
    Retrieves user details from the 'users' table.
    Allows for future profile updates (handled by separate POST routes).
    """
    if 'user_id' not in session:
        flash('Please log in to view your profile.', 'info')
        return redirect(url_for('login'))

    user_db = get_user_db()
    user = user_db.execute("SELECT id, username, email, dob FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    user_db.close()

    if not user:
        flash('User not found. Please log in again.', 'error')
        session.pop('user_id', None) # Clear invalid session
        session.pop('username', None)
        return redirect(url_for('login'))

    return render_template('profile.html', user=user)

@app.route('/update_dob', methods=['POST'])
def update_dob():
    """
    Handles updating the user's date of birth.
    Requires user to be logged in. Validates the DOB format.
    """
    if 'user_id' not in session:
        flash('Please log in to update your profile.', 'info')
        return redirect(url_for('login'))

    new_dob = request.form.get('dob').strip()
    user_id = session['user_id']

    if not new_dob:
        flash('Date of Birth cannot be empty.', 'error')
        return redirect(url_for('profile'))

    # Basic date format validation (YYYY-MM-DD)
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", new_dob):
        flash('Invalid date format. Please use YYYY-MM-DD.', 'error')
        return redirect(url_for('profile'))

    user_db = get_user_db()
    try:
        user_db.execute("UPDATE users SET dob = ? WHERE id = ?", (new_dob, user_id))
        user_db.commit()
        flash('Date of Birth updated successfully!', 'success')
    except sqlite3.Error as e:
        print(f"Database error updating DOB: {e}")
        flash(f'An unexpected error occurred: {e}', 'error')
        user_db.rollback()
    finally:
        user_db.close()
    return redirect(url_for('profile'))

@app.route('/change_password', methods=['POST'])
def change_password():
    """
    Handles changing the user's password.
    Requires user to be logged in. Validates old password and new password match.
    """
    if 'user_id' not in session:
        flash('Please log in to change your password.', 'info')
        return redirect(url_for('login'))

    old_password = request.form.get('old_password').strip()
    new_password = request.form.get('new_password').strip()
    confirm_new_password = request.form.get('confirm_new_password').strip()
    user_id = session['user_id']

    user_db = get_user_db()
    user = user_db.execute("SELECT password FROM users WHERE id = ?", (user_id,)).fetchone()

    if not user:
        flash('User not found. Please log in again.', 'error')
        session.pop('user_id', None)
        session.pop('username', None)
        user_db.close()
        return redirect(url_for('login'))

    if not old_password or not new_password or not confirm_new_password:
        flash('All password fields are required.', 'error')
        user_db.close()
        return redirect(url_for('profile'))

    if not check_password_hash(user['password'], old_password):
        flash('Incorrect old password.', 'error')
        user_db.close()
        return redirect(url_for('profile'))

    if new_password != confirm_new_password:
        flash('New passwords do not match.', 'error')
        user_db.close()
        return redirect(url_for('profile'))
    
    if len(new_password) < 6:
        flash('New password must be at least 6 characters long.', 'error')
        user_db.close()
        return redirect(url_for('profile'))

    try:
        hashed_new_password = generate_password_hash(new_password)
        user_db.execute("UPDATE users SET password = ? WHERE id = ?", (hashed_new_password, user_id))
        user_db.commit()
        flash('Password updated successfully!', 'success')
    except sqlite3.Error as e:
        print(f"Database error changing password: {e}")
        flash(f'An unexpected error occurred: {e}', 'error')
        user_db.rollback()
    finally:
        user_db.close()
    return redirect(url_for('profile'))


@app.route('/search', methods=["GET", "POST"])
def search():
    """
    Multiple filter search route.
    Handles text (fuzzy), score, date, age rating, and platform filtering.
    Displays search results on a separate page (`search_results.html`).
    """
    conn = get_popular_games_db()
    # Retrieve lists for publishers and developers for hints in the search form.
    publishers = conn.execute("SELECT name FROM publishers").fetchall()
    developers = conn.execute("SELECT name FROM developers").fetchall()
    
    # For fuzzy text matching, get relevant names.
    game_titles = [row["title"] for row in conn.execute("SELECT title FROM games").fetchall()]
    dev_names = [row["name"] for row in developers]
    pub_names = [row["name"] for row in publishers]

    # Get min/max score from DB for range input defaults
    row = conn.execute("SELECT MIN(metacritic_score) AS min_score, MAX(metacritic_score) AS max_score FROM games").fetchone()
    min_score = row["min_score"] if row and row["min_score"] is not None else 0
    max_score = row["max_score"] if row and row["max_score"] is not None else 100
    
    all_platforms = conn.execute("SELECT platform_id, platform_name FROM platforms ORDER BY platform_name").fetchall()

    results = [] # Initialize results list
    search_type = None # Initialize search_type

    if request.method == "POST":
        filter_type = request.form.get("filter")
        query = GAME_SELECT + " WHERE 1=1 " # Start with a true condition for easy AND additions
        params = []
        error = None

        if filter_type == "text":
            search_term = request.form.get("search_term", "").strip()
            if search_term:
                candidates = game_titles + dev_names + pub_names
                # Use difflib for fuzzy matching, cutoff can be adjusted
                close_matches = difflib.get_close_matches(search_term, candidates, n=1, cutoff=0.6)
                best_match = close_matches[0] if close_matches else search_term
                wildcard = f"%{best_match}%"
                
                query += """
                    AND (g.title LIKE ? COLLATE NOCASE
                        OR d.name LIKE ? COLLATE NOCASE
                        OR pub.name LIKE ? COLLATE NOCASE
                        OR g.genre LIKE ? COLLATE NOCASE) -- Added genre to text search
                    """
                params.extend([wildcard, wildcard, wildcard, wildcard])
                search_type = "text"
            else:
                error = "Please enter a search term."

        elif filter_type == "score":
            score_min = request.form.get("score_min", "").strip()
            score_max = request.form.get("score_max", "").strip()
            try:
                min_val = int(score_min) if score_min else min_score
                max_val = int(score_max) if score_max else max_score

                if not (0 <= min_val <= 100 and 0 <= max_val <= 100 and min_val <= max_val):
                    error = "Score values must be between 0 and 100, and min score cannot exceed max score."
                else:
                    query += " AND g.metacritic_score >= ? AND g.metacritic_score <= ? "
                    params.extend([min_val, max_val])
                    search_type = "score"
            except ValueError:
                error = "Invalid score values. Please enter numbers only."

        elif filter_type == "date":
            date_min = request.form.get("date_min", "").strip()
            date_max = request.form.get("date_max", "").strip()
            try:
                # Basic date format validation and range check
                if date_min and date_max:
                    date_min_obj = datetime.strptime(date_min, "%Y-%m-%d")
                    date_max_obj = datetime.strptime(date_max, "%Y-%m-%d")
                    
                    # Example allowed range; adjust as per your data
                    allowed_min = datetime(1980, 1, 1) # Games pre-2000 are common
                    allowed_max = datetime.now() # Up to current date

                    if not (allowed_min <= date_min_obj <= date_max_obj <= allowed_max):
                        error = f"Dates must be between {allowed_min.strftime('%Y-%m-%d')} and {allowed_max.strftime('%Y-%m-%d')}, and start date cannot be after end date."
                    else:
                        query += " AND g.release_date BETWEEN ? AND ? "
                        params.extend([date_min, date_max])
                        search_type = "date"
                else:
                    error = "Please provide both start and end dates."
            except ValueError:
                error = "Invalid date format. Use YYYY-MM-DD."

        elif filter_type == "age_rating":
            age_rating = request.form.get("age_rating", "").strip().upper()
            allowed_age_ratings = ["G", "PG", "M", "R13", "R16", "R18"] # Based on NZ ratings
            if age_rating and age_rating in allowed_age_ratings:
                query += " AND ar.rating = ? "
                params.append(age_rating)
                search_type = "age_rating"
            else:
                error = f"Invalid age rating. Allowed ratings: {', '.join(allowed_age_ratings)}."

        elif filter_type == "platform":
            selected_plats_ids = request.form.getlist("platforms") # Get platform IDs
            if selected_plats_ids:
                # Construct conditions for each platform_id column
                platform_conditions = []
                for i in range(1, 9): # platform_id to platform_id8
                    platform_conditions.append(f"gp.platform_id{'' if i == 1 else i} IN ({','.join('?' * len(selected_plats_ids))})")
                
                query += " AND (" + " OR ".join(platform_conditions) + ")"
                
                # Extend params for each platform_id column condition
                for _ in range(8): # Duplicate selected_plats_ids 8 times as per your existing query structure
                    params.extend(selected_plats_ids)
                search_type = "platform"
            else:
                error = "Please select at least one platform."

        if error:
            flash(error, 'error') # Flash error messages
            # If error, re-render the search form with previous values (optional, but good UX)
            return render_template("search.html",
                                   publishers=publishers,
                                   developers=developers,
                                   min_score=min_score,
                                   max_score=max_score,
                                   platforms=all_platforms)
        else:
            try:
                results = conn.execute(query, tuple(params)).fetchall()
                # Process results to combine platforms into a list
                processed_results = []
                for game_row in results:
                    game_dict = dict(game_row) # Convert Row to dict for easier manipulation
                    platforms_list = []
                    for i in range(1, 9):
                        platform_key = f'platform_name{"" if i == 1 else i}'
                        if game_dict.get(platform_key):
                            platforms_list.append(game_dict[platform_key])
                            del game_dict[platform_key] # Remove individual platform keys
                    game_dict['platforms_display'] = list(set(platforms_list)) # Use set to remove duplicates, then convert to list
                    processed_results.append(game_dict)
                
                return render_template("search_results.html",
                                       results=processed_results,
                                       search_type=filter_type)
            except sqlite3.Error as e:
                flash(f"Database error during search: {e}", 'error')
                return render_template("search.html",
                                       publishers=publishers,
                                       developers=developers,
                                       min_score=min_score,
                                       max_score=max_score,
                                       platforms=all_platforms)
    
    # Initial GET request for search page
    # The connection is automatically closed by @app.teardown_appcontext
    return render_template("search.html",
                           publishers=publishers,
                           developers=developers,
                           min_score=min_score,
                           max_score=max_score,
                           platforms=all_platforms)

@app.route('/game/<int:game_id>')
def game_detail(game_id):
    """
    Displays detailed information for a specific game.
    Includes a check to see if the game is already in the logged-in user's list
    to provide real-time UI feedback for the 'Add to My List' button.

    Args:
        game_id (int): The unique identifier of the game to display.

    Returns:
        flask.render_template: Renders the game_detail.html page with game data
                               and a flag indicating if the game is in the user's list.
        flask.redirect: Redirects to home if the game_id is invalid.
    """
    popular_games_db = get_popular_games_db()
    
    # Use the comprehensive GAME_SELECT to fetch all details
    query = GAME_SELECT + " WHERE g.game_id = ?"
    game_row = popular_games_db.execute(query, (game_id,)).fetchone()

    if not game_row:
        flash('Game not found.', 'error')
        return redirect(url_for('home'))
    
    # Process game_row to consolidate platform names
    game = dict(game_row)
    platforms_list = []
    for i in range(1, 9):
        platform_key = f'platform_name{"" if i == 1 else i}'
        if game.get(platform_key):
            platforms_list.append(game[platform_key])
            del game[platform_key] # Clean up individual platform keys
    game['platforms_display'] = list(set(platforms_list)) # Remove duplicates

    is_game_in_user_list = False
    if 'user_id' in session:
        user_id = session['user_id']
        user_db = get_user_db()
        entry = user_db.execute("SELECT 1 FROM user_game_list WHERE user_id = ? AND game_id = ?",
                                 (user_id, game_id)).fetchone()
        if entry:
            is_game_in_user_list = True
        # user_db connection will be closed by teardown_appcontext

    return render_template("game_detail.html", game=game, is_game_in_user_list=is_game_in_user_list)

@app.route("/random")
def random_game():
    """
    Redirects to a random game's detail page.
    Selects a random game_id from the Popular_Games.db.
    """
    conn = get_popular_games_db()
    games = conn.execute("SELECT game_id FROM games").fetchall()
    if not games:
        flash("No games available in the database.", 'warning')
        return redirect(url_for('home'))
    random_id = random.choice(games)["game_id"]
    return redirect(url_for("game_detail", game_id=random_id))


@app.route('/my_games')
def my_games():
    """
    Displays the logged-in user's personal list of games.
    Retrieves game IDs from user_data.db and then fetches full game details
    from Popular_Games.db based on those IDs.
    Requires user to be logged in.
    """
    if 'user_id' not in session:
        flash('Please log in to view your game list.', 'info')
        return redirect(url_for('login'))

    user_id = session['user_id']
    user_db = get_user_db()
    # Fetch game IDs associated with the current user
    game_id_rows = user_db.execute("SELECT game_id FROM user_game_list WHERE user_id = ?", (user_id,)).fetchall()
    game_ids = [row['game_id'] for row in game_id_rows] # Access by column name 'game_id'
    
    if not game_ids: # If the user has no games in their list
        return render_template('my_games.html', user_games=[])

    popular_games_db = get_popular_games_db()
    placeholders = ','.join('?' * len(game_ids))
    
    # Query Popular_Games.db to get full game details for the collected IDs
    query = f"{GAME_SELECT} WHERE g.game_id IN ({placeholders})"
    games_data_rows = popular_games_db.execute(query, game_ids).fetchall()
    
    # Process fetched rows to consolidate platforms and map to expected display names
    user_games = []
    for g_row in games_data_rows:
        game_dict = dict(g_row) # Convert Row to dict
        platforms_list = []
        for i in range(1, 9):
            platform_key = f'platform_name{"" if i == 1 else i}'
            if game_dict.get(platform_key):
                platforms_list.append(game_dict[platform_key])
        
        user_games.append({
            'game_id': game_dict['game_id'],
            'title': game_dict['title'],
            'genre': game_dict['genre'],
            'platforms_display': list(set(platforms_list)), # Use 'platforms_display'
            'release_date': game_dict['release_date'],
            'age_rating': game_dict['age_rating'],
            'publisher': game_dict['publisher'],
            'developer': game_dict['developer'],
            'metacritic_score': game_dict['metacritic_score'],
            'description': game_dict['description'] # Include description if needed
        })

    return render_template('my_games.html', user_games=user_games)

@app.route('/add_to_list/<int:game_id>', methods=['POST'])
def add_to_list(game_id):
    """
    Adds a specified game to the logged-in user's personal game list.
    Includes validation for game existence in Popular_Games.db and prevents duplicate entries.
    Flashes messages for success or error.
    """
    if 'user_id' not in session:
        flash('Please log in to add games to your list.', 'info')
        return redirect(url_for('login'))

    user_id = session['user_id']

    popular_games_db = get_popular_games_db()
    # Check if the game_id actually exists in the main games database
    game_exists = popular_games_db.execute("SELECT 1 FROM games WHERE game_id = ?", (game_id,)).fetchone()
    
    if not game_exists:
        flash('Game not found. Cannot add to your list.', 'error')
        return redirect(url_for('search')) # Redirect to search if game not valid

    user_db = get_user_db()
    try:
        # Check if the game is already in the user's list to prevent duplicate entries.
        existing_entry = user_db.execute("SELECT 1 FROM user_game_list WHERE user_id = ? AND game_id = ?",
                                         (user_id, game_id)).fetchone()
        if existing_entry:
            flash('This game is already in your list!', 'warning')
            return redirect(url_for('my_games')) # Redirect to the user's game list
        else:
            # Insert the user_id and game_id into the user_game_list table.
            user_db.execute("INSERT INTO user_game_list (user_id, game_id) VALUES (?, ?)",
                            (user_id, game_id))
            user_db.commit()
            flash('Game added to your list successfully!', 'success')
    except sqlite3.Error as e:
        print(f"Database error adding game to list: {e}")
        flash(f'An unexpected error occurred: {e}', 'error')
        user_db.rollback() # Rollback changes on error
    # The database connections will be closed by @app.teardown_appcontext

    # If the game was successfully added, redirect back to its detail page.
    return redirect(url_for('game_detail', game_id=game_id))

@app.route('/remove_from_list/<int:game_id>', methods=['POST'])
def remove_from_list(game_id):
    """
    Removes a game from the logged-in user's personal game list.
    Requires user to be logged in.
    """
    if 'user_id' not in session:
        flash('Please log in to remove games from your list.', 'info')
        return redirect(url_for('login'))

    user_id = session['user_id']
    user_db = get_user_db()
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
        print(f"Database error removing game from list: {e}")
        flash(f'An unexpected error occurred: {e}', 'error')
        user_db.rollback()
    # The database connection will be closed by @app.teardown_appcontext
    
    return redirect(url_for('my_games')) # Always redirect to the user's game list after removal


# --- Application Entry Point ---
if __name__ == '__main__':
    # Ensure the user database and its tables are created when the application starts
    # This block runs only when app.py is executed directly (e.g., `python app.py`)
    with app.app_context():
        create_user_table() # This will ensure user_data.db is set up
    app.run(debug=True) # Run the Flask development server in debug mode