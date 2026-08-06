import os
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel
import sqlite3
from settings import settings

TOKEN_EXPIRE_HOURS = 24

AUTH_DB_PATH = settings.auth_db_path


def ensure_db_dir() -> None:
    os.makedirs(os.path.dirname(AUTH_DB_PATH), exist_ok=True)


# ===== Models =====
class UserCreate(BaseModel):
    username: str
    password: str
    email: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = TOKEN_EXPIRE_HOURS * 3600

class UserInfo(BaseModel):
    id: int
    username: str
    email: Optional[str]
    created_at: str


# ===== Database =====
def get_auth_db():
    ensure_db_dir()
    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_auth_db():
    conn = get_auth_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()


# ===== Password Hashing =====
def hash_password(password: str) -> str:
    """Hash password with salt."""
    salt = secrets.token_hex(16)
    hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}:{hash_obj.hex()}"

def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash."""
    try:
        salt, stored_hash = password_hash.split(':')
        hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return hash_obj.hex() == stored_hash
    except Exception:
        return False


# ===== Token Management =====
def generate_token() -> str:
    """Generate a secure random token."""
    return secrets.token_urlsafe(32)

def create_token(user_id: int) -> tuple[str, datetime]:
    """Create a new token for user."""
    conn = get_auth_db()
    cursor = conn.cursor()
    
    token = generate_token()
    expires_at = datetime.now() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    
    cursor.execute(
        "INSERT INTO tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
        (user_id, token, expires_at.isoformat())
    )
    
    conn.commit()
    conn.close()
    
    return token, expires_at

def validate_token(token: str) -> Optional[int]:
    """Validate token and return user_id if valid."""
    conn = get_auth_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT user_id, expires_at FROM tokens 
        WHERE token = ?
    """, (token,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
    
    expires_at = datetime.fromisoformat(row['expires_at'])
    if datetime.now() > expires_at:
        # Token expired, delete it
        delete_token(token)
        return None
    
    return row['user_id']

def delete_token(token: str):
    """Delete a token."""
    conn = get_auth_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tokens WHERE token = ?", (token,))
    conn.commit()
    conn.close()


# ===== User Management =====
def create_user(username: str, password: str, email: str = None) -> Optional[int]:
    """Create a new user."""
    conn = get_auth_db()
    cursor = conn.cursor()
    
    try:
        password_hash = hash_password(password)
        cursor.execute(
            "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
            (username, password_hash, email)
        )
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        conn.close()
        return None  # Username already exists

def authenticate_user(username: str, password: str) -> Optional[dict]:
    """Authenticate user and return user info if valid."""
    conn = get_auth_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
    
    if not verify_password(password, row['password_hash']):
        return None
    
    return dict(row)

def get_user_by_id(user_id: int) -> Optional[dict]:
    """Get user by ID."""
    conn = get_auth_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, username, email, created_at FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    return dict(row) if row else None


# Initialize database
init_auth_db()
