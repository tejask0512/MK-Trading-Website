from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
try:
    # For SQLAlchemy 1.4+
    from sqlalchemy.orm import declarative_base
except ImportError:
    # For older SQLAlchemy versions
    from sqlalchemy.ext.declarative import declarative_base

# Create database engine
engine = create_engine(DATABASE_URL)

# Create session factory (using more compatible syntax)
Session = sessionmaker()
Session.configure(bind=engine)
SessionLocal = Session

# Create base class for models
Base = declarative_base()

# Database session dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()