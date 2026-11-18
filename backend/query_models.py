import sqlite3

conn = sqlite3.connect("data/yolowebagent-starter.db")
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%model%'")
print("TABLES:", [r[0] for r in cur.fetchall()])
try:
    cur.execute(
        "SELECT id, name, status, dataset_id, artifact_type, format, model_path, created_at, archived_at FROM model_versions ORDER BY created_at DESC"
    )
    rows = cur.fetchall()
    print("COUNT:", len(rows))
    for r in rows:
        print(r)
except Exception as e:
    print("ERR", e)