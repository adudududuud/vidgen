import pytest
from app.security import validate_url

@pytest.mark.parametrize('url', [
    'http://www.youtube.com/watch?v=x',
    'https://localhost/admin',
    'https://127.0.0.1/',
    'https://youtube.com.attacker.example/test',
    'https://user:pass@youtube.com/watch',
    'https://youtube.com:444/watch',
    'file:///etc/passwd',
    'https://youtube.com/watch\nX-Header: anything',
])
def test_url_rejects_invalid(url):
    with pytest.raises(ValueError):
        validate_url(url, resolve_dns=False)


def test_valid_host():
    assert validate_url('https://youtu.be/abc123', resolve_dns=False) == 'https://youtu.be/abc123'
