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
    'auto': '智能兼容（推荐 · 优先 MP4）',
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
    opts = {'noplaylist': True, 'retries': 5, 'fragment_retries': 5, 'extractor_retries': 3,
            'socket_timeout': 25, 'quiet': True, 'no_warnings': True,
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
    if mode == 'auto':
        return {'format': 'b[ext=mp4][height<=720]/bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b',
                'merge_output_format': 'mp4'}
    if mode == 'mp4_720':
        return {'format': 'b[ext=mp4][height<=720]/bv*[ext=mp4][height<=720]+ba[ext=m4a]/b[height<=720]/bv*+ba/b',
                'merge_output_format': 'mp4'}
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
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(validated, download=False)
    except Exception as exc:
        raise RuntimeError(explain_download_error(str(exc))) from None
    if not info or info.get('_type') == 'playlist':
        raise RuntimeError('无法读取单个视频信息')
    return {'title': str(info.get('title') or '未获取标题')[:160],
            'duration': int(info.get('duration') or 0),
            'extractor': str(info.get('extractor_key') or ''),
            'id': str(info.get('id') or '')}


def explain_download_error(message: str) -> str:
    """Convert upstream failures to actionable, non-bypass instructions."""
    m = message.lower()
    if any(v in m for v in ('not a bot', 'confirm you’re not a bot', 'confirm you\'re not a bot',
                            'sign in', 'sign-in', 'login required', 'login to confirm', 'cookies')):
        return '该视频需要登录或人机验证，公开下载暂不可用。请确认在浏览器中可正常观看；程序不绕过登录及验证限制。'
    if any(v in m for v in ('drm', 'widevine', 'protected content')):
        return '来源视频受到 DRM 或访问控制保护，本程序不提供解除保护的功能。'
    if any(v in m for v in ('video unavailable', 'private video', 'is private', 'members-only', 'removed by', 'not available in your country')):
        return '视频可能已删除、设为私密、仅限会员或存在地区限制，无法公开下载。'
    if any(v in m for v in ('http error 429', 'too many requests', 'rate limit')):
        return '来源站点限制了请求频率（429）。请稍后再试，不建议频繁重试。'
    if any(v in m for v in ('http error 403', '403 forbidden', 'access denied')):
        return '来源网站拒绝了本次访问（403）。请检查网络、视频权限或稍后重试。'
    if any(v in m for v in ('requested format is not available', 'requested format not available', 'no video formats found')):
        return '该视频没有当前选项可用的格式。请尝试“智能兼容”或“原始最佳格式”。'
    if any(v in m for v in ('ffmpeg is not installed', 'ffmpeg not found', 'postprocessing: ffmpeg')):
        return '音视频合并或转换需要 FFmpeg。请重新安装完整 Windows 版本。'
    if any(v in m for v in ('timed out', 'timeout', 'network is unreachable', 'name resolution')):
        return '网络连接超时或无法解析站点地址，请检查网络后重试。'
    if 'unsupported url' in m or 'no suitable extractor' in m:
        return '当前 yt-dlp 版本暂不支持这个链接，请确认地址有效并更新软件。'
    return '下载未完成。请检查视频权限、网络或尝试“智能兼容”格式。错误摘要：' + message[:190]


def is_format_failure(message: str) -> bool:
    m = message.lower()
    return any(v in m for v in ('requested format is not available', 'requested format not available'))


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
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([validated])
        except Exception as exc:
            if cancel.is_set():
                raise Cancelled('任务已取消') from exc
            if mode in ('auto', 'mp4_720', 'mp4_best') and is_format_failure(str(exc)):
                # Only retry an unavailable *format*, never a login / 403 / DRM error.
                # Remove fragments created by the unsuccessful attempt.
                for item in staging.iterdir():
                    if item.is_file():
                        item.unlink(missing_ok=True)
                notify(0, '该视频没有预选格式，改用原始格式重试一次…')
                fallback = dict(opts, format='bv*+ba/b')
                fallback.pop('merge_output_format', None)
                try:
                    with yt_dlp.YoutubeDL(fallback) as ydl:
                        ydl.download([validated])
                except Exception as retry_exc:
                    if cancel.is_set():
                        raise Cancelled('任务已取消') from retry_exc
                    raise RuntimeError(explain_download_error(str(retry_exc))) from None
            else:
                raise RuntimeError(explain_download_error(str(exc))) from None
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
