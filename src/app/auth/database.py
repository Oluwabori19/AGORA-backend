"""Database connection and session management using SQLAlchemy with PostgreSQL."""

from sqlalchemy import create_engine, text
from sqlalchemy.sql import func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import QueuePool  # Connection pooling for better performance
from app.auth.config import settings

# Build PostgreSQL connection string from environment variables
SQL_DATABASE_URL = f"postgresql://{settings.DATABASE_USERNAME}:{settings.DATABASE_PASSWORD}@{settings.DATABASE_HOSTNAME}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}"

# Create database engine with connection pooling
# pool_size=20: maintain 20 persistent connections
# max_overflow=10: allow 10 additional temporary connections when pool is exhausted
# poolclass=QueuePool: thread-safe connection management
engine = create_engine(
    SQL_DATABASE_URL, pool_size=20, max_overflow=10, poolclass=QueuePool
)

# Session factory for creating database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for ORM models
Base = declarative_base()


def get_db():
    """Dependency injection function for database sessions.
    
    Returns a new database session and ensures it's properly closed after use.
    Used with FastAPI Depends() for automatic session management per request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def execute_sql_query(sql_query: str):
    """Execute raw SQL query and return results.
    
    Args:
        sql_query: Raw SQL query string with optional parameters
        
    Returns:
        SQLAlchemy result object with fetchone(), fetchall() methods
    """
    with engine.connect() as connection:
        result = connection.execute(text(sql_query))
        return result
