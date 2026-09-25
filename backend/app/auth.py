"""Local operator accounts. Create accounts from the trusted server terminal."""
import argparse
import getpass
import hashlib
import hmac
import secrets
import time
from fastapi import Header, HTTPException
from app.operations import database


def tables(db):
    db.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, salt TEXT, password_hash TEXT, role TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, username TEXT, expires REAL)")
    db.execute("CREATE TABLE IF NOT EXISTS login_attempts (username TEXT PRIMARY KEY, failures INTEGER, reset_at REAL)")


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600000).hex()


def create_user(username, password, role):
    username = username.strip().lower()
    if not username or len(username) > 80 or len(password) < 12 or role not in ("operator", "reviewer"):
        raise ValueError("Use a username, a password of at least 12 characters, and operator or reviewer role.")
    salt = secrets.token_hex(16)
    digest = password_hash(password, salt)
    with database() as db:
        tables(db)
        if db.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            raise ValueError("Account already exists; creation does not overwrite credentials.")
        db.execute("INSERT INTO users VALUES (?,?,?,?)", (username, salt, digest, role))


def login(username, password):
    username = username.strip().lower()
    now = time.time()
    # Serialize attempts so concurrent logins cannot bypass the failure counter.
    with database() as db:
        tables(db)
        db.execute("BEGIN IMMEDIATE")
        attempts = db.execute("SELECT * FROM login_attempts WHERE username=?", (username,)).fetchone()
        if attempts and attempts["reset_at"] > now and attempts["failures"] >= 5:
            return None
        user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        candidate = password_hash(password, user["salt"] if user else "00" * 16)
        if not user or not hmac.compare_digest(candidate, user["password_hash"]):
            failures = attempts["failures"] if attempts and attempts["reset_at"] > now else 0
            reset = attempts["reset_at"] if failures else now + 900
            db.execute("INSERT OR REPLACE INTO login_attempts VALUES (?,?,?)", (username, failures+1, reset))
            return None
        db.execute("DELETE FROM login_attempts WHERE username=?", (username,))
        db.execute("DELETE FROM sessions WHERE expires<?", (now,))
        token = secrets.token_urlsafe(32)
        db.execute("INSERT INTO sessions VALUES (?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), username, now+8*3600))
        return {"token": token, "username": username, "role": user["role"]}


def identity(authorization: str = Header(default="")):
    token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
    with database() as db:
        tables(db)
        row = db.execute("SELECT u.username,u.role FROM sessions s JOIN users u ON u.username=s.username WHERE s.token_hash=? AND s.expires>?", (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
    if not row:
        raise HTTPException(401, "Sign in with a local operator or reviewer account.")
    return dict(row)


def main():
    parser = argparse.ArgumentParser(description="Create a local authenticated Vayu account")
    parser.add_argument("username")
    parser.add_argument("--role", choices=["operator", "reviewer"], required=True)
    args = parser.parse_args()
    password = getpass.getpass("Password (at least 12 characters): ")
    if password != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords did not match.")
    create_user(args.username, password, args.role)
    print("Account created. Sign in on the Action planner page.")


if __name__ == "__main__":
    main()
