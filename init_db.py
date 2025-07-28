import sqlite3

conn = sqlite3.connect("verdicts.db")
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS verdict_counts (
    date TEXT NOT NULL,
    verdict TEXT NOT NULL,
    count INTEGER DEFAULT 1,
    PRIMARY KEY (date, verdict)
)
""")

conn.commit()
conn.close()

print("✅ verdict_counts table initialized")
