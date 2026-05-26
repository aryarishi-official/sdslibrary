"""
Migration: add `role` column to the users table (safe to re-run).
"""
from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'viewer'"
    ))
    # Back-fill any existing rows that have NULL role
    conn.execute(text(
        "UPDATE users SET role = 'viewer' WHERE role IS NULL"
    ))
    conn.commit()
    print("Migration done: role column added to users table.")
