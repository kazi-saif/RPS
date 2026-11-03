import os
import secrets
from pathlib import Path
from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash

# Retain a random local key across restarts. Never commit this file.
key_path = Path(__file__).resolve().parents[2] / '.jwt-secret'
SECRET_KEY = os.getenv('RPS_SECRET_KEY')
if not SECRET_KEY:
    try:
        with open(key_path, 'x', opener=lambda path, flags: os.open(path, flags, 0o600)) as file:
            file.write(secrets.token_urlsafe(48))
    except FileExistsError:
        pass
    SECRET_KEY = key_path.read_text().strip()
if len(SECRET_KEY) < 32:
    raise RuntimeError('RPS_SECRET_KEY must contain at least 32 characters')
password_hash = PasswordHash.recommended()
def hash_password(password):
    return password_hash.hash(password)
def verify_password(password, hashed_password):
    try:
        return password_hash.verify(password, hashed_password)
    except Exception:
        return False

def create_access_token(data):
    return jwt.encode({**data, 'exp': datetime.now(timezone.utc) + timedelta(hours=1)}, SECRET_KEY, algorithm='HS256')
def decode_access_token(token):
    return jwt.decode(token, SECRET_KEY, algorithms=['HS256'], options={'require': ['exp', 'sub', 'ver']})
