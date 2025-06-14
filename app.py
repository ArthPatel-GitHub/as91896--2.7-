from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
import sqlite3
import difflib
import random
import re # This is the library used for regular expressions

# --- Flask Application Setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_very_long_and_random_secret_key_for_production_use' # CHANGE THIS IN PRODUCTION!
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///user_information.db' # SQLAlchemy will manage this database
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- External Database Paths (for Popular Games, read-only) ---
POPULAR_GAMES_DATABASE = 'Popular_Games.db' # This database will still be accessed directly via sqlite3

# --- Database Models (managed by Flask-SQLAlchemy) ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    dob = db.Column(db.String(10), nullable=True) # YYYY-MM-DD string

    user_games_entries = db.relationship('UserGame', backref='user', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<User {self.username}>'

class UserGame(db.Model):
    # This model represents a user's personal game list entry
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    game_id = db.Column(db.Integer, nullable=False) # Store the game_id from Popular_Games.db
    date_added = db.Column(db.DateTime, default=datetime.utcnow) # Track when the game was added

    # Ensure unique combinations of user_id and game_id
    __table_args__ = (db.UniqueConstraint('user_id', 'game_id', name='unique_user_game'),)

    def __repr__(self):
        return f'<UserGame UserID:{self.user_id} GameID:{self.game_id}>'


# --- Database connection functions for Popular_Games.db (read-only) ---
def get_popular_games_db():
    """
    Establishes a connection to the Popular_Games.db database.
    Stores the connection in Flask's global 'g' object to reuse it within a request.
    Configures the connection to return rows as sqlite3.Row objects.
    """
    db_conn = getattr(g, '_popular_games_database', None)
    if db_conn is None:
        db_conn = g._popular_games_database = sqlite3.connect(POPULAR_GAMES_DATABASE)
        db_conn.row_factory = sqlite3.Row  # Enable dictionary-like access to columns
    return db_conn

# Database connection cleanup for Popular_Games.db
@app.teardown_appcontext
def close_db_connections(exception):
    """
    Closes database connections that were opened during the request.
    This specifically closes the connection to Popular_Games.db.
    SQLAlchemy connections are managed automatically.
    """
    db_pop_games = getattr(g, '_popular_games_database', None)
    if db_pop_games is not None:
        db_pop_games.close()

# --- Setup for SQLAlchemy (to create tables for User and UserGame) ---
with app.app_context():
    db.create_all() # This creates tables for User and UserGame in database.db

# --- Context Processor for Global Variables (e.g., datetime for footer) ---
@app.before_request
def before_request():
    g.datetime = datetime

# --- Utility functions ---
def is_valid_email(email):
    """
    Simple email validation using regex.
    """
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_pattern, email) is not None

def calculate_age(dob_str):
    """Calculates age from a YYYY-MM-DD date string."""
    try:
        birth_date = datetime.strptime(dob_str, "%Y-%m-%d").date()
        today = date.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        return age
    except ValueError:
        return None # Invalid date format

# Function to check password strength (new)
def is_strong_password(password):
    """
    Checks if a password meets complexity requirements:
    - At least 8 characters long
    - Contains at least one uppercase letter
    - Contains at least one lowercase letter
    - Contains at least one digit
    - Contains at least one special character (e.g., !@#$%^&*()_+-=[]{};':"|,.<>/?`~)
    """
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"|,.<>/?`~]", password):
        return False
    return True

# Function to validate username (new)
def is_valid_username(username):
    """
    Checks if a username contains only alphanumeric characters and underscores.
    - Between 3 and 20 characters long.
    """
    if not 3 <= len(username) <= 20:
        return False
    # Only allow letters, numbers, and underscores
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        return False
    return True

