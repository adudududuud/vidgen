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
    assert site.get('/healthz').json() == {'ok': True}
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
