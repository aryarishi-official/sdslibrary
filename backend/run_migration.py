from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text("ALTER TABLE subsections ADD COLUMN IF NOT EXISTS content_html TEXT"))
    conn.commit()
    print("Migration done.")