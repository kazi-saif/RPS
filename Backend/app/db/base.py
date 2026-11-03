from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """Shared metadata. Import app.models before initializing the database."""
    pass
