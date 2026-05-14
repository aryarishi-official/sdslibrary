"""
Migration: add uploaded_at and signal_word to sds_documents
Run once: python migrate_add_columns.py
"""
from sqlalchemy import text
from database import engine

with engine.connect() as conn:
    # Add uploaded_at
    try:
        conn.execute(text(
            "ALTER TABLE sds_documents ADD COLUMN uploaded_at TIMESTAMP DEFAULT NOW()"
        ))
        conn.commit()
        print("✅  Added uploaded_at column")
    except Exception as e:
        print(f"⚠   uploaded_at already exists or error: {e}")

    # Add signal_word
    try:
        conn.execute(text(
            "ALTER TABLE sds_documents ADD COLUMN signal_word VARCHAR"
        ))
        conn.commit()
        print("✅  Added signal_word column")
    except Exception as e:
        print(f"⚠   signal_word already exists or error: {e}")

print("Migration complete.")
