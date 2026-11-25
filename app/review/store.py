import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from app.business import DomainIssue

SCHEMA = '''CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY, report TEXT NOT NULL, created TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING', revision INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '', reviewed TEXT
);
CREATE TABLE IF NOT EXISTS authorizations (
    run_id TEXT NOT NULL, entrust TEXT NOT NULL,
    revoked INTEGER NOT NULL DEFAULT 0, updated TEXT NOT NULL,
    PRIMARY KEY (run_id, entrust)
);'''


class Store:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=15)) as db, db:
            db.row_factory = sqlite3.Row
            for statement in SCHEMA.split(';'):
                if statement.strip():
                    db.execute(statement)
            yield db

    def register(self, run_id, report):
        with self.connect() as db:
            db.execute('INSERT INTO runs(id,report,created) VALUES (?,?,?) ON CONFLICT(id) DO NOTHING',
                       (run_id,json.dumps(report,ensure_ascii=False),report['manifest']['created']))
        return self.load(run_id)

    def load(self, run_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone()
        if row is None:
            raise DomainIssue('RUN_NOT_FOUND')
        result = dict(row)
        result['report'] = json.loads(result['report'])
        return result

    def list(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT id,created,status,revision,note FROM runs ORDER BY created DESC,id LIMIT 50')]

    def revise(self, run_id, revision, status, note, now):
        with self.connect() as db:
            cursor = db.execute('UPDATE runs SET status=?,note=?,reviewed=?,revision=revision+1 WHERE id=? AND revision=?',
                                (status, note, now, run_id, revision))
            if cursor.rowcount != 1:
                raise DomainIssue('STALE_REVIEW')
        return self.load(run_id)

    def is_revoked(self, run_id, entrust):
        with self.connect() as db:
            row = db.execute('SELECT revoked FROM authorizations WHERE run_id=? AND entrust=?',
                             (run_id, entrust)).fetchone()
        return bool(row and row['revoked'])

    def revoke(self, run_id, entrust, now):
        with self.connect() as db:
            db.execute('INSERT INTO authorizations(run_id,entrust,revoked,updated) VALUES (?,?,1,?) '
                       'ON CONFLICT(run_id,entrust) DO UPDATE SET revoked=1, updated=excluded.updated',
                       (run_id, entrust, now))
        return now

    def authorization_snapshot(self, run_id):
        with self.connect() as db:
            return {row['entrust']: bool(row['revoked'])
                    for row in db.execute('SELECT entrust,revoked FROM authorizations WHERE run_id=?', (run_id,))}
