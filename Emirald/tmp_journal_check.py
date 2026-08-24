import sqlite3, json
from pathlib import Path
p = Path('data/journal.sqlite')
if not p.exists():
    print('NO_JOURNAL')
    raise SystemExit
con = sqlite3.connect(p)
con.row_factory = sqlite3.Row
rows = con.execute("SELECT * FROM trades ORDER BY id DESC LIMIT 10").fetchall()
for r in rows:
    print(json.dumps({k: r[k] for k in r.keys()}, ensure_ascii=False))
con.close()
