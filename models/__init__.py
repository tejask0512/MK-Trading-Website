from models.base import Base, engine
from models.subscription import Subscription

# Create all tables
def init_db():
    Base.metadata.create_all(bind=engine)
