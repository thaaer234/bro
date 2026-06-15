import sqlite3

def scan_tables():
    conn = sqlite3.connect("db.sqlite3")
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Found {len(tables)} tables. Scanning...")
        
        corrupted_tables = []
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM [{table}];")
                count = cursor.fetchone()[0]
                # print(f"Table '{table}': {count} rows (OK)")
            except Exception as e:
                print(f"Table '{table}': FAILED - {e}")
                corrupted_tables.append(table)
        
        print("\nScan completed.")
        if corrupted_tables:
            print("Corrupted tables:", corrupted_tables)
        else:
            print("No individual tables failed simple count query.")
            
    except Exception as e:
        print("Failed to get tables list:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    scan_tables()
