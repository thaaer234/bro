import sqlite3

def try_fix():
    db_path = "db.sqlite3"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get schemas of the corrupted tables before dropping them
    schemas = {}
    for table in ['errors_errorlog', 'pages_activitylog']:
        try:
            cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}';")
            row = cursor.fetchone()
            if row:
                schemas[table] = row[0]
                print(f"Schema for {table}: {row[0]}")
        except Exception as e:
            print(f"Failed to get schema for {table}: {e}")

    # Also get indices of these tables
    indices = []
    try:
        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name IN ('errors_errorlog', 'pages_activitylog');")
        indices = cursor.fetchall()
        print("Indices to recreate:", indices)
    except Exception as e:
        print("Failed to get indices:", e)

    # Let's try to drop the tables
    for table in ['errors_errorlog', 'pages_activitylog']:
        print(f"Attempting to drop table {table}...")
        try:
            cursor.execute(f"DROP TABLE [{table}];")
            print(f"Successfully dropped table {table}!")
        except Exception as e:
            print(f"Failed to drop table {table}: {e}")

    # Recreate the tables if they were successfully dropped
    for table, schema in schemas.items():
        print(f"Attempting to recreate table {table}...")
        try:
            cursor.execute(schema)
            print(f"Successfully recreated table {table}!")
        except Exception as e:
            print(f"Failed to recreate table {table}: {e}")

    # Recreate the indices
    for index_name, index_sql in indices:
        if index_sql:
            print(f"Attempting to recreate index {index_name}...")
            try:
                cursor.execute(index_sql)
                print(f"Successfully recreated index {index_name}!")
            except Exception as e:
                print(f"Failed to recreate index {index_name}: {e}")

    # Run integrity check
    print("Running integrity check after operations...")
    try:
        cursor.execute("PRAGMA integrity_check;")
        results = cursor.fetchall()
        for res in results[:20]:
            print(res)
    except Exception as e:
        print("Integrity check failed:", e)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    try_fix()
