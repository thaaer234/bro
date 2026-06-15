import sqlite3

def run_reindex():
    conn = sqlite3.connect("db.sqlite3")
    cursor = conn.cursor()
    print("Running REINDEX on the database...")
    try:
        cursor.execute("REINDEX;")
        conn.commit()
        print("REINDEX completed successfully!")
    except Exception as e:
        print("Error during REINDEX:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    run_reindex()
