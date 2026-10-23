"""Restrict public submissions; container egress restrictions still required for production."""
import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import socket
import time
from urllib.parse import urlsplit
from fastapi import HTTPException
from .config import get_settings


def validate_url(url: str, *, resolve_dns: bool = True) -> str:
    if not isinstance(url, str) or len(url) > 2048 or any(c in url for c in '\r\n\t'):
        raise ValueError('链接过长或格式不正确')
    url = url.strip()
    try:
        p = urlsplit(url)
        host = (p.hostname or '').lower().rstrip('.')
        port = p.port
    except ValueError:
        raise ValueError('链接地址不合法') from None
    if p.scheme != 'https' or not host or port not in (None, 443) or p.username or p.password:
        raise ValueError('仅接受 HTTPS 的公开视频链接')
    if host not in get_settings().allowed_hosts or not re.fullmatch(r'[a-z0-9.-]+', host):
        raise ValueError('此网站暂未开放，请提交支持的网站链接')
    try:
        ipaddress.ip_address(host)
        raise ValueError('不支持 IP 地址形式的链接')
    except ValueError as exc:
        if str(exc).startswith('不支持'):
            raise
    if resolve_dns:
        try:
            ips = {entry[4][0] for entry in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
        except (OSError, ValueError):
            raise ValueError('无法解析该网站地址，请稍后重试') from None
        if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
            raise ValueError('目标地址不可访问')
    return url


def fingerprint(ip: str) -> str:
    return hmac.new(get_settings().app_secret.encode(), ip.encode(), hashlib.sha256).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def require_token(received: str, expected_hash: str) -> None:
    if not received or not hmac.compare_digest(token_hash(received), expected_hash):
        raise HTTPException(status_code=403, detail='无权访问该任务')


def sign_admin_session() -> str:
    data = str(int(time.time()))
    mac = hmac.new(get_settings().app_secret.encode(), data.encode(), hashlib.sha256).hexdigest()
    return data + '.' + mac


def require_admin(request) -> None:
    settings = get_settings()
    if not settings.admin_password or not settings.app_secret:
        raise HTTPException(status_code=503, detail='管理员凭据尚未配置')
    cookie = request.cookies.get('admin_session', '')
    try:
        timestamp_str, signature = cookie.split('.', 1)
        ts = int(timestamp_str)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=401, detail='请先登录管理后台') from None
    expected = hmac.new(settings.app_secret.encode(), timestamp_str.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature) or ts > time.time() + 60 or time.time() - ts > 8 * 3600:
        raise HTTPException(status_code=401, detail='登录已过期，请重新登录')
