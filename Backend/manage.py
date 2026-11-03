"""Local setup and backup commands. Run from the Backend directory."""
import argparse
import getpass
import sqlite3
import re
from datetime import datetime
from pathlib import Path
from sqlalchemy import select
from app.db.base import Base
from app.db.migrations import initialize_database
from app.db.session import engine, SessionLocal
from app.models import User
from app.core.security import hash_password

parser = argparse.ArgumentParser(description='Set up or back up your Result Processing System')
parser.add_argument('command', choices=['init', 'create-admin', 'backup'])
parser.add_argument('--username', default='admin')
args = parser.parse_args()
if args.command == 'init':
    initialize_database(engine)
    print('Database ready.')
elif args.command == 'create-admin':
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,30}', args.username):
        raise SystemExit('Username must contain 1–30 letters, digits, underscores or hyphens.')
    initialize_database(engine)
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.username == args.username)):
            raise SystemExit('That username already exists.')
        password = getpass.getpass('Choose an admin password (at least 12 characters): ')
        if not 12 <= len(password) <= 128 or password != getpass.getpass('Confirm password: '):
            raise SystemExit('Passwords must match and contain 12–128 characters.')
        db.add(User(username=args.username, hashed_password=hash_password(password), role='admin', must_change_password=False))
        db.commit()
        print('Admin created. Start the server and sign in.')
else:
    if engine.dialect.name != 'sqlite':
        raise SystemExit('Use your database provider’s backup tool for non-SQLite databases.')
    source = Path(engine.url.database)
    if not source.exists():
        raise SystemExit('Initialize the database first.')
    folder = Path(__file__).parent / 'backups'
    folder.mkdir(exist_ok=True)
    target = folder / f'rps-{datetime.now():%Y%m%d-%H%M%S-%f}.sqlite3'
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dest:
        src.backup(dest)
    print(f'Backup saved to {target}')
