import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-production-use-a-long-random-string")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///bfc.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False