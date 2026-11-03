#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/Backend"
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
if ! .venv/bin/python -c 'import fastapi, uvicorn, sqlalchemy, jwt, pwdlib, multipart, email_validator' 2>/dev/null; then
  .venv/bin/python -m pip install -r requirements.txt
fi
.venv/bin/python manage.py init
if ! .venv/bin/python -c 'from app.db.session import SessionLocal; from app.models import User; from sqlalchemy import select; db=SessionLocal(); raise SystemExit(0 if db.scalar(select(User.id).where(User.role=="admin").limit(1)) else 1)'; then
  .venv/bin/python manage.py create-admin
fi
printf '\nOpen http://127.0.0.1:%s in your browser. Press Ctrl+C here to stop.\n\n' "${RPS_PORT:-8001}"
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "${RPS_PORT:-8001}"
