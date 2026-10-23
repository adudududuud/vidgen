"""yt-dlp subprocess-free integration. Enable only for content you have rights to download.

PUBLIC INTERNET WARNING: app-level validation is defense-in-depth, not sufficient SSRF
protection. For a public deployment, block private, loopback and link-local egress from
the downloader container via host firewall / egress proxy / separate network policy.
"""
import shutil
import time
from pathlib import Path
from .config import get_settings
from . import db
from .security import validate_url


class UserDownloadError(Exception):
    pass


def download_media(url: str, task_dir: Path, progress_callback):
    validate_url(url, resolve_dns=True)
    try:
        import yt_dlp
    except ImportError:
        raise UserDownloadError('尚未安装 yt-dlp，请先完成依赖安装') from None
    cfg = get_settings()
    task_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    max_bytes = cfg.max_mb * 1024 * 1024
    last_report = [-1, 0.0]

    def progress(info):
        if time.monotonic() - started > 10 * 60:
            raise UserDownloadError('任务超时，请重新尝试')
        downloaded = info.get('downloaded_bytes') or 0
        if downloaded > max_bytes:
            raise UserDownloadError('文件超过大小限制')
        total = info.get('total_bytes') or info.get('total_bytes_estimate') or 0
        if total > max_bytes:
            raise UserDownloadError('文件超过大小限制')
        if total:
            pct = min(97, int(100 * downloaded / total))
            if pct >= last_report[0] + 3 or time.monotonic() - last_report[1] > 2:
                progress_callback(pct)
                last_report[:] = [pct, time.monotonic()]

    def match_filter(info, *, incomplete=False):
        if info.get('is_live') or info.get('live_status') in ('is_live', 'is_upcoming'):
            return '不支持直播下载'
        if info.get('duration') and info['duration'] > cfg.max_seconds:
            return '视频时长超过允许上限'
        return None

    options = {
        'outtmpl': str(task_dir / '%(title).90s-%(id)s.%(ext)s'),
        'format': 'bv*[height<=720]+ba/b[height<=720]/b',
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'max_downloads': 1,
        'max_filesize': max_bytes,
        'match_filter': match_filter,
        'progress_hooks': [progress],
        'restrictfilenames': True,
        'socket_timeout': 15,
        'retries': 2,
        'fragment_retries': 2,
        'quiet': True,
        'no_warnings': True,
        'cachedir': False,
        'js_runtimes': {'node': {}},  # YouTube EJS requires supported external JS runtime
        'nopart': False,
        'nocheckcertificate': False,
        'writesubtitles': False,
        'writethumbnail': False,
    }
    with yt_dlp.YoutubeDL(options) as downloader:
        downloader.download([url])
    files = [p for p in task_dir.iterdir() if p.is_file() and p.suffix.lower() in {'.mp4', '.webm', '.mkv', '.mov', '.m4a', '.mp3'}]
    if not files:
        raise UserDownloadError('未生成可下载的视频文件，可能需要 FFmpeg 或源站暂不可用')
    media = max(files, key=lambda p: p.stat().st_size)
    if media.stat().st_size > max_bytes:
        raise UserDownloadError('视频文件超过大小限制')
    return media


def execute_job(job_id):
    record = db.get(job_id)
    if not record:
        return
    cfg = get_settings()
    target = cfg.download_dir / job_id
    db.update(job_id, status='running', progress=1)
    try:
        media = download_media(record['source_url'], target, lambda n: db.update(job_id, progress=n))
        if not media.is_file() or media.resolve().parent != target.resolve():
            raise UserDownloadError('文件路径校验失败')
        db.update(job_id, status='done', progress=100, filename=media.name)
    except Exception as exc:
        # Avoid showing internal full tracebacks to end users.
        safe_message = str(exc)
        if len(safe_message) > 160:
            safe_message = safe_message[:157] + '...'
        db.update(job_id, status='error', error=safe_message or '下载失败')
        shutil.rmtree(target, ignore_errors=True)


def cleanup_expired():
    cfg = get_settings()
    for record in db.expired():
        shutil.rmtree(cfg.download_dir / record['id'], ignore_errors=True)
        db.remove(record['id'])
