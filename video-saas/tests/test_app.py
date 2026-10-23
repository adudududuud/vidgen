import time
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def site(tmp_path, monkeypatch):
    monkeypatch.setenv('APP_SECRET', 'test-secret-only-' * 5)
    monkeypatch.setenv('ADMIN_PASSWORD', 'correct-horse-battery-test')
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setenv('DOWNLOAD_DIR', str(tmp_path / 'downloads'))
    monkeypatch.setenv('DAILY_LIMIT', '2')
    monkeypatch.setenv('SITE_URL', 'http://localhost:8000')
    monkeypatch.setenv('ADSENSE_ENABLED', 'false')
    from app import main, security, db
    monkeypatch.setattr(main, 'validate_url', lambda url: security.validate_url(url, resolve_dns=False))

    def fake_job(job_id):
        from pathlib import Path
        job_dir = tmp_path / 'downloads' / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / 'sample.mp4').write_bytes(b'demo-media')
        db.update(job_id, status='done', progress=100, filename='sample.mp4')

    monkeypatch.setattr(main.worker, 'execute_job', fake_job)
    app = main.create_app()
    with TestClient(app) as client:
        yield client


def start(client, url='https://www.youtube.com/watch?v=demo', confirmed=True):
    return client.post('/api/jobs', json={'url': url, 'confirmed_rights': confirmed})


def test_homepage_and_config(site):
    assert site.get('/').status_code == 200
    assert '视频素材' in site.get('/').text
    assert site.get('/healthz').json() == {'ok': True, 'version': '0.3.0'}
    cfg = site.get('/api/config').json()
    assert cfg['daily_limit'] == 2
    assert cfg['adsense_enabled'] is False
    assert site.get('/ads.txt').status_code == 404


def test_requires_rights(site):
    result = start(site, confirmed=False)
    assert result.status_code == 422


def test_rejects_foreign_hosts(site):
    assert start(site, 'https://127.0.0.1/internal').status_code == 422
    assert start(site, 'https://www.youtube.com.evil.com/test').status_code == 422
    assert start(site, 'http://www.youtube.com/watch?v=demo').status_code == 422
    assert start(site, 'https://www.youtube.com:444/test').status_code == 422


def test_job_end_to_end_mocked(site):
    resp = start(site)
    assert resp.status_code == 202
    job = resp.json()
    id, token = job['job_id'], job['access_token']
    assert site.get(f'/api/jobs/{id}').status_code == 403
    assert site.get(f'/api/jobs/{id}', headers={'X-Job-Token': 'bad-token'}).status_code == 403
    for _ in range(100):
        status = site.get(f'/api/jobs/{id}', headers={'X-Job-Token': token})
        if status.json()['status'] == 'done':
            break
        time.sleep(0.01)
    assert status.status_code == 200
    assert status.json()['status'] == 'done'
    file = site.get(f'/api/files/{id}', params={'token': token})
    assert file.status_code == 200
    assert file.content == b'demo-media'
    assert site.get(f'/api/files/{id}', params={'token': 'bad'}).status_code == 403


def test_limit(site):
    assert start(site).status_code == 202
    assert start(site).status_code == 202
    assert start(site).status_code == 429


def test_admin_auth_and_deletion(site):
    assert site.get('/api/admin/summary').status_code == 401
    assert site.post('/api/admin/login', json={'password': 'wrong'}).status_code == 401
    assert site.post('/api/admin/login', json={'password': 'correct-horse-battery-test'}).status_code == 200
    started = start(site).json()
    for _ in range(100):
        stats = site.get('/api/admin/summary')
        if stats.json()['completed'] == 1:
            break
        time.sleep(0.01)
    assert stats.status_code == 200
    assert stats.json()['total'] == 1
    jobs = site.get('/api/admin/jobs').json()['jobs']
    assert len(jobs) == 1
    assert 'token_hash' not in jobs[0]
    assert site.delete('/api/admin/jobs/' + started['job_id']).status_code == 200
    assert site.get('/api/admin/summary').json()['total'] == 0
    assert site.post('/api/admin/logout').status_code == 200
    assert site.get('/api/admin/summary').status_code == 401


