#Database Config

DB_USER=os.get.environ("DB_USER","postgres")
DB_PASSWORD=os.environ.get("DB_PASSWORD","postgres")
DB_HOST=os.environ.get("DB_HOST","db")
DB_PORT=os.environ.get("DB_PORT","5432")
DB_NAME=os.environ.get("DB_NAME","mktrading")

DATABASE_URL=f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"