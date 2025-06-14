from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import sqlite3
import difflib
import random
import re

# Flask app setup
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_change_this_in_production'  # REMEMBER TO USE A STRONG, UNIQUE KEY
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database file paths
USER_DATABASE = 'user_data.db'
POPULAR_GAMES_DATABASE = 'Popular_Games.db'

# SQLAlchemy Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    dob = db.Column(db.String(10), nullable=False)

    # Relationship to UserGame model (if you have one)
    # user_games = db.relationship('UserGame', backref='user', lazy=True)

    def __repr__(self):
        return '<User %r>' % self.username

class UserGame(db.Model):
    __tablename__ = 'user_game'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    game_id = db.Column(db.Integer, nullable=False)
    
    # Ensure unique combinations of user_id and game_id
    __table_args__ = (db.UniqueConstraint('user_id', 'game_id', name='unique_user_game'),)

# Database connection functions
def get_user_db():
    """
    Establishes a connection to the user_data.db database.
    Stores the connection in Flask's global 'g' object to reuse it within a request.
    Configures the connection to return rows as sqlite3.Row objects.
    """
    db_conn = getattr(g, '_user_database', None)
    if db_conn is None:
        db_conn = g._user_database = sqlite3.connect(USER_DATABASE)
        db_conn.row_factory = sqlite3.Row  # Enable dictionary-like access to columns
    return db_conn

def get_popular_games_db():
    """
    Establishes a connection to the Popular_Games.db database.
    Stores the connection in Flask's global 'g' object to reuse it within a request.
    Configures the connection to return rows as sqlite3.Row objects.
    """
    db_conn = getattr(g, '_popular_games_database', None)
    if db_conn is None:
        db_conn = g._popular_games_database = sqlite3.connect(POPULAR_GAMES_DATABASE)
        db_conn.row_factory = sqlite3.Row
    return db_conn

