"""
Database migration script to add new columns for multi-agent sequential mode.
Run this if you want to preserve existing data.
"""

import sqlite3

def migrate_database():
    conn = sqlite3.connect('chat_app.db.backup_*')  # Update with your backup filename
    cursor = conn.cursor()

    try:
        # Add conversation_mode column to multi_agent_sessions
        print("Adding conversation_mode column...")
        cursor.execute("""
            ALTER TABLE multi_agent_sessions
            ADD COLUMN conversation_mode VARCHAR(20) DEFAULT 'sequential'
        """)
        print("✓ Added conversation_mode column")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e):
            print("✓ conversation_mode column already exists")
        else:
            raise

    try:
        # Rename round_number to turn_number in multi_agent_turns
        # SQLite doesn't support RENAME COLUMN directly in older versions
        # So we need to recreate the table
        print("Updating multi_agent_turns table...")

        # Check if turn_number exists
        cursor.execute("PRAGMA table_info(multi_agent_turns)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'turn_number' not in columns and 'round_number' in columns:
            # Create new table with correct schema
            cursor.execute("""
                CREATE TABLE multi_agent_turns_new (
                    id INTEGER PRIMARY KEY,
                    session_id INTEGER NOT NULL,
                    turn_number INTEGER NOT NULL,
                    model_name VARCHAR(100) NOT NULL,
                    model_role VARCHAR(200),
                    content TEXT NOT NULL,
                    duration FLOAT,
                    error TEXT,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES multi_agent_sessions(id) ON DELETE CASCADE
                )
            """)

            # Copy data from old table
            cursor.execute("""
                INSERT INTO multi_agent_turns_new
                SELECT id, session_id, round_number as turn_number, model_name,
                       model_role, content, duration, error, created_at
                FROM multi_agent_turns
            """)

            # Drop old table and rename new one
            cursor.execute("DROP TABLE multi_agent_turns")
            cursor.execute("ALTER TABLE multi_agent_turns_new RENAME TO multi_agent_turns")
            print("✓ Updated turn_number column")
        else:
            print("✓ turn_number column already correct")

    except sqlite3.OperationalError as e:
        print(f"Warning: {e}")

    conn.commit()
    conn.close()
    print("\n✓ Migration completed successfully!")
    print("You can now use the updated database.")

if __name__ == "__main__":
    migrate_database()
