import sqlite3
import subprocess
import os

def main():
    db_path = 'db.sqlite3'
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check columns
        cursor.execute("PRAGMA table_info(accounts_studentenrollment)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'subjects_note' not in columns:
            print("Adding column subjects_note to accounts_studentenrollment...")
            cursor.execute("ALTER TABLE accounts_studentenrollment ADD COLUMN subjects_note varchar(255) NOT NULL DEFAULT 'كامل المواد'")
            conn.commit()
            print("Column added successfully!")
        else:
            print("Column subjects_note already exists.")
            
        conn.close()
        
        # Fake the migration in Django
        print("Faking the migration in Django...")
        res = subprocess.run(["python", "manage.py", "migrate", "accounts", "0012", "--fake"], capture_output=True, text=True)
        print("STDOUT:", res.stdout)
        print("STDERR:", res.stderr)
        
    except Exception as e:
        print("Error:", e)

if __name__ == '__main__':
    main()
