"""SQLite job store. Single-process MVP with safe, parameterized filters."""
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
            expires_at REAL NOT NULL, cancel_requested INTEGER NOT NULL DEFAULT 0
        )''')
        # Backward-compatible migration for databases created by V0.1.
        columns = {row['name'] for row in db.execute('PRAGMA table_info(jobs)').fetchall()}
        if 'cancel_requested' not in columns:
            db.execute('ALTER TABLE jobs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0')
        db.execute('CREATE INDEX IF NOT EXISTS jobs_ip_created ON jobs(ip_hash,created_at)')
        db.execute('CREATE INDEX IF NOT EXISTS jobs_expiry ON jobs(expires_at)')
        db.execute('CREATE INDEX IF NOT EXISTS jobs_status_created ON jobs(status,created_at)')


def recover_jobs():
    with connect() as db:
        db.execute("UPDATE jobs SET status='error', error='服务重启，请重新提交任务' WHERE status IN ('running','queued') AND cancel_requested=0")
        db.execute("UPDATE jobs SET status='cancelled', error='任务已取消' WHERE status IN ('running','queued') AND cancel_requested=1")


def create(job_id, secret_hash, url, ip_hash):
    now = time.time()
    settings = get_settings()
    with connect() as db:
        cnt = db.execute('SELECT count(*) FROM jobs WHERE ip_hash=? AND created_at>?', (ip_hash, now-86400)).fetchone()[0]
        if cnt >= settings.daily_limit:
            return False
        db.execute('''INSERT INTO jobs(id,token_hash,source_url,ip_hash,status,progress,created_at,updated_at,expires_at,cancel_requested)
            VALUES (?,?,?,?,'queued',0,?,?,?,0)''', (job_id, secret_hash, url, ip_hash, now, now, now+settings.ttl_hours*3600))
        return True


def get(job_id):
    with connect() as db:
        v = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        return dict(v) if v else None


def start_job(job_id):
    """Atomically claim a queued job; returns False if it was cancelled first."""
    now = time.time()
    with connect() as db:
        result = db.execute("UPDATE jobs SET status='running',progress=1,updated_at=? WHERE id=? AND status='queued' AND cancel_requested=0", (now, job_id))
        return result.rowcount == 1


def request_cancel(job_id):
    """Cancel queued work immediately or signal a running downloader to stop."""
    now = time.time()
    with connect() as db:
        row = db.execute('SELECT status FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            return None
        status = row['status']
        if status == 'queued':
            db.execute("UPDATE jobs SET status='cancelled',cancel_requested=1,error='任务已取消',updated_at=? WHERE id=? AND status='queued'", (now, job_id))
            return 'cancelled'
        if status == 'running':
            db.execute("UPDATE jobs SET cancel_requested=1,updated_at=? WHERE id=? AND status='running'", (now, job_id))
            return 'cancelling'
        return status


def is_cancel_requested(job_id):
    with connect() as db:
        row = db.execute('SELECT cancel_requested FROM jobs WHERE id=?', (job_id,)).fetchone()
        return bool(row and row['cancel_requested'])


def update(job_id, status=None, progress=None, filename=None, error=None):
    values = {'updated_at': time.time()}
    if status is not None: values['status'] = status
    if progress is not None: values['progress'] = max(0, min(100, int(progress)))
    if filename is not None: values['filename'] = filename
    if error is not None: values['error'] = str(error)[:350]
    sql = 'UPDATE jobs SET ' + ','.join(f'{k}=?' for k in values) + ' WHERE id=?'
    with connect() as db:
        db.execute(sql, (*values.values(), job_id))


def active_for_ip(ip_hash):
    with connect() as db:
        return db.execute("SELECT count(*) FROM jobs WHERE ip_hash=? AND status IN ('queued','running')", (ip_hash,)).fetchone()[0]


def _filters(status=None, search=None):
    where, params = [], []
    if status and status in ('queued', 'running', 'done', 'error', 'cancelled'):
        where.append('status=?')
        params.append(status)
    if search:
        where.append('source_url LIKE ?')
        params.append('%' + search[:200] + '%')
    return (' WHERE ' + ' AND '.join(where) if where else ''), params


def list_jobs(limit=100, offset=0, status=None, search=None):
    where, params = _filters(status, search)
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    with connect() as db:
        return [dict(x) for x in db.execute('SELECT * FROM jobs' + where + ' ORDER BY created_at DESC LIMIT ? OFFSET ?', (*params, limit, offset)).fetchall()]


def count_jobs(status=None, search=None):
    where, params = _filters(status, search)
    with connect() as db:
        return db.execute('SELECT COUNT(*) FROM jobs' + where, params).fetchone()[0]


def stats():
    with connect() as db:
        return {'total': db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],
                'completed': db.execute("SELECT COUNT(*) FROM jobs WHERE status='done'").fetchone()[0],
                'failed': db.execute("SELECT COUNT(*) FROM jobs WHERE status='error'").fetchone()[0],
                'cancelled': db.execute("SELECT COUNT(*) FROM jobs WHERE status='cancelled'").fetchone()[0],
                'pending': db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('running','queued')").fetchone()[0]}


def remove(job_id):
    with connect() as db:
        db.execute('DELETE FROM jobs WHERE id=?', (job_id,))


def expired():
    with connect() as db:
        return [dict(x) for x in db.execute("SELECT * FROM jobs WHERE expires_at<? AND status NOT IN ('queued','running')", (time.time(),))]
