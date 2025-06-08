from models.base import SessionLocal
from models.subscription import Subscription

def get_all_subscriptions():
    db = SessionLocal()
    try:
        return db.query(Subscription).all()
    finally:
        db.close()

def get_subscription_by_id(subscription_id):
    db = SessionLocal()
    try:
        return db.query(Subscription).filter(Subscription.id == subscription_id).first()
    finally:
        db.close()

def create_subscription(name, price, duration, features):
    db = SessionLocal()
    try:
        db_subscription = Subscription(
            name=name,
            price=price,
            duration=duration,
            features=features
        )
        db.add(db_subscription)
        db.commit()
        db.refresh(db_subscription)
        return db_subscription
    finally:
        db.close()