# --- SQL Query Definitions for Popular_Games.db ---
# Note: The original query assumes `game_platforms` links to 8 platform_id columns.
# This is an unusual schema. If `game_platforms` has a game_id and a single platform_id
# column for a many-to-many relationship, this query needs adjustment.
# I'm keeping it as is based on your provided original.
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
# --- Flask Routes ---
@app.route('/')
def home():
    """
    Home page route.
    Displays a list of all games from the Popular_Games.db database.
    """
    conn = get_popular_games_db()
    games = conn.execute(GAME_SELECT).fetchall()
    
    processed_games = []
    for game_row in games:
        game_dict = dict(game_row)
        platforms_list = []
        # Collect platforms from potentially multiple platform_nameX columns
        for i in range(1, 9):
            platform_key = f'platform_name{"" if i == 1 else i}'
            if game_dict.get(platform_key):
                platforms_list.append(game_dict[platform_key])
        game_dict['platforms_display'] = list(set(platforms_list)) # Remove duplicates
        processed_games.append(game_dict)

    return render_template("index.html", all_games=processed_games)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if session.get('user_id'):
        flash('You are already logged in.', 'info')
        return redirect(url_for('home'))

    # Get today's date for use in the template to set max attribute for DOB input
    today_date_str = date.today().strftime('%Y-%m-%d')

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        dob = request.form.get('dob', '').strip()

        # Validation
        if not username or not email or not password or not confirm_password or not dob:
            flash('All fields are required!', 'danger')
            return redirect(url_for('register'))

        # Refinement: Username validation
        if not is_valid_username(username):
            flash('Username must be 3-20 characters long and contain only letters, numbers, and underscores.', 'danger')
            return redirect(url_for('register'))

        if not is_valid_email(email):
            flash('Please enter a valid email address.', 'danger')
            return redirect(url_for('register'))

        # Refinement: Password complexity validation
        if not is_strong_password(password):
            flash('Password must be at least 8 characters long and include uppercase, lowercase, numbers, and special characters.', 'danger')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))

        # Validate DOB format and minimum/maximum age
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", dob):
            flash('Invalid date format. Please use YYYY-MM-DD.', 'danger')
            return redirect(url_for('register'))
        
        try:
            birth_date_obj = datetime.strptime(dob, "%Y-%m-%d").date()
            current_date = date.today()
            min_dob_allowed = date(1925, 1, 1) # Nothing before 1925
        except ValueError:
            flash('Invalid date of birth provided. Please use a valid date.', 'danger')
            return redirect(url_for('register'))

        if birth_date_obj > current_date:
            flash('Date of birth cannot be in the future.', 'danger')
            return redirect(url_for('register'))

        if birth_date_obj < min_dob_allowed:
            flash(f'Date of birth cannot be before {min_dob_allowed.year}.', 'danger')
            return redirect(url_for('register'))

        user_age = calculate_age(dob)
        if user_age is None:
            flash('Invalid date of birth provided.', 'danger')
            return redirect(url_for('register'))
        elif user_age < 13: # Example: Minimum age requirement
            flash('You must be at least 13 years old to register.', 'danger')
            return redirect(url_for('register'))

        # Check if username or email already exists using SQLAlchemy
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing_user:
            if existing_user.username == username:
                flash('Username already exists. Please choose a different one.', 'danger')
            else: # existing_user.email == email
                flash('Email already exists. Please use a different one or log in.', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, email=email, password_hash=hashed_password, dob=dob)

        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback() # Rollback in case of any database error
            flash(f'An unexpected error occurred during registration. Please try again. Error: {str(e)}', 'danger')
            print(f"Registration Error: {e}") # Log the error for debugging

    return render_template('register.html', today_date_str=today_date_str)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        flash('You are already logged in.', 'info')
        return redirect(url_for('home'))

    if request.method == 'POST':
        username_or_email = request.form.get('username_or_email', '').strip()
        password = request.form.get('password', '').strip()

        if not username_or_email or not password:
            flash('Username/Email and Password are required!', 'danger')
            return redirect(url_for('login'))

        # Find user by either username or email using SQLAlchemy
        user = User.query.filter(
            (User.username == username_or_email) | (User.email == username_or_email)
        ).first()

        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['email'] = user.email
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid username/email or password.', 'danger')
            return redirect(url_for('login'))
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    """
    Logs out the current user by clearing session variables.
    """
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('email', None)
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

    user = User.query.get(session['user_id']) # Get user by ID using SQLAlchemy

    if not user:
        flash('User not found. Please log in again.', 'error')
        session.pop('user_id', None)
        session.pop('username', None)
        session.pop('email', None)
        return redirect(url_for('login'))

    # Get today's date for use in the template to set max attribute for DOB input
    today_date_str = date.today().strftime('%Y-%m-%d')

    return render_template('profile.html', user=user, today_date_str=today_date_str)

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

    user = User.query.get(user_id) # Get user by ID using SQLAlchemy

    if not user:
        flash('User not found. Please log in again.', 'error')
        session.pop('user_id', None)
        session.pop('username', None)
        session.pop('email', None)
        return redirect(url_for('login'))

    if not old_password or not new_password or not confirm_new_password:
        flash('All password fields are required.', 'error')
        return redirect(url_for('profile'))

    if not check_password_hash(user.password_hash, old_password):
        flash('Incorrect old password.', 'error')
        return redirect(url_for('profile'))

    if new_password != confirm_new_password:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('profile'))
    
    # Refinement: Password complexity validation for change password
    if not is_strong_password(new_password):
        flash('New password must be at least 8 characters long and include uppercase, lowercase, numbers, and special characters.', 'danger')
        return redirect(url_for('profile'))

    try:
        user.password_hash = generate_password_hash(new_password)
        db.session.commit() # Commit changes to database via SQLAlchemy
        flash('Password updated successfully!', 'success')
    except Exception as e:
        db.session.rollback() # Rollback in case of error
        print(f"Database error changing password: {e}")
        flash('An unexpected error occurred while updating password.', 'error')
    
    return redirect(url_for('profile'))

