from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///bankbot.db"

engine = create_engine(
    DATABASE_URL,
    future=True,
    echo=False
)

SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()


def create_db():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)