def test_cancel_queued_and_signal_running(site):
    import uuid
    from app import db, security

    queued_id = str(uuid.uuid4())
    queued_secret = security.new_token()
    assert db.create(queued_id, security.token_hash(queued_secret), 'https://www.youtube.com/watch?v=queued', security.fingerprint('192.0.2.10'))
    cancelled = site.post(f'/api/jobs/{queued_id}/cancel', headers={'X-Job-Token': queued_secret})
    assert cancelled.status_code == 200
    assert cancelled.json()['status'] == 'cancelled'
    assert site.get(f'/api/jobs/{queued_id}', headers={'X-Job-Token': queued_secret}).json()['status'] == 'cancelled'
    assert db.start_job(queued_id) is False  # a cancelled queued job cannot be claimed by a worker
    assert db.get(queued_id)['status'] == 'cancelled'

    running_id = str(uuid.uuid4())
    running_secret = security.new_token()
    assert db.create(running_id, security.token_hash(running_secret), 'https://www.youtube.com/watch?v=running', security.fingerprint('192.0.2.11'))
    assert db.start_job(running_id)
    stopping = site.post(f'/api/jobs/{running_id}/cancel', headers={'X-Job-Token': running_secret})
    assert stopping.status_code == 200
    assert stopping.json()['status'] == 'cancelling'
    assert db.is_cancel_requested(running_id) is True


def test_retry_requires_rights_and_only_retries_failed_jobs(site):
    import uuid
    from app import db, security

    job_id = str(uuid.uuid4())
    secret = security.new_token()
    assert db.create(job_id, security.token_hash(secret), 'https://www.youtube.com/watch?v=retry', security.fingerprint('192.0.2.12'))
    db.update(job_id, status='error', error='simulated failure')
    headers = {'X-Job-Token': secret}
    assert site.post(f'/api/jobs/{job_id}/retry', headers=headers, json={'confirmed_rights': False}).status_code == 422
    retried = site.post(f'/api/jobs/{job_id}/retry', headers=headers, json={'confirmed_rights': True})
    assert retried.status_code == 202
    assert retried.json()['job_id'] != job_id
    assert retried.json()['access_token']
    assert site.post(f'/api/jobs/{retried.json()["job_id"]}/retry', headers={'X-Job-Token': retried.json()['access_token']}, json={'confirmed_rights': True}).status_code == 409


def test_admin_filter_and_csv_export(site):
    import uuid
    from app import db, security

    job_id = str(uuid.uuid4())
    secret = security.new_token()
    assert db.create(job_id, security.token_hash(secret), 'https://www.youtube.com/watch?v=csv-test', security.fingerprint('192.0.2.13'))
    db.update(job_id, status='cancelled', error='user cancelled')
    assert site.post('/api/admin/login', json={'password': 'correct-horse-battery-test'}).status_code == 200
    result = site.get('/api/admin/jobs?status=cancelled&q=csv-test')
    assert result.status_code == 200
    assert result.json()['total'] == 1
    assert result.json()['jobs'][0]['id'] == job_id
    export = site.get('/api/admin/jobs/export.csv?status=cancelled')
    assert export.status_code == 200
    assert 'text/csv' in export.headers['content-type']
    assert 'csv-test' in export.text
    assert site.get('/api/admin/summary').json()['cancelled'] == 1


def test_google_oauth_disabled_by_default_and_me_requires_login(site):
    cfg = site.get('/api/config').json()
    assert cfg['version'] == '0.3.0'
    assert cfg['google_oauth_enabled'] is False
    me = site.get('/api/me')
    assert me.status_code == 200
    assert me.json()['authenticated'] is False
    assert site.get('/auth/google').status_code == 503
    assert site.get('/api/me/jobs').status_code == 401


