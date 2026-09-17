"""认证与权限：PBKDF2 密码哈希 + HMAC 签名 token（无新依赖）。"""
import base64
import hashlib
import hmac
import json
import time

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User, UserRole

TOKEN_TTL = 7 * 24 * 3600  # 7 天
_bearer = HTTPBearer(auto_error=False)


# ---------- 密码 ----------

def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or base64.urlsafe_b64encode(
        hashlib.sha256(str(time.time_ns()).encode()).digest())[:16].decode()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, _ = stored.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(hash_password(password, salt), stored)


# ---------- Token（base64url(payload).hmac） ----------

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _sign(payload: str) -> str:
    secret = get_settings().secret_key.encode()
    return _b64(hmac.new(secret, payload.encode(), hashlib.sha256).digest())


def create_token(user: User) -> str:
    payload = _b64(json.dumps({
        "uid": user.id, "username": user.username, "role": user.role,
        "exp": int(time.time()) + TOKEN_TTL,
    }).encode())
    return f"{payload}.{_sign(payload)}"


def decode_token(token: str) -> dict | None:
    try:
        payload, sig = token.split(".", 1)
        if not hmac.compare_digest(sig, _sign(payload)):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if data.get("exp", 0) < time.time():
            return None
        return data
    except Exception:
        return None


# ---------- FastAPI 依赖 ----------

def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """要求登录。"""
    if not cred:
        raise HTTPException(401, "未登录")
    data = decode_token(cred.credentials)
    user = db.get(User, data["uid"]) if data else None
    if not user:
        raise HTTPException(401, "登录已失效，请重新登录")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """要求超管。"""
    if user.role != UserRole.ADMIN:
        raise HTTPException(403, "需要管理员权限")
    return user
