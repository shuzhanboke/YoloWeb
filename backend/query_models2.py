import sqlite3

conn = sqlite3.connect("data/yolowebagent-starter.db")
cur = conn.cursor()

cur.execute("PRAGMA table_info(datasets)")
print("=== datasets cols ===")
for r in cur.fetchall():
    print(r)

cur.execute("SELECT * FROM datasets")
print("\n=== datasets rows ===")
for r in cur.fetchall():
    print(r)

print("\n=== models grouped by dataset_id ===")
cur.execute(
    "SELECT COALESCE(dataset_id,'(no dataset)') d, count(*) FROM model_versions GROUP BY d"
)
for r in cur.fetchall():
    print(r)