import sqlite3

conn = sqlite3.connect("lost_found.db")

conn.execute("""
    CREATE TABLE IF NOT EXISTS lost_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name TEXT NOT NULL,
        description TEXT NOT NULL,
        category TEXT NOT NULL,
        location TEXT NOT NULL,
        date TEXT NOT NULL,
        image TEXT,
        status TEXT NOT NULL
    )
""")

conn.execute("""
    CREATE TABLE IF NOT EXISTS found_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name TEXT NOT NULL,
        description TEXT NOT NULL,
        category TEXT NOT NULL,
        location TEXT NOT NULL,
        date TEXT NOT NULL,
        image TEXT,
        status TEXT NOT NULL
    )
""")

conn.execute("""
    CREATE TABLE IF NOT EXISTS claims (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        found_item_id INTEGER NOT NULL,
        claimant_name TEXT NOT NULL,
        claimant_email TEXT NOT NULL,
        message TEXT,
        status TEXT NOT NULL,
        FOREIGN KEY (found_item_id) REFERENCES found_items(id)
    )
""")

conn.commit()
conn.close()

print("Database created successfully!")