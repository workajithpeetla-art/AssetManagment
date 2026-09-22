import os
import psycopg2
import psycopg2.extras
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'office-asset-management-secret-key')

DATABASE_URL = os.environ.get('DATABASE_URL')

# --- Database Helper ---
def get_db_connection():
    if DATABASE_URL:
        # Connect to Supabase / PostgreSQL
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        # Local SQLite fallback for testing on your computer
        import sqlite3
        BASE_DIR = os.path.abspath(os.path.dirname(__file__))
        DB_PATH = os.path.join(BASE_DIR, 'assets.db')
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
    return conn

# --- Initialize Database Tables ---
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if DATABASE_URL:
        # PostgreSQL Table Creation Syntax
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'admin'
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS assets (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                serial_number TEXT UNIQUE NOT NULL,
                status TEXT DEFAULT 'Available',
                assigned_to TEXT
            )
        ''')
    else:
        # SQLite Table Creation Syntax
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'admin'
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                serial_number TEXT UNIQUE NOT NULL,
                status TEXT DEFAULT 'Available',
                assigned_to TEXT
            )
        ''')

    # Create Default Admin User (username: admin | password: admin123)
    if DATABASE_URL:
        cursor.execute('SELECT * FROM users WHERE username = %s', ('admin',))
    else:
        cursor.execute('SELECT * FROM users WHERE username = ?', ('admin',))
        
    if not cursor.fetchone():
        hashed_pw = generate_password_hash('admin123', method='pbkdf2:sha256')
        if DATABASE_URL:
            cursor.execute('INSERT INTO users (username, password, role) VALUES (%s, %s, %s)',
                           ('admin', hashed_pw, 'admin'))
        else:
            cursor.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                           ('admin', hashed_pw, 'admin'))
        print("Default admin created. Username: admin | Password: admin123")

    conn.commit()
    conn.close()

# Ensure database tables and default admin are created on startup
init_db()

# --- Flask-Login Configuration ---
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, password, role):
        self.id = id
        self.username = username
        self.password = password
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    else:
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    if user_data:
        return User(user_data['id'], user_data['username'], user_data['password'], user_data['role'])
    return None

# --- Application Routes ---

@app.route('/')
@login_required
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM assets')
    assets = cursor.fetchall()
    conn.close()
    return render_template('dashboard.html', assets=assets)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_db_connection()
        cursor = conn.cursor()
        if DATABASE_URL:
            cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        else:
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user_data = cursor.fetchone()
        conn.close()

        if user_data and check_password_hash(user_data['password'], password):
            user = User(user_data['id'], user_data['username'], user_data['password'], user_data['role'])
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/asset/add', methods=['POST'])
@login_required
def add_asset():
    name = request.form.get('name')
    category = request.form.get('category')
    serial_number = request.form.get('serial_number')
    status = request.form.get('status')
    assigned_to = request.form.get('assigned_to') if status == 'Assigned' else None

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if DATABASE_URL:
            cursor.execute(
                'INSERT INTO assets (name, category, serial_number, status, assigned_to) VALUES (%s, %s, %s, %s, %s)',
                (name, category, serial_number, status, assigned_to)
            )
        else:
            cursor.execute(
                'INSERT INTO assets (name, category, serial_number, status, assigned_to) VALUES (?, ?, ?, ?, ?)',
                (name, category, serial_number, status, assigned_to)
            )
        conn.commit()
        flash('Asset added successfully!', 'success')
    except Exception:
        conn.rollback()
        flash('Error: An asset with this Serial Number already exists.', 'danger')
    finally:
        conn.close()

    return redirect(url_for('dashboard'))

@app.route('/asset/edit/<int:id>', methods=['POST'])
@login_required
def edit_asset(id):
    name = request.form.get('name')
    category = request.form.get('category')
    serial_number = request.form.get('serial_number')
    status = request.form.get('status')
    assigned_to = request.form.get('assigned_to') if status == 'Assigned' else None

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if DATABASE_URL:
            cursor.execute(
                'UPDATE assets SET name = %s, category = %s, serial_number = %s, status = %s, assigned_to = %s WHERE id = %s',
                (name, category, serial_number, status, assigned_to, id)
            )
        else:
            cursor.execute(
                'UPDATE assets SET name = ?, category = ?, serial_number = ?, status = ?, assigned_to = ? WHERE id = ?',
                (name, category, serial_number, status, assigned_to, id)
            )
        conn.commit()
        flash('Asset updated successfully!', 'success')
    except Exception:
        conn.rollback()
        flash('Error: Serial number already exists on another item.', 'danger')
    finally:
        conn.close()

    return redirect(url_for('dashboard'))

@app.route('/asset/delete/<int:id>')
@login_required
def delete_asset(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute('DELETE FROM assets WHERE id = %s', (id,))
    else:
        cursor.execute('DELETE FROM assets WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Asset deleted successfully!', 'success')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)