import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Railway proporciona DATABASE_URL
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# Si no hay DATABASE_URL (entorno local), podríamos usar uno por defecto pero el usuario pidió Postgres
if SQLALCHEMY_DATABASE_URL and SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

if not SQLALCHEMY_DATABASE_URL:
    # Por defecto para desarrollo local podriamos usar algo como:
    # SQLALCHEMY_DATABASE_URL = "postgresql://user:password@localhost/dbname"
    # Pero vamos a dejar que falle o que el usuario lo configure en .env
    SQLALCHEMY_DATABASE_URL = "sqlite:///./temp.db" # Fallback temporal para evitar errores inmediatos si no hay .env

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