def create_user_table():
    """
    Initializes the user data database with necessary tables:
    - 'users' table: Stores user authentication details (username, hashed password, email, DOB).
    - 'user_game_list' table: Stores which games a user has added to their personal list.
    This function is called once on application startup or within a @app.before_request context.
    """
    conn = get_user_db()
    cursor = conn.cursor()  # Get a cursor object for executing SQL commands

    # Create 'users' table with username, password hash, email, and date of birth (dob)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            dob TEXT
        )
    ''')

    # Create 'user_game_list' table to store games associated with each user
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_game_list (
            user_id INTEGER NOT NULL,
            game_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, game_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    conn.commit()  # Commit the changes to the database
    print("User database (user_data.db) initialized successfully!")

# Database connection cleanup
@app.teardown_appcontext
def close_db_connections(exception):
    """
    Closes database connections that were opened during the request.
    """
    db_pop_games = getattr(g, '_popular_games_database', None)
    if db_pop_games is not None:
        db_pop_games.close()
    db_user = getattr(g, '_user_database', None)
    if db_user is not None:
        db_user.close()

# Setup before each request
@app.before_request
def before_request_setup():
    """
    This function runs before every incoming request.
    It ensures that the 'users' and 'user_game_list' tables exist in user_data.db.
    """
    create_user_table()

# SQL Query Definitions
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
JOIN developers d ON g.developer_id = d.developer_id
JOIN publishers pub ON g.publisher_id = pub.publisher_id
JOIN age_ratings ar ON g.age_rating_id = ar.age_rating_id
JOIN images i ON g.game_id = i.game_id
LEFT JOIN prices pr ON g.game_id = pr.game_id
LEFT JOIN game_platforms gp ON g.game_id = gp.game_id
LEFT JOIN platforms p1 ON gp.platform_id = p1.platform_id
LEFT JOIN platforms p2 ON gp.platform_id2 = p2.platform_id
LEFT JOIN platforms p3 ON gp.platform_id3 = p3.platform_id
LEFT JOIN platforms p4 ON gp.platform_id4 = p4.platform_id
LEFT JOIN platforms p5 ON gp.platform_id5 = p5.platform_id
LEFT JOIN platforms p6 ON gp.platform_id6 = p6.platform_id
LEFT JOIN platforms p7 ON gp.platform_id7 = p7.platform_id
LEFT JOIN platforms p8 ON gp.platform_id8 = p8.platform_id
"""

# Flask Routes
@app.route('/')
def home():
    """
    Home page route.
    Displays a list of all games from the Popular_Games.db database.
    """
    conn = get_popular_games_db()
    games = conn.execute(GAME_SELECT).fetchall()
    return render_template("index.html", all_games=games)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handles user registration using raw SQL instead of SQLAlchemy ORM.
    """
    if request.method == 'POST':
        # Use .get() method instead of direct key access to avoid KeyError
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        dob = request.form.get('dob', '').strip()

        # Basic validation
        if not username or not email or not password or not dob:
            flash('All fields are required!', 'danger')
            return redirect(url_for('register'))

        # Simple email format validation
        if '@' not in email or '.' not in email:
            flash('Please enter a valid email address.', 'danger')
            return redirect(url_for('register'))

        # Check if username OR email already exists
        user_db = get_user_db()
        existing_user_by_username = user_db.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        existing_user_by_email = user_db.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()

        if existing_user_by_username:
            flash('Username already exists. Please choose a different one.', 'danger')
            return redirect(url_for('register'))
        if existing_user_by_email:
            flash('Email address is already registered. Please use a different one or log in.', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        
        try:
            user_db.execute(
                "INSERT INTO users (username, email, password, dob) VALUES (?, ?, ?, ?)",
                (username, email, hashed_password, dob)
            )
            user_db.commit()
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.Error as e:
            user_db.rollback()
            flash(f'An unexpected error occurred during registration. Please try again.', 'danger')
            print(f"Registration Error: {e}")

    return render_template('register.html')

# Also add this debug route temporarily to see what's being sent:
@app.route('/debug_form', methods=['POST'])
def debug_form():
    """
    Temporary debug route to see what form data is being sent
    """
    print("Form data received:")
    for key, value in request.form.items():
        print(f"  {key}: {value}")
    
    print("Request method:", request.method)
    print("Content type:", request.content_type)
    
    return "Debug info printed to console"

# ... (rest of your app.py code above this, including imports, app setup, models, and seeding) ...

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        flash('You are already logged in.', 'info')
        return redirect(url_for('home'))

    if request.method == 'POST':
        # This single field will accept either username or email
        identifier = request.form['username'] # The input field will still be named 'username'
        password = request.form['password']

        # Attempt to find user by either username OR email
        user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()

        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username # Store username in session
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid username/email or password.', 'danger')
            return redirect(url_for('login'))
            
    return render_template('login.html')

# ... (rest of your app.py code below this) ...
@app.route('/logout')
def logout():
    """
    Logs out the current user by clearing session variables.
    """
    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/profile')
def profile():
    """
    Displays the logged-in user's profile information.
    """
    if 'user_id' not in session:
        flash('Please log in to view your profile.', 'info')
        return redirect(url_for('login'))

    user_db = get_user_db()
    user = user_db.execute(
        "SELECT id, username, email, dob FROM users WHERE id = ?", 
        (session['user_id'],)
    ).fetchone()

    if not user:
        flash('User not found. Please log in again.', 'error')
        session.pop('user_id', None)
        session.pop('username', None)
        return redirect(url_for('login'))

    return render_template('profile.html', user=user)

@app.route('/update_dob', methods=['POST'])
def update_dob():
    """
    Handles updating the user's date of birth.
    """
    if 'user_id' not in session:
        flash('Please log in to update your profile.', 'info')
        return redirect(url_for('login'))

    new_dob = request.form.get('dob', '').strip()
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
        flash('An unexpected error occurred.', 'error')
        user_db.rollback()
    
    return redirect(url_for('profile'))

@app.route('/change_password', methods=['POST'])
def change_password():
    """
    Handles changing the user's password.
    """
    if 'user_id' not in session:
        flash('Please log in to change your password.', 'info')
        return redirect(url_for('login'))

    old_password = request.form.get('old_password', '').strip()
    new_password = request.form.get('new_password', '').strip()
    confirm_new_password = request.form.get('confirm_new_password', '').strip()
    user_id = session['user_id']

    user_db = get_user_db()
    user = user_db.execute("SELECT password FROM users WHERE id = ?", (user_id,)).fetchone()

    if not user:
        flash('User not found. Please log in again.', 'error')
        session.pop('user_id', None)
        session.pop('username', None)
        return redirect(url_for('login'))

    if not old_password or not new_password or not confirm_new_password:
        flash('All password fields are required.', 'error')
        return redirect(url_for('profile'))

    if not check_password_hash(user['password'], old_password):
        flash('Incorrect old password.', 'error')
        return redirect(url_for('profile'))

    if new_password != confirm_new_password:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('profile'))
    
    if len(new_password) < 6:
        flash('New password must be at least 6 characters long.', 'error')
        return redirect(url_for('profile'))

    try:
        hashed_new_password = generate_password_hash(new_password)
        user_db.execute("UPDATE users SET password = ? WHERE id = ?", (hashed_new_password, user_id))
        user_db.commit()
        flash('Password updated successfully!', 'success')
    except sqlite3.Error as e:
        print(f"Database error changing password: {e}")
        flash('An unexpected error occurred.', 'error')
        user_db.rollback()
    
    return redirect(url_for('profile'))

@app.route('/search', methods=["GET", "POST"])
def search():
    """
    Multiple filter search route.
    """
    conn = get_popular_games_db()
    publishers = conn.execute("SELECT name FROM publishers").fetchall()
    developers = conn.execute("SELECT name FROM developers").fetchall()
    
    game_titles = [row["title"] for row in conn.execute("SELECT title FROM games").fetchall()]
    dev_names = [row["name"] for row in developers]
    pub_names = [row["name"] for row in publishers]

    row = conn.execute("SELECT MIN(metacritic_score) AS min_score, MAX(metacritic_score) AS max_score FROM games").fetchone()
    min_score = row["min_score"] if row and row["min_score"] is not None else 0
    max_score = row["max_score"] if row and row["max_score"] is not None else 100
    
    all_platforms = conn.execute("SELECT platform_id, platform_name FROM platforms ORDER BY platform_name").fetchall()

    results = []
    search_type = None

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
                best_match = close_matches[0] if close_matches else search_term
                wildcard = f"%{best_match}%"
                
                query += """
                    AND (g.title LIKE ? COLLATE NOCASE
                        OR d.name LIKE ? COLLATE NOCASE
                        OR pub.name LIKE ? COLLATE NOCASE
                        OR g.genre LIKE ? COLLATE NOCASE)
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
                if date_min and date_max:
                    date_min_obj = datetime.strptime(date_min, "%Y-%m-%d")
                    date_max_obj = datetime.strptime(date_max, "%Y-%m-%d")
                    
                    allowed_min = datetime(1980, 1, 1)
                    allowed_max = datetime.now()

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
            allowed_age_ratings = ["G", "PG", "M", "R13", "R16", "R18"]
            if age_rating and age_rating in allowed_age_ratings:
                query += " AND ar.rating = ? "
                params.append(age_rating)
                search_type = "age_rating"
            else:
                error = f"Invalid age rating. Allowed ratings: {', '.join(allowed_age_ratings)}."

        elif filter_type == "platform":
            selected_plats_ids = request.form.getlist("platforms")
            if selected_plats_ids:
                platform_conditions = []
                for i in range(1, 9):
                    platform_conditions.append(f"gp.platform_id{'' if i == 1 else i} IN ({','.join('?' * len(selected_plats_ids))})")
                
                query += " AND (" + " OR ".join(platform_conditions) + ")"
                
                for _ in range(8):
                    params.extend(selected_plats_ids)
                search_type = "platform"
            else:
                error = "Please select at least one platform."

        if error:
            flash(error, 'error')
            return render_template("search.html",
                                   publishers=publishers,
                                   developers=developers,
                                   min_score=min_score,
                                   max_score=max_score,
                                   platforms=all_platforms)
        else:
            try:
                results = conn.execute(query, tuple(params)).fetchall()
                processed_results = []
                for game_row in results:
                    game_dict = dict(game_row)
                    platforms_list = []
                    for i in range(1, 9):
                        platform_key = f'platform_name{"" if i == 1 else i}'
                        if game_dict.get(platform_key):
                            platforms_list.append(game_dict[platform_key])
                            del game_dict[platform_key]
                    game_dict['platforms_display'] = list(set(platforms_list))
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
    """
    popular_games_db = get_popular_games_db()
    
    query = GAME_SELECT + " WHERE g.game_id = ?"
    game_row = popular_games_db.execute(query, (game_id,)).fetchone()

    if not game_row:
        flash('Game not found.', 'error')
        return redirect(url_for('home'))
    
    game = dict(game_row)
    platforms_list = []
    for i in range(1, 9):
        platform_key = f'platform_name{"" if i == 1 else i}'
        if game.get(platform_key):
            platforms_list.append(game[platform_key])
            del game[platform_key]
    game['platforms_display'] = list(set(platforms_list))

    is_game_in_user_list = False
    if 'user_id' in session:
        user_id = session['user_id']
        user_db = get_user_db()
        entry = user_db.execute("SELECT 1 FROM user_game_list WHERE user_id = ? AND game_id = ?",
                                 (user_id, game_id)).fetchone()
        if entry:
            is_game_in_user_list = True

    return render_template("game_detail.html", game=game, is_game_in_user_list=is_game_in_user_list)

@app.route("/random")
def random_game():
    """
    Redirects to a random game's detail page.
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
    """
    if 'user_id' not in session:
        flash('Please log in to view your game list.', 'info')
        return redirect(url_for('login'))

    user_id = session['user_id']
    user_db = get_user_db()
    game_id_rows = user_db.execute("SELECT game_id FROM user_game_list WHERE user_id = ?", (user_id,)).fetchall()
    game_ids = [row['game_id'] for row in game_id_rows]
    
    if not game_ids:
        return render_template('my_games.html', user_games=[])

    popular_games_db = get_popular_games_db()
    placeholders = ','.join('?' * len(game_ids))
    
    query = f"{GAME_SELECT} WHERE g.game_id IN ({placeholders})"
    games_data_rows = popular_games_db.execute(query, game_ids).fetchall()
    
    user_games = []
    for g_row in games_data_rows:
        game_dict = dict(g_row)
        platforms_list = []
        for i in range(1, 9):
            platform_key = f'platform_name{"" if i == 1 else i}'
            if game_dict.get(platform_key):
                platforms_list.append(game_dict[platform_key])
        
        user_games.append({
            'game_id': game_dict['game_id'],
            'title': game_dict['title'],
            'genre': game_dict['genre'],
            'platforms_display': list(set(platforms_list)),
            'release_date': game_dict['release_date'],
            'age_rating': game_dict['age_rating'],
            'publisher': game_dict['publisher'],
            'developer': game_dict['developer'],
            'metacritic_score': game_dict['metacritic_score'],
            'description': game_dict['description']
        })

    return render_template('my_games.html', user_games=user_games)

@app.route('/add_to_list/<int:game_id>', methods=['POST'])
def add_to_list(game_id):
    """
    Adds a specified game to the logged-in user's personal game list.
    """
    if 'user_id' not in session:
        flash('Please log in to add games to your list.', 'info')
        return redirect(url_for('login'))

    user_id = session['user_id']

    popular_games_db = get_popular_games_db()
    game_exists = popular_games_db.execute("SELECT 1 FROM games WHERE game_id = ?", (game_id,)).fetchone()
    
    if not game_exists:
        flash('Game not found. Cannot add to your list.', 'error')
        return redirect(url_for('search'))

    user_db = get_user_db()
    try:
        existing_entry = user_db.execute("SELECT 1 FROM user_game_list WHERE user_id = ? AND game_id = ?",
                                         (user_id, game_id)).fetchone()
        if existing_entry:
            flash('This game is already in your list!', 'warning')
            return redirect(url_for('my_games'))
        else:
            user_db.execute("INSERT INTO user_game_list (user_id, game_id) VALUES (?, ?)",
                            (user_id, game_id))
            user_db.commit()
            flash('Game added to your list successfully!', 'success')
    except sqlite3.Error as e:
        print(f"Database error adding game to list: {e}")
        flash('An unexpected error occurred.', 'error')
        user_db.rollback()

    return redirect(url_for('game_detail', game_id=game_id))

@app.route('/remove_from_list/<int:game_id>', methods=['POST'])
def remove_from_list(game_id):
    """
    Removes a game from the logged-in user's personal game list.
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
        if cursor.rowcount > 0:
            user_db.commit()
            flash('Game removed from your list!', 'success')
        else:
            flash('Game not found in your list.', 'warning')
    except sqlite3.Error as e:
        print(f"Database error removing game from list: {e}")
        flash('An unexpected error occurred.', 'error')
        user_db.rollback()
    
    return redirect(url_for('my_games'))

# Application Entry Point
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create SQLAlchemy tables
        create_user_table()  # Create raw SQL tables
    app.run(debug=True)