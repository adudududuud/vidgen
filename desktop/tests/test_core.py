from pathlib import Path
import sys
import threading
import types
import pytest
from desktop import core


@pytest.mark.parametrize('address', [
 'http://youtu.be/ixw8pLpXtYs', 'https://localhost/a',
 'https://www.youtube.com.evil.example/watch?v=x',
 'https://username:password@youtu.be/x',
 'https://youtu.be:8443/a', 'file:///etc/passwd',
 'https://127.0.0.1/test', 'https://youtu.be/test\nlocalhost'
])
def test_invalid_urls(address):
    with pytest.raises(ValueError): core.validate_video_url(address)


@pytest.mark.parametrize('address', ['https://youtu.be/ixw8pLpXtYs',
 'https://www.youtube.com/watch?v=ixw8pLpXtYs', 'https://v.douyin.com/short-link/'])
def test_valid_urls(address):
    assert core.validate_video_url(address) == address


def test_format_options():
    assert 'format' in core._format_options('mp4_720')
    assert core._format_options('mp3')['postprocessors'][0]['preferredcodec'] == 'mp3'
    with pytest.raises(ValueError): core._format_options('random')


def test_unique_target(tmp_path):
    (tmp_path / 'sample.mp4').write_bytes(b'a')
    assert core._unique_target(tmp_path, 'sample.mp4').name == 'sample (1).mp4'
    assert core._unique_target(tmp_path, '../../sample.mp4').name == 'sample (1).mp4'


class FakeYDL:
    opts = None
    def __init__(self, opts):
        FakeYDL.opts = opts
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def extract_info(self, url, download=False):
        return {'id':'ixw8pLpXtYs', 'title':'测试', 'duration':42, 'extractor_key':'Youtube'}
    def download(self, urls):
        target = Path(self.opts['outtmpl']).parent
        (target / 'sample.mp4').write_bytes(b'video')
        self.opts['progress_hooks'][0]({'status':'downloading','downloaded_bytes':50,'total_bytes':100})
        self.opts['progress_hooks'][0]({'status':'finished'})


@pytest.fixture
def mock_ytdlp(monkeypatch):
    monkeypatch.setitem(sys.modules, 'yt_dlp', types.SimpleNamespace(YoutubeDL=FakeYDL))
    return FakeYDL


def test_probe_only_metadata(mock_ytdlp):
    meta = core.probe_metadata('https://youtu.be/ixw8pLpXtYs')
    assert meta['id'] == 'ixw8pLpXtYs'
    assert meta['duration'] == 42
    assert FakeYDL.opts['skip_download'] is True


def test_download_moves_file_and_cleans_staging(tmp_path, mock_ytdlp):
    received = []
    final = core.download_video('https://youtu.be/ixw8pLpXtYs', tmp_path, 'mp4_720',
         lambda p, m: received.append(p))
    assert final.read_bytes() == b'video'
    assert final.parent == tmp_path
    assert received[-1] == 100
    assert not list(tmp_path.glob('.yingsu-*'))


def test_duplicate_doesnt_overwrite(tmp_path, mock_ytdlp):
    first = core.download_video('https://youtu.be/ixw8pLpXtYs', tmp_path, 'mp4_720')
    second = core.download_video('https://youtu.be/ixw8pLpXtYs', tmp_path, 'mp4_720')
    assert first != second
    assert first.read_bytes() == second.read_bytes() == b'video'


def test_cancel_in_progress_hook(tmp_path, mock_ytdlp):
    flag = threading.Event()
    def cancel_soon(percent, message):
        if percent == 50: flag.set()
    with pytest.raises(core.Cancelled):
        core.download_video('https://youtu.be/ixw8pLpXtYs', tmp_path, 'mp4_720', cancel_soon, flag)
    assert not list(tmp_path.glob('.yingsu-*'))
    assert not list(tmp_path.glob('*.mp4'))


def test_cancel_before_begin(tmp_path, mock_ytdlp):
    flag = threading.Event(); flag.set()
    with pytest.raises(core.Cancelled):
        core.download_video('https://youtu.be/ixw8pLpXtYs', tmp_path, 'mp4_720', cancel=flag)


def test_mp3_requires_ffmpeg(tmp_path, mock_ytdlp, monkeypatch):
    monkeypatch.setattr(core, '_binary', lambda name: None)
    with pytest.raises(RuntimeError, match='FFmpeg'):
        core.download_video('https://youtu.be/ixw8pLpXtYs', tmp_path, 'mp3')
