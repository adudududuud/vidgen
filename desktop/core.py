"""Platform-independent download engine used by the desktop application.

Only use with media that the user has permission to download and where the
source platform permits such use. No login-cookie harvesting, DRM bypass or
client-server service is provided.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit
import os
import shutil
import sys
import tempfile
import threading

VALID_HOSTS = {
    'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com',
    'youtu.be', 'www.youtu.be', 'douyin.com', 'www.douyin.com',
    'v.douyin.com', 'iesdouyin.com', 'www.iesdouyin.com',
}
MODES = {
    'mp4_720': 'MP4 视频（优先 720P，无需合并）',
    'mp4_best': 'MP4 高清视频（可能需要音视频合并）',
    'original': '原始最佳格式（可能是 MKV/WebM）',
    'mp3': 'MP3 音频（需要 FFmpeg）',
}


class Cancelled(Exception):
    """Download cancelled via user action."""


def validate_video_url(url: str) -> str:
    """Only accept allow-listed, normal HTTPS URLs. No local network targets."""
    if not isinstance(url, str):
        raise ValueError('请粘贴视频链接')
    url = url.strip()
    if len(url) > 2048 or any(c in url for c in '\r\n\t\\'):
        raise ValueError('链接格式有误或长度超过限制')
    try:
        p = urlsplit(url)
        host = (p.hostname or '').lower().rstrip('.')
        port = p.port
    except ValueError:
        raise ValueError('链接格式有误') from None
    if p.scheme != 'https' or host not in VALID_HOSTS or p.username or p.password or port not in (None, 443):
        raise ValueError('仅支持白名单内的 YouTube / 抖音 HTTPS 链接')
    return url


def _resource_dir() -> Path:
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))


def _binary(name: str) -> str | None:
    ext = '.exe' if os.name == 'nt' else ''
    locations = [_resource_dir() / 'bin' / (name + ext), Path(sys.executable).resolve().parent / 'bin' / (name + ext)]
    for path in locations:
        if path.is_file():
            return str(path)
    return shutil.which(name)


def runtime_options() -> dict:
    opts = {'noplaylist': True, 'retries': 3, 'fragment_retries': 3,
            'socket_timeout': 20, 'quiet': True, 'no_warnings': True,
            'cachedir': False, 'restrictfilenames': True,
            'ignoreerrors': False, 'nocheckcertificate': False}
    node = _binary('node')
    if node:
        opts['js_runtimes'] = {'node': {'path': node}}
    ffmpeg = _binary('ffmpeg')
    if ffmpeg:
        opts['ffmpeg_location'] = str(Path(ffmpeg).parent)
    return opts


def _format_options(mode: str) -> dict:
    if mode == 'mp4_720':
        return {'format': 'best[ext=mp4][height<=720]/best[height<=720]/best[ext=mp4]/best'}
    if mode == 'mp4_best':
        return {'format': 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b', 'merge_output_format': 'mp4'}
    if mode == 'original':
        return {'format': 'bv*+ba/b'}
    if mode == 'mp3':
        return {'format': 'bestaudio/best', 'postprocessors': [{
            'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]}
    raise ValueError('不支持所选下载格式')


def probe_metadata(url: str) -> dict:
    """Read video metadata without downloading media bytes."""
    validated = validate_video_url(url)
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError('yt-dlp 尚未安装或未正确打包') from exc
    opts = runtime_options()
    opts.update({'skip_download': True, 'extract_flat': False, 'simulate': True})
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(validated, download=False)
    if not info or info.get('_type') == 'playlist':
        raise RuntimeError('无法读取单个视频信息')
    return {'title': str(info.get('title') or '未获取标题')[:160],
            'duration': int(info.get('duration') or 0),
            'extractor': str(info.get('extractor_key') or ''),
            'id': str(info.get('id') or '')}


def _unique_target(directory: Path, filename: str) -> Path:
    safe = Path(filename).name
    base = directory / safe
    if not base.exists():
        return base
    for i in range(1, 10000):
        target = directory / f'{base.stem} ({i}){base.suffix}'
        if not target.exists():
            return target
    raise RuntimeError('同名文件数量过多')


def download_video(url: str, directory: str | Path, mode: str, progress=None,
                   cancel: threading.Event | None = None) -> Path:
    """Run a one-video download and atomically move its final file into directory.

    progress receives (percentage:int, message:str). Cancellation takes effect
    when yt-dlp next fires a progress/postprocessor hook.
    """
    validated = validate_video_url(url)
    options = _format_options(mode)
    if mode == 'mp3' and not _binary('ffmpeg'):
        raise RuntimeError('音频转 MP3 需要 FFmpeg，请使用安装包自带版本')
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError('yt-dlp 尚未安装或未正确打包') from exc
    folder = Path(directory).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    cancel = cancel or threading.Event()
    if cancel.is_set():
        raise Cancelled('任务已取消')
    def notify(pct, message):
        if progress is not None:
            progress(max(0, min(100, int(pct))), message)

    def hook(info):
        if cancel.is_set():
            raise Cancelled('用户取消下载')
        if info.get('status') == 'finished':
            notify(98, '下载完成，正在处理文件…')
            return
        downloaded = info.get('downloaded_bytes') or 0
        total = info.get('total_bytes') or info.get('total_bytes_estimate') or 0
        if total:
            notify(min(97, int(downloaded * 100 / total)), '正在下载…')

    def post_hook(info):
        if cancel.is_set():
            raise Cancelled('用户取消处理')
        if info.get('status') == 'started':
            notify(98, '正在合并或转换媒体…')

    staging = Path(tempfile.mkdtemp(prefix='.yingsu-', dir=str(folder)))
    try:
        opts = runtime_options()
        opts.update(options)
        opts.update({'outtmpl': str(staging / '%(title).100s [%(id)s].%(ext)s'),
                     'progress_hooks': [hook], 'postprocessor_hooks': [post_hook],
                     'windowsfilenames': True, 'overwrites': False})
        notify(0, '正在读取视频信息…')
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([validated])
        if cancel.is_set():
            raise Cancelled('任务已取消')
        candidates = [p for p in staging.iterdir() if p.is_file() and p.suffix.lower()
                      in {'.mp4', '.mkv', '.webm', '.mov', '.m4a', '.mp3', '.flv', '.avi'}]
        if not candidates:
            raise RuntimeError('未生成媒体文件。请检查视频权限、网络或 FFmpeg 配置')
        chosen = max(candidates, key=lambda p: p.stat().st_size)
        final = _unique_target(folder, chosen.name)
        shutil.move(str(chosen), str(final))
        notify(100, '已保存：' + final.name)
        return final
    except Exception as exc:
        if cancel.is_set():
            raise Cancelled('任务已取消') from exc
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
