import sqlite3

def scan_rows():
    conn = sqlite3.connect("db.sqlite3")
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Found {len(tables)} tables. Scanning rows...")
        
        corrupted_tables = []
        for table in tables:
            try:
                # Do a full table scan by selecting all rows and fetching them
                cursor.execute(f"SELECT * FROM [{table}];")
                # We can fetch in chunks to avoid loading all into memory, but we want to trigger reading of all pages.
                chunk_size = 1000
                rows_read = 0
                while True:
                    rows = cursor.fetchmany(chunk_size)
                    if not rows:
                        break
                    rows_read += len(rows)
                # print(f"Table '{table}': successfully read {rows_read} rows.")
            except Exception as e:
                print(f"Table '{table}': FAILED at row read - {e}")
                corrupted_tables.append(table)
        
        print("\nScan completed.")
        if corrupted_tables:
            print("Corrupted tables:", corrupted_tables)
        else:
            print("No tables failed during full row read.")
            
    except Exception as e:
        print("Failed to get tables list:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    scan_rows()
