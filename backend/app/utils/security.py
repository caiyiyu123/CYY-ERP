from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError
import bcrypt
from cryptography.fernet import Fernet
import base64
import hashlib

from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, FERNET_KEY

_fernet_key = base64.urlsafe_b64encode(hashlib.sha256(FERNET_KEY.encode()).digest())
_fernet = Fernet(_fernet_key)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def encrypt_token(plain_text: str) -> str:
    return _fernet.encrypt(plain_text.encode()).decode()


def decrypt_token(encrypted_text: str) -> str:
    return _fernet.decrypt(encrypted_text.encode()).decode()
