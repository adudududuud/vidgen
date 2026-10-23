"""Environment-based settings. Never commit a populated .env file."""
import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # lets tests run without fetching optional dependencies
    pass

BASE = Path(__file__).resolve().parent.parent


def as_int(name: str, default: int, minimum: int = 1, maximum: int = 100000) -> int:
    try:
        return max(minimum, min(maximum, int(os.getenv(name, str(default)))))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    download_dir: Path
    admin_password: str
    app_secret: str
    daily_limit: int
    max_workers: int
    max_mb: int
    max_seconds: int
    ttl_hours: int
    site_url: str
    public_contact: str
    adsense_enabled: bool
    adsense_client: str
    adsense_slot: str
    allowed_hosts: tuple[str, ...]


def get_settings() -> Settings:
    return Settings(
        data_dir=Path(os.getenv('DATA_DIR', str(BASE / 'data'))).resolve(),
        download_dir=Path(os.getenv('DOWNLOAD_DIR', str(BASE / 'downloads'))).resolve(),
        admin_password=os.getenv('ADMIN_PASSWORD', ''),
        app_secret=os.getenv('APP_SECRET', ''),
        daily_limit=as_int('DAILY_LIMIT', 5, 1, 500),
        max_workers=as_int('MAX_WORKERS', 2, 1, 4),
        max_mb=as_int('MAX_DOWNLOAD_MB', 250, 10, 2048),
        max_seconds=as_int('MAX_DURATION_SECONDS', 1200, 60, 7200),
        ttl_hours=as_int('FILE_TTL_HOURS', 6, 1, 168),
        site_url=os.getenv('SITE_URL', 'http://localhost:8000').rstrip('/'),
        public_contact=os.getenv('CONTACT_EMAIL', '请配置 CONTACT_EMAIL'),
        adsense_enabled=os.getenv('ADSENSE_ENABLED', 'false').lower() == 'true',
        adsense_client=os.getenv('ADSENSE_CLIENT', ''),
        adsense_slot=os.getenv('ADSENSE_SLOT', ''),
        allowed_hosts=tuple(x.strip().lower() for x in os.getenv(
            'ALLOWED_HOSTS',
            'youtube.com,www.youtube.com,m.youtube.com,youtu.be,douyin.com,www.douyin.com,v.douyin.com'
        ).split(',') if x.strip()),
    )
