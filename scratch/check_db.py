import sqlite3

def check_integrity():
    conn = sqlite3.connect("db.sqlite3")
    cursor = conn.cursor()
    print("Checking database integrity...")
    try:
        cursor.execute("PRAGMA integrity_check;")
        results = cursor.fetchall()
        for res in results[:20]:
            print(res)
        if len(results) > 20:
            print(f"... and {len(results) - 20} more errors/messages.")
    except Exception as e:
        print("Error checking integrity:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    check_integrity()
