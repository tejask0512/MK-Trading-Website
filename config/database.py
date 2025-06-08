import os
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

DB_NAME = os.getenv("DB_NAME", "mktrading")
DB_USER = os.getenv("DB_USER", "user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")

# Use 'db' only if running inside Docker
IS_DOCKER = os.getenv("DOCKER", "false").lower() == "true"
DB_HOST = "db" if IS_DOCKER else "localhost"

DB_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:5432/{DB_NAME}"
