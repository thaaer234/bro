import sqlite3
import os
import shutil

db_name = 'db.sqlite3'
backup_name = 'db.sqlite3.corrupt_backup'

# 1. Make a backup of the current database file
if not os.path.exists(backup_name):
    print(f"Creating backup of {db_name} to {backup_name}...")
    shutil.copy2(db_name, backup_name)

# 2. Try VACUUM first
try:
    print("Attempting to run VACUUM...")
    conn = sqlite3.connect(db_name)
    conn.execute("VACUUM;")
    conn.close()
    print("VACUUM completed successfully! Checking integrity...")
    
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("PRAGMA integrity_check;")
    res = cursor.fetchall()
    conn.close()
    print("Integrity check results:", res)
    if res == [('ok',)]:
        print("Database successfully repaired using VACUUM!")
        exit(0)
except Exception as e:
    print(f"VACUUM failed: {e}")

# 3. If VACUUM failed or integrity check is still not ok, let's rebuild the database table by table
print("\nAttempting to rebuild database by copying tables to a new file...")
recovered_db = 'db_recovered.sqlite3'
if os.path.exists(recovered_db):
    os.remove(recovered_db)

conn_old = sqlite3.connect(db_name)
cursor_old = conn_old.cursor()

conn_new = sqlite3.connect(recovered_db)
cursor_new = conn_new.cursor()

# Get schema (tables and indices)
cursor_old.execute("SELECT sql, name, type FROM sqlite_master WHERE sql IS NOT NULL;")
schema_objects = cursor_old.fetchall()

# We want to create tables first, then copy data, then create indices
tables_schema = [obj for obj in schema_objects if obj[2] == 'table']
indices_schema = [obj for obj in schema_objects if obj[2] == 'index']

print(f"Found {len(tables_schema)} tables and {len(indices_schema)} indices.")

# Create all tables in the new database
for sql, name, type_ in tables_schema:
    if name.startswith('sqlite_'):
        continue
    try:
        cursor_new.execute(sql)
    except Exception as e:
        print(f"Error creating table {name}: {e}")

# Copy data table by table
for _, name, _ in tables_schema:
    if name.startswith('sqlite_'):
        continue
    print(f"Copying data for table: {name}...")
    try:
        # Fetch all from old
        cursor_old.execute(f"SELECT * FROM `{name}`;")
        rows = cursor_old.fetchall()
        if not rows:
            continue
            
        # Get placeholders
        placeholders = ', '.join(['?'] * len(rows[0]))
        # Insert into new
        cursor_new.executemany(f"INSERT INTO `{name}` VALUES ({placeholders});", rows)
        conn_new.commit()
    except Exception as e:
        print(f"Error copying table {name}: {e}")

# Create indices
print("Creating indices...")
for sql, name, _ in indices_schema:
    try:
        cursor_new.execute(sql)
    except Exception as e:
        print(f"Error creating index {name}: {e}")

# Run integrity check on new db
print("Running integrity check on recovered database...")
cursor_new.execute("PRAGMA integrity_check;")
res_new = cursor_new.fetchall()
print("Recovered database integrity check:", res_new)

conn_old.close()
conn_new.close()

if res_new == [('ok',)]:
    print("\nRecovery successful!")
    print(f"Replacing {db_name} with {recovered_db}...")
    
    # Try to rename instead of direct remove to bypass lock issues if any
    try:
        if os.path.exists('db.sqlite3.old'):
            os.remove('db.sqlite3.old')
        os.rename(db_name, 'db.sqlite3.old')
        os.rename(recovered_db, db_name)
        print("Database replaced successfully.")
    except Exception as e:
        print(f"Failed to replace file directly (database might be in use). Error: {e}")
        print(f"Please manually close the server and rename '{recovered_db}' to '{db_name}'.")
else:
    print("Rebuilt database is still not fully healthy or has errors.")
