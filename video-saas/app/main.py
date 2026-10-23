"""Video SaaS API. Use one Uvicorn worker; the V0.2 queue remains process-local."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import csv
import hmac
import io
import re
import shutil
import time
import uuid
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import BASE, get_settings
from . import db, worker
from .security import validate_url, fingerprint, new_token, token_hash, require_token, require_admin, sign_admin_session


class CreateJob(BaseModel):
    url: str = Field(min_length=12, max_length=2048)
    confirmed_rights: bool


class RetryJob(BaseModel):
    confirmed_rights: bool


class Login(BaseModel):
    password: str


def public_job(job):
    return {name: job[name] for name in ('id','status','progress','filename','error','created_at','expires_at','cancel_requested')}


def create_app():
    pool = ThreadPoolExecutor(max_workers=get_settings().max_workers, thread_name_prefix='video-job')

    @asynccontextmanager
    async def lifespan(app):
        db.init_db()
        db.recover_jobs()
        worker.cleanup_expired()
        yield
        pool.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title='Video SaaS MVP', version='0.2.0', lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.login_attempts = {}
    app.mount('/static', StaticFiles(directory=str(BASE / 'static')), name='static')

    @app.middleware('http')
    async def headers(request: Request, call_next):
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Cache-Control'] = 'no-store' if request.url.path.startswith('/api/') else 'public, max-age=300'
        return response

    @app.get('/', include_in_schema=False)
    def homepage():
        return FileResponse(BASE / 'static' / 'index.html')

    @app.get('/admin', include_in_schema=False)
    def admin_page():
        return FileResponse(BASE / 'static' / 'admin.html')

    @app.get('/privacy', include_in_schema=False)
    def privacy_page():
        return FileResponse(BASE / 'static' / 'privacy.html')

    @app.get('/terms', include_in_schema=False)
    def terms_page():
        return FileResponse(BASE / 'static' / 'terms.html')

    @app.get('/healthz')
    def healthz():
        return {'ok': True, 'version': '0.2.0'}

    @app.get('/api/config')
    def config():
        cfg = get_settings()
        allow_ads = cfg.adsense_enabled and re.fullmatch(r'ca-pub-\d{10,25}', cfg.adsense_client) and re.fullmatch(r'\d{8,25}', cfg.adsense_slot)
        return {'version': '0.2.0', 'daily_limit': cfg.daily_limit, 'max_mb': cfg.max_mb, 'max_minutes': cfg.max_seconds // 60,
                'adsense_enabled': bool(allow_ads),
                'adsense_client': cfg.adsense_client if allow_ads else '',
                'adsense_slot': cfg.adsense_slot if allow_ads else '',
                'contact_email': cfg.public_contact}

    @app.get('/ads.txt')
    def ads_txt():
        cfg = get_settings()
        if not cfg.adsense_enabled or not re.fullmatch(r'ca-pub-\d{10,25}', cfg.adsense_client):
            raise HTTPException(404, '尚未启用广告')
        pub = cfg.adsense_client.replace('ca-', '')
        return PlainTextResponse(f'google.com, {pub}, DIRECT, f08c47fec0942fa0\n')

    def enqueue(url: str, iphash: str):
        active = db.active_for_ip(iphash)
        if active >= 2:
            raise HTTPException(429, '最多同时提交两个任务')
        worker.cleanup_expired()
        job_id = str(uuid.uuid4())
        secret = new_token()
        if not db.create(job_id, token_hash(secret), url, iphash):
            raise HTTPException(429, '今日免费额度已用完，请明天再来')
        pool.submit(worker.execute_job, job_id)
        return {'job_id': job_id, 'access_token': secret, 'status': 'queued'}

    @app.post('/api/jobs', status_code=202)
    def submit(body: CreateJob, request: Request):
        if not body.confirmed_rights:
            raise HTTPException(422, '仅支持您拥有权利或已获授权的视频素材')
        try:
            url = validate_url(body.url)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        if not get_settings().app_secret:
            raise HTTPException(503, '服务端 APP_SECRET 未配置')
        ip = request.client.host if request.client else 'unknown'
        return enqueue(url, fingerprint(ip))

    def authorized_job(job_id: str, token: str):
        job = db.get(job_id)
        if not job:
            raise HTTPException(404, '任务不存在或已经到期')
        require_token(token, job['token_hash'])
        if job['expires_at'] < time.time() and job['status'] not in ('queued','running'):
            raise HTTPException(410, '文件已经过期')
        return job

    @app.get('/api/jobs/{job_id}')
    def job_status(job_id: str, request: Request):
        job = authorized_job(job_id, request.headers.get('X-Job-Token', ''))
        return public_job(job)

    @app.post('/api/jobs/{job_id}/cancel')
    def cancel_job(job_id: str, request: Request):
        authorized_job(job_id, request.headers.get('X-Job-Token', ''))
        result = db.request_cancel(job_id)
        if result is None:
            raise HTTPException(404, '任务不存在')
        if result == 'done' or result == 'error':
            raise HTTPException(409, '任务已结束，不能取消')
        return {'ok': True, 'status': result, 'message': '正在取消任务' if result == 'cancelling' else '任务已取消'}

    @app.post('/api/jobs/{job_id}/retry', status_code=202)
    def retry_job(job_id: str, body: RetryJob, request: Request):
        old = authorized_job(job_id, request.headers.get('X-Job-Token', ''))
        if not body.confirmed_rights:
            raise HTTPException(422, '请确认您拥有该素材的下载权利或已取得授权')
        if old['status'] not in ('error', 'cancelled'):
            raise HTTPException(409, '只有失败或已取消的任务可以重试')
        if not get_settings().app_secret:
            raise HTTPException(503, '服务端 APP_SECRET 未配置')
        return enqueue(old['source_url'], old['ip_hash'])

    @app.get('/api/files/{job_id}')
    def file_download(job_id: str, token: str):
        job = authorized_job(job_id, token)
        if job['status'] != 'done' or not job['filename']:
            raise HTTPException(409, '视频尚未处理完成')
        root = (get_settings().download_dir / job_id).resolve()
        file = (root / job['filename']).resolve()
        if file.parent != root or not file.is_file():
            raise HTTPException(404, '视频文件不存在')
        return FileResponse(file, media_type='application/octet-stream', filename=file.name)

    @app.post('/api/admin/login')
    def admin_login(body: Login, request: Request):
        cfg = get_settings()
        if not cfg.app_secret or not cfg.admin_password:
            raise HTTPException(503, '未配置管理员账号')
        ip = request.client.host if request.client else 'unknown'
        now = time.time()
        recent = [n for n in app.state.login_attempts.get(ip, []) if n > now - 600]
        if len(recent) >= 5:
            raise HTTPException(429, '密码错误次数过多，10 分钟后再试')
        if not hmac.compare_digest(body.password, cfg.admin_password):
            recent.append(now)
            app.state.login_attempts[ip] = recent
            raise HTTPException(401, '密码不正确')
        app.state.login_attempts[ip] = []
        response = JSONResponse({'ok': True})
        response.set_cookie('admin_session', sign_admin_session(), max_age=8*3600,
                            secure=cfg.site_url.startswith('https://'), httponly=True, samesite='strict', path='/')
        return response

    @app.post('/api/admin/logout')
    def admin_logout(request: Request):
        require_admin(request)
        response = JSONResponse({'ok': True})
        response.delete_cookie('admin_session', path='/')
        return response

    @app.get('/api/admin/summary')
    def admin_summary(request: Request):
        require_admin(request)
        return db.stats()

    @app.get('/api/admin/jobs')
    def admin_jobs(request: Request, status: str = '', q: str = '', limit: int = 100, offset: int = 0):
        require_admin(request)
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        jobs = db.list_jobs(limit=limit, offset=offset, status=status or None, search=q or None)
        return {'jobs': [dict(public_job(j), source_url=j['source_url']) for j in jobs],
                'total': db.count_jobs(status=status or None, search=q or None), 'limit': limit, 'offset': offset}

    @app.get('/api/admin/jobs/export.csv')
    def admin_export_jobs(request: Request, status: str = '', q: str = ''):
        require_admin(request)
        output = io.StringIO(newline='')
        writer = csv.writer(output)
        writer.writerow(['任务ID', '提交时间', '状态', '进度', '来源链接', '文件名', '错误信息'])
        for job in db.list_jobs(limit=500, offset=0, status=status or None, search=q or None):
            writer.writerow([job['id'], time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(job['created_at'])),
                             job['status'], job['progress'], job['source_url'], job['filename'] or '', job['error'] or ''])
        return Response(content='\ufeff' + output.getvalue(), media_type='text/csv; charset=utf-8',
                        headers={'Content-Disposition': 'attachment; filename="video-saas-jobs.csv"'})

    @app.delete('/api/admin/jobs/{job_id}')
    def admin_delete(job_id: str, request: Request):
        require_admin(request)
        job = db.get(job_id)
        if not job:
            raise HTTPException(404, '任务不存在')
        if job['status'] in ('running','queued'):
            raise HTTPException(409, '正在运行的任务不能删除')
        shutil.rmtree(get_settings().download_dir / job_id, ignore_errors=True)
        db.remove(job_id)
        return {'ok': True}

    return app


app = create_app()