@app.route('/update_dob', methods=['POST'])
def update_dob():
    if 'user_id' not in session:
        flash('Please log in to update your profile.', 'warning')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('login'))

    new_dob = request.form.get('dob')
    if new_dob:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", new_dob):
            flash('Invalid date format. Please use YYYY-MM-DD.', 'danger')
            return redirect(url_for('profile'))
        
        try:
            birth_date_obj = datetime.strptime(new_dob, "%Y-%m-%d").date()
            current_date = date.today()
            min_dob_allowed = date(1925, 1, 1) # Nothing before 1925
        except ValueError:
            flash('Invalid date of birth provided. Please use a valid date.', 'danger')
            return redirect(url_for('profile'))

        if birth_date_obj > current_date:
            flash('Date of birth cannot be in the future. DOB not updated.', 'danger')
            return redirect(url_for('profile'))

        if birth_date_obj < min_dob_allowed:
            flash(f'Date of birth cannot be before {min_dob_allowed.year}. DOB not updated.', 'danger')
            return redirect(url_for('profile'))

        user_age = calculate_age(new_dob)
        if user_age is None:
            flash('Invalid date of birth provided.', 'danger')
            return redirect(url_for('profile'))
        elif user_age < 13: # Example: Minimum age requirement
            flash('You must be at least 13 years old. DOB not updated.', 'danger')
            return redirect(url_for('profile'))

        try:
            user.dob = new_dob
            db.session.commit()
            flash('Date of birth updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'An unexpected error occurred: {e}', 'danger')
    else:
        flash('Date of birth cannot be empty.', 'danger')

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
    
    # Store form values to pre-fill the search form on re-render
    search_term_val = ""
    score_min_val = ""
    score_max_val = ""
    date_min_val = ""
    date_max_val = ""
    selected_age_rating = ""
    selected_platforms_ids = [] # Use platform IDs for comparison

    if request.method == "POST":
        filter_type = request.form.get("filter")
        query_parts = [GAME_SELECT, "WHERE 1=1"] # Start with a true condition for easy AND additions
        params = []
        error = None

        if filter_type == "text":
            search_term_val = request.form.get("search_term", "").strip()
            if search_term_val:
                candidates = game_titles + dev_names + pub_names
                # Use difflib.get_close_matches for a slightly fuzzy search on input, then use that for LIKE
                # Note: This is an expensive operation for large datasets.
                close_matches = difflib.get_close_matches(search_term_val, candidates, n=1, cutoff=0.6)
                best_match = close_matches[0] if close_matches else search_term_val
                wildcard = f"%{best_match}%"
                
                query_parts.append("""
                    AND (g.title LIKE ? COLLATE NOCASE
                        OR d.name LIKE ? COLLATE NOCASE
                        OR pub.name LIKE ? COLLATE NOCASE
                        OR g.genre LIKE ? COLLATE NOCASE
                        OR g.description LIKE ? COLLATE NOCASE)
                    """)
                params.extend([wildcard, wildcard, wildcard, wildcard, wildcard])
                search_type = "Text Search"
            else:
                error = "Please enter a search term."

        elif filter_type == "score":
            score_min_val = request.form.get("score_min", "").strip()
            score_max_val = request.form.get("score_max", "").strip()
            try:
                min_val = int(score_min_val) if score_min_val else min_score
                max_val = int(score_max_val) if score_max_val else max_score

                if not (0 <= min_val <= 100 and 0 <= max_val <= 100 and min_val <= max_val):
                    error = "Score values must be between 0 and 100, and min score cannot exceed max score."
                else:
                    query_parts.append(" AND g.metacritic_score >= ? AND g.metacritic_score <= ? ")
                    params.extend([min_val, max_val])
                    search_type = f"Metacritic Score: {min_val}-{max_val}"
            except ValueError:
                error = "Invalid score values. Please enter numbers only."

        elif filter_type == "date":
            date_min_val = request.form.get("date_min", "").strip()
            date_max_val = request.form.get("date_max", "").strip()
            try:
                if date_min_val and date_max_val:
                    date_min_obj = datetime.strptime(date_min_val, "%Y-%m-%d")
                    date_max_obj = datetime.strptime(date_max_val, "%Y-%m-%d")
                    
                    # Ensure valid date range (e.g., after 1980, before today)
                    allowed_min_date = datetime(1980, 1, 1).date()
                    allowed_max_date = date.today()

                    if not (allowed_min_date <= date_min_obj.date() <= date_max_obj.date() <= allowed_max_date):
                        error = f"Dates must be between {allowed_min_date.strftime('%Y-%m-%d')} and {allowed_max_date.strftime('%Y-%m-%d')}, and start date cannot be after end date."
                    else:
                        query_parts.append(" AND g.release_date BETWEEN ? AND ? ")
                        params.extend([date_min_val, date_max_val])
                        search_type = f"Release Date: {date_min_val} to {date_max_val}"
                else:
                    error = "Please provide both start and end dates."
            except ValueError:
                error = "Invalid date format. Use YYYY-MM-DD."

        elif filter_type == "age_rating":
            selected_age_rating = request.form.get("age_rating", "").strip().upper()
            allowed_age_ratings = ["G", "PG", "M", "R13", "R16", "R18"]
            if selected_age_rating and selected_age_rating in allowed_age_ratings:
                query_parts.append(" AND ar.rating = ? ")
                params.append(selected_age_rating)
                search_type = f"Age Rating: {selected_age_rating}"
            else:
                error = f"Invalid age rating. Allowed ratings: {', '.join(allowed_age_ratings)}."

        elif filter_type == "platform":
            selected_platforms_ids = request.form.getlist("platforms") # Get list of selected platform IDs
            if selected_platforms_ids:
                # Build a dynamic OR condition for each platform_id column
                # This is still a bit clunky due to your database schema (multiple platform_id columns)
                platform_conditions = []
                for i in range(1, 9): # Iterate through platform_id, platform_id2, ..., platform_id8
                    platform_conditions.append(f"gp.platform_id{'' if i == 1 else i} IN ({','.join('?' * len(selected_platforms_ids))})")
                
                query_parts.append(" AND (" + " OR ".join(platform_conditions) + ")")
                
                # Extend params for each platform_id column condition
                for _ in range(8): # Each platform_idX column needs its own set of parameters
                    params.extend(selected_platforms_ids)
                
                search_type = "Platform"
            else:
                error = "Please select at least one platform."
        
        # If no filter type was selected or something went wrong
        if not filter_type and not error:
            error = "Please select a search filter."

        if error:
            flash(error, 'danger')
        else:
            try:
                full_query = " ".join(query_parts)
                results_raw = conn.execute(full_query, tuple(params)).fetchall()
                
                processed_results = []
                for game_row in results_raw:
                    game_dict = dict(game_row)
                    platforms_list = []
                    # Collect platforms from potentially multiple platform_nameX columns
                    for i in range(1, 9):
                        platform_key = f'platform_name{"" if i == 1 else i}'
                        if game_dict.get(platform_key):
                            platforms_list.append(game_dict[platform_key])
                            # Optional: remove the individual platform_nameX keys if not needed for display
                            # del game_dict[platform_key]
                    game_dict['platforms_display'] = list(set(platforms_list)) # Remove duplicates
                    processed_results.append(game_dict)
                results = processed_results
                
            except sqlite3.Error as e:
                flash(f"Database error during search: {e}", 'danger')
                results = [] # Clear results on error
    
    return render_template("search.html",
                           publishers=publishers,
                           developers=developers,
                           min_score=min_score,
                           max_score=max_score,
                           platforms=all_platforms,
                           results=results,
                           search_type=search_type,
                           # Pass back current form values for persistence
                           search_term=search_term_val,
                           score_min=score_min_val,
                           score_max=score_max_val,
                           date_min=date_min_val,
                           date_max=date_max_val,
                           selected_age_rating=selected_age_rating,
                           selected_platforms=selected_platforms_ids # Pass IDs to re-check checkboxes
                           )

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
            # del game[platform_key] # Optional: clean up dict
    game['platforms_display'] = list(set(platforms_list))

    is_game_in_user_list = False
    if 'user_id' in session:
        user_id = session['user_id']
        # Check using SQLAlchemy's UserGame model
        existing_entry = UserGame.query.filter_by(user_id=user_id, game_id=game_id).first()
        if existing_entry:
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
    
    # Get game_ids from UserGame using SQLAlchemy
    user_game_entries = UserGame.query.filter_by(user_id=user_id).order_by(UserGame.date_added.desc()).all()
    game_ids = [entry.game_id for entry in user_game_entries]
    
    if not game_ids:
        return render_template('my_games.html', user_games=[])

    popular_games_db = get_popular_games_db()
    # Use IN clause to fetch all details for these game_ids from Popular_Games.db
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
            'description': game_dict['description'],
            'cover_image': game_dict.get('cover_image', ''),
            'price': game_dict.get('price', 'N/A'),
            'currency': game_dict.get('currency', '')
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

    # Check and add using SQLAlchemy's UserGame model
    existing_entry = UserGame.query.filter_by(user_id=user_id, game_id=game_id).first()
    if existing_entry:
        flash('This game is already in your list!', 'warning')
    else:
        new_entry = UserGame(user_id=user_id, game_id=game_id)
        try:
            db.session.add(new_entry)
            db.session.commit()
            flash('Game added to your list successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            print(f"SQLAlchemy error adding game to list: {e}")
            flash('An unexpected error occurred while adding the game.', 'error')

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
    
    # Find and delete using SQLAlchemy's UserGame model
    entry_to_remove = UserGame.query.filter_by(user_id=user_id, game_id=game_id).first()
    
    if entry_to_remove:
        try:
            db.session.delete(entry_to_remove)
            db.session.commit()
            flash('Game removed from your list!', 'success')
        except Exception as e:
            db.session.rollback()
            print(f"SQLAlchemy error removing game from list: {e}")
            flash('An unexpected error occurred while removing the game.', 'error')
    else:
        flash('Game not found in your list.', 'warning')
    
    # Redirect back to 'my_games' if that was the referrer, otherwise to game detail
    if request.referrer and 'my_games' in request.referrer:
        return redirect(url_for('my_games'))
    return redirect(url_for('game_detail', game_id=game_id))

# --- Application Entry Point ---
if __name__ == '__main__':
    app.run(debug=True)