def test_google_user_storage_and_per_user_daily_quota(site):
    import uuid
    from app import db, security

    user = db.upsert_google_user('google-sub-test', 'tester@example.com', 'Test User', '')
    assert user['email'] == 'tester@example.com'
    assert user['is_active'] == 1
    iphash = security.fingerprint('192.0.2.44')
    for n in range(2):
        assert db.create(str(uuid.uuid4()), security.token_hash(security.new_token()),
                         f'https://www.youtube.com/watch?v=user-{n}', iphash, user_id=user['id'])
    assert db.create(str(uuid.uuid4()), security.token_hash(security.new_token()),
                     'https://www.youtube.com/watch?v=user-over-limit', iphash, user_id=user['id']) is False
    assert db.count_user_jobs(user['id']) == 2
    assert db.list_user_jobs(user['id'])


def test_admin_can_disable_google_user(site):
    from app import db
    user = db.upsert_google_user('google-sub-admin', 'member@example.com', 'Member', '')
    assert site.post('/api/admin/login', json={'password': 'correct-horse-battery-test'}).status_code == 200
    listing = site.get('/api/admin/users')
    assert listing.status_code == 200
    assert any(x['id'] == user['id'] for x in listing.json()['users'])
    result = site.patch(f"/api/admin/users/{user['id']}", json={'is_active': False})
    assert result.status_code == 200
    assert db.get_user(user['id'])['is_active'] == 0
    assert site.get('/api/admin/summary').json()['users'] == 1


def test_v02_database_migrates_to_v03_user_schema(tmp_path, monkeypatch):
    import sqlite3
    from app import db

    legacy_dir = tmp_path / 'legacy'
    legacy_dir.mkdir()
    monkeypatch.setenv('DATA_DIR', str(legacy_dir))
    cx = sqlite3.connect(legacy_dir / 'jobs.sqlite3')
    cx.execute('''CREATE TABLE jobs (
        id TEXT PRIMARY KEY, token_hash TEXT NOT NULL, source_url TEXT NOT NULL,
        ip_hash TEXT NOT NULL, status TEXT NOT NULL, progress INTEGER DEFAULT 0,
        filename TEXT, error TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL,
        expires_at REAL NOT NULL, cancel_requested INTEGER NOT NULL DEFAULT 0
    )''')
    cx.commit()
    cx.close()
    db.init_db()
    cx = sqlite3.connect(legacy_dir / 'jobs.sqlite3')
    columns = {r[1] for r in cx.execute('PRAGMA table_info(jobs)').fetchall()}
    tables = {r[0] for r in cx.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    cx.close()
    assert 'user_id' in columns
    assert 'users' in tables


def test_google_session_scopes_task_history_and_downloads(site, tmp_path, monkeypatch):
    import base64
    import json
    import uuid
    from itsdangerous import TimestampSigner
    from app import db, security

    own = db.upsert_google_user('google-sub-own', 'owner@example.com', 'Owner', '')
    other = db.upsert_google_user('google-sub-other', 'other@example.com', 'Other', '')
    own_id = str(uuid.uuid4())
    other_id = str(uuid.uuid4())
    own_token = security.new_token()
    other_token = security.new_token()
    iphash = security.fingerprint('192.0.2.50')
    assert db.create(own_id, security.token_hash(own_token), 'https://www.youtube.com/watch?v=own', iphash, user_id=own['id'])
    assert db.create(other_id, security.token_hash(other_token), 'https://www.youtube.com/watch?v=other', iphash, user_id=other['id'])
    db.update(own_id, status='done', progress=100, filename='own.mp4')
    db.update(other_id, status='done', progress=100, filename='other.mp4')
    own_dir = tmp_path / 'downloads' / own_id
    own_dir.mkdir(parents=True, exist_ok=True)
    (own_dir / 'own.mp4').write_bytes(b'owned-video')

    secret = 'test-secret-only-' * 5
    payload = base64.b64encode(json.dumps({'user_id': own['id']}).encode('utf-8'))
    cookie = TimestampSigner(secret).sign(payload).decode('utf-8')
    site.cookies.set('session', cookie)

    assert site.get('/api/me').json()['authenticated'] is True
    history = site.get('/api/me/jobs').json()
    assert history['total'] == 1
    assert history['jobs'][0]['id'] == own_id
    assert site.get(f'/api/jobs/{own_id}').status_code == 200
    assert site.get(f'/api/files/{own_id}').content == b'owned-video'
    assert site.get(f'/api/jobs/{other_id}').status_code == 403
