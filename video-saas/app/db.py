"""SQLite job store (single application worker / process)."""
import sqlite3
import time
from contextlib import contextmanager
from .config import get_settings


@contextmanager
def connect():
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(str(settings.data_dir / 'jobs.sqlite3'), timeout=20)
    cx.row_factory = sqlite3.Row
    try:
        yield cx
        cx.commit()
    finally:
        cx.close()


def init_db():
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('''CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, token_hash TEXT NOT NULL, source_url TEXT NOT NULL,
            ip_hash TEXT NOT NULL, status TEXT NOT NULL, progress INTEGER DEFAULT 0,
            filename TEXT, error TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL,
            expires_at REAL NOT NULL
        )''')
        db.execute('CREATE INDEX IF NOT EXISTS jobs_ip_created ON jobs(ip_hash,created_at)')
        db.execute('CREATE INDEX IF NOT EXISTS jobs_expiry ON jobs(expires_at)')


def recover_jobs():
    with connect() as db:
        db.execute("UPDATE jobs SET status='error', error='服务重启，请重新提交任务' WHERE status IN ('running','queued')")


def create(job_id, secret_hash, url, ip_hash):
    now = time.time()
    settings = get_settings()
    with connect() as db:
        cnt = db.execute('SELECT count(*) FROM jobs WHERE ip_hash=? AND created_at>?', (ip_hash, now-86400)).fetchone()[0]
        if cnt >= settings.daily_limit:
            return False
        db.execute('''INSERT INTO jobs(id,token_hash,source_url,ip_hash,status,progress,created_at,updated_at,expires_at)
            VALUES (?,?,?,?,'queued',0,?,?,?)''', (job_id, secret_hash, url, ip_hash, now, now, now+settings.ttl_hours*3600))
        return True


def get(job_id):
    with connect() as db:
        v = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        return dict(v) if v else None


def update(job_id, status=None, progress=None, filename=None, error=None):
    values = {'updated_at': time.time()}
    if status is not None: values['status'] = status
    if progress is not None: values['progress'] = max(0, min(100, int(progress)))
    if filename is not None: values['filename'] = filename
    if error is not None: values['error'] = str(error)[:350]
    sql = 'UPDATE jobs SET ' + ','.join(f'{k}=?' for k in values) + ' WHERE id=?'
    with connect() as db:
        db.execute(sql, (*values.values(), job_id))


def list_jobs(limit=100):
    with connect() as db:
        return [dict(x) for x in db.execute('SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?', (limit,)).fetchall()]


def stats():
    with connect() as db:
        return {'total': db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],
                'completed': db.execute("SELECT COUNT(*) FROM jobs WHERE status='done'").fetchone()[0],
                'failed': db.execute("SELECT COUNT(*) FROM jobs WHERE status='error'").fetchone()[0],
                'pending': db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('running','queued')").fetchone()[0]}


def remove(job_id):
    with connect() as db:
        db.execute('DELETE FROM jobs WHERE id=?', (job_id,))


def expired():
    with connect() as db:
        return [dict(x) for x in db.execute("SELECT * FROM jobs WHERE expires_at<? AND status NOT IN ('queued','running')", (time.time(),))]
