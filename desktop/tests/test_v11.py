from pathlib import Path
import sys
import threading
import types
from unittest.mock import MagicMock
import pytest
from desktop import core, dpi, __version__


def test_version():
    assert __version__ == '1.1.0'


def test_auto_compatibility_mode_is_default_first():
    assert next(iter(core.MODES)) == 'auto'
    assert 'format' in core._format_options('auto')
    assert 'mp4' in core._format_options('auto')['format']


@pytest.mark.parametrize('raw,expected', [
    ('ERROR: Sign in to confirm you’re not a bot.', '人机验证'),
    ('HTTP Error 403: Forbidden', '403'),
    ('HTTP Error 429: Too Many Requests', '429'),
    ('Requested format is not available', '智能兼容'),
    ('DRM protected video', 'DRM'),
    ('ERROR: Video unavailable', '私密'),
    ('Operation timed out', '超时'),
    ('ffmpeg not found', 'FFmpeg'),
])
def test_error_messages(raw, expected):
    assert expected in core.explain_download_error(raw)


def test_format_retry_only_on_format_errors():
    assert core.is_format_failure('Requested format is not available')
    assert not core.is_format_failure('Sign in to confirm you are not a bot')
    assert not core.is_format_failure('HTTP Error 403: Forbidden')


class RetryYDL:
    attempts = []
    def __init__(self, options):
        self.options = options
        type(self).attempts.append(options['format'])
    def __enter__(self): return self
    def __exit__(self, *args): return None
    def download(self, urls):
        if len(type(self).attempts) == 1:
            raise RuntimeError('Requested format is not available')
        Path(self.options['outtmpl']).parent.joinpath('fallback.webm').write_bytes(b'data')


def test_automatic_format_retry(tmp_path, monkeypatch):
    RetryYDL.attempts = []
    monkeypatch.setitem(sys.modules, 'yt_dlp', types.SimpleNamespace(YoutubeDL=RetryYDL))
    file = core.download_video('https://youtu.be/ixw8pLpXtYs', tmp_path, 'auto')
    assert file.name == 'fallback.webm'
    assert file.read_bytes() == b'data'
    assert len(RetryYDL.attempts) == 2
    assert not list(tmp_path.glob('.yingsu-*'))


class ForbiddenYDL(RetryYDL):
    attempts = []
    def download(self, urls):
        raise RuntimeError('HTTP Error 403: Forbidden')


def test_never_retry_forbidden(tmp_path, monkeypatch):
    ForbiddenYDL.attempts = []
    monkeypatch.setitem(sys.modules, 'yt_dlp', types.SimpleNamespace(YoutubeDL=ForbiddenYDL))
    with pytest.raises(RuntimeError, match='403'):
        core.download_video('https://youtu.be/ixw8pLpXtYs', tmp_path, 'auto')
    assert len(ForbiddenYDL.attempts) == 1


def test_dpi_non_windows(monkeypatch):
    monkeypatch.setattr(dpi.sys, 'platform', 'linux')
    assert dpi.enable_high_dpi() == 'not-windows'


def test_long_nonstandard_error_is_bounded():
    assert len(core.explain_download_error('unexpected ' * 100)) <= 240
