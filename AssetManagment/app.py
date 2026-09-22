import os
import sqlite3
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'office-asset-management-secret-key')

# Absolute path for SQLite compatibility
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'assets.db')

# --- Database Helper ---
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  
    return conn

# --- Initialize Database Tables ---
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create User Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'admin'
        )
    ''')

    # Create Asset Table
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
    cursor.execute('SELECT * FROM users WHERE username = ?', ('admin',))
    if not cursor.fetchone():
        hashed_pw = generate_password_hash('admin123', method='pbkdf2:sha256')
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
    user_data = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if user_data:
        return User(user_data['id'], user_data['username'], user_data['password'], user_data['role'])
    return None

# --- Application Routes ---

@app.route('/')
@login_required
def dashboard():
    conn = get_db_connection()
    assets = conn.execute('SELECT * FROM assets').fetchall()
    conn.close()
    return render_template('dashboard.html', assets=assets)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_db_connection()
        user_data = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
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

@app.route('/admin/create-user', methods=['POST'])
@login_required
def create_user_route():
    if current_user.role != 'admin':
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('dashboard'))

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()

    if not username or not password:
        flash('Username and password are required.', 'danger')
        return redirect(url_for('dashboard'))

    hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                     (username, hashed_pw, 'admin'))
        conn.commit()
        flash(f'Admin user "{username}" created successfully!', 'success')
    except sqlite3.IntegrityError:
        flash(f'Error: Username "{username}" already exists.', 'danger')
    finally:
        conn.close()

    return redirect(url_for('dashboard'))

@app.route('/asset/add', methods=['POST'])
@login_required
def add_asset():
    name = request.form.get('name')
    category = request.form.get('category')
    serial_number = request.form.get('serial_number')
    status = request.form.get('status')
    assigned_to = request.form.get('assigned_to') if status == 'Assigned' else None

    conn = get_db_connection()
    try:
        conn.execute(
            'INSERT INTO assets (name, category, serial_number, status, assigned_to) VALUES (?, ?, ?, ?, ?)',
            (name, category, serial_number, status, assigned_to)
        )
        conn.commit()
        flash('Asset added successfully!', 'success')
    except sqlite3.IntegrityError:
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
    try:
        conn.execute(
            'UPDATE assets SET name = ?, category = ?, serial_number = ?, status = ?, assigned_to = ? WHERE id = ?',
            (name, category, serial_number, status, assigned_to, id)
        )
        conn.commit()
        flash('Asset updated successfully!', 'success')
    except sqlite3.IntegrityError:
        flash('Error: Serial number already exists on another item.', 'danger')
    finally:
        conn.close()

    return redirect(url_for('dashboard'))

@app.route('/asset/delete/<int:id>')
@login_required
def delete_asset(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM assets WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Asset deleted successfully!', 'success')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)