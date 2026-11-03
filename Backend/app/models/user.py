import secrets
from sqlalchemy import Column, Integer, String, Boolean, CheckConstraint, UniqueConstraint, BigInteger
from app.db.base import Base
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(30), unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False)
    reference_id = Column(String, nullable=True)
    must_change_password = Column(Boolean, nullable=False, default=True)
    token_version = Column(BigInteger, nullable=False, default=lambda: secrets.randbits(52))
    __table_args__ = (UniqueConstraint('role', 'reference_id', name='uq_users_role_reference'), CheckConstraint("role IN ('admin', 'teacher', 'student')"),)
