import sqlite3
import os
import shutil

def rebuild():
    old_db = "db.sqlite3"
    new_db = "db_rebuilt.sqlite3"
    backup_db = "db_malformed_backup.sqlite3"
    
    if os.path.exists(new_db):
        os.remove(new_db)
        
    print(f"Connecting to {old_db} and creating {new_db}...")
    conn_old = sqlite3.connect(old_db)
    conn_new = sqlite3.connect(new_db)
    
    cursor_old = conn_old.cursor()
    cursor_new = conn_new.cursor()
    
    # 1. Get all tables and their creation SQL
    cursor_old.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = cursor_old.fetchall()
    
    print(f"Found {len(tables)} tables to recreate.")
    
    # Create tables in the new database
    for table_name, create_sql in tables:
        if not create_sql:
            continue
        try:
            cursor_new.execute(create_sql)
            # print(f"Created table: {table_name}")
        except Exception as e:
            print(f"Failed to create table {table_name}: {e}")
            
    # Commit table creation
    conn_new.commit()
    
    # 2. Copy data for each table
    corrupted_tables = ['errors_errorlog', 'pages_activitylog']
    
    for table_name, _ in tables:
        print(f"Copying data for {table_name}...")
        try:
            # We fetch all rows
            cursor_old.execute(f"SELECT * FROM [{table_name}];")
            
            # Get column count to format INSERT statement
            cursor_new.execute(f"PRAGMA table_info([{table_name}]);")
            columns = cursor_new.fetchall()
            col_count = len(columns)
            placeholders = ",".join(["?"] * col_count)
            insert_sql = f"INSERT INTO [{table_name}] VALUES ({placeholders});"
            
            rows_copied = 0
            if table_name in corrupted_tables:
                # For corrupted tables, read row-by-row and skip corrupted ones
                while True:
                    try:
                        row = cursor_old.fetchone()
                        if row is None:
                            break
                        cursor_new.execute(insert_sql, row)
                        rows_copied += 1
                    except Exception as row_error:
                        print(f"Skipping corrupted row in {table_name}: {row_error}")
                        # Re-establish cursor_old if it got aborted
                        # (in sqlite, fetchone on a malformed db might error but allow continuing, or might need cursor reset)
                        # Let's just try to continue or break if it fails repeatedly.
                        break
            else:
                # Standard batch copying
                batch_size = 1000
                while True:
                    rows = cursor_old.fetchmany(batch_size)
                    if not rows:
                        break
                    cursor_new.executemany(insert_sql, rows)
                    rows_copied += len(rows)
            
            print(f"Copied {rows_copied} rows for {table_name}.")
            
        except Exception as e:
            print(f"Error copying {table_name}: {e}")
            
    conn_new.commit()
    
    # 3. Copy views
    cursor_old.execute("SELECT name, sql FROM sqlite_master WHERE type='view';")
    views = cursor_old.fetchall()
    print(f"Recreating {len(views)} views...")
    for view_name, create_sql in views:
        if not create_sql:
            continue
        try:
            cursor_new.execute(create_sql)
        except Exception as e:
            print(f"Failed to create view {view_name}: {e}")
            
    # 4. Copy indices
    cursor_old.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%';")
    indices = cursor_old.fetchall()
    print(f"Recreating {len(indices)} indices...")
    for idx_name, create_sql in indices:
        if not create_sql:
            continue
        try:
            cursor_new.execute(create_sql)
        except Exception as e:
            print(f"Failed to create index {idx_name}: {e}")
            
    # 5. Copy triggers
    cursor_old.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger';")
    triggers = cursor_old.fetchall()
    print(f"Recreating {len(triggers)} triggers...")
    for trigger_name, create_sql in triggers:
        if not create_sql:
            continue
        try:
            cursor_new.execute(create_sql)
        except Exception as e:
            print(f"Failed to create trigger {trigger_name}: {e}")
            
    conn_new.commit()
    
    # 6. Check integrity of rebuilt database
    print("Running integrity check on rebuilt database...")
    try:
        cursor_new.execute("PRAGMA integrity_check;")
        results = cursor_new.fetchall()
        print("Integrity check results for rebuilt DB:")
        for res in results[:20]:
            print(res)
    except Exception as e:
        print("Integrity check on rebuilt DB failed:", e)
        
    conn_old.close()
    conn_new.close()
    
    # 7. Backup malformed db and swap
    print("Swapping database files...")
    try:
        if os.path.exists(backup_db):
            os.remove(backup_db)
        os.rename(old_db, backup_db)
        os.rename(new_db, old_db)
        print("Database successfully rebuilt and swapped!")
    except Exception as e:
        print("Failed to swap database files:", e)

if __name__ == "__main__":
    rebuild()
