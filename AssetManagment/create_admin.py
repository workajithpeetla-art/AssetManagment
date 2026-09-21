import os
import sqlite3
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'assets.db')

def init_db(cursor):
    """Ensure database tables exist before adding records."""
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

def create_admin():
    print("=== Create New Admin User ===")
    username = input("Enter admin username: ").strip()
    password = input("Enter admin password: ").strip()

    if not username or not password:
        print("Error: Username and password cannot be empty.")
        return

    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Automatically create tables if they do not exist
    init_db(cursor)

    try:
        cursor.execute(
            'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
            (username, hashed_password, 'admin')
        )
        conn.commit()
        print(f"Success: Admin user '{username}' created successfully!")
    except sqlite3.IntegrityError:
        print(f"Error: User '{username}' already exists in the database.")
    finally:
        conn.close()

if __name__ == '__main__':
    create_admin()