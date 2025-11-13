import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME")

if not MONGODB_URI:
    raise ValueError("MONGODB_URI environment variable is not set")

if not MONGODB_DB_NAME:
    raise ValueError("MONGODB_DB_NAME environment variable is not set")

client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB_NAME]


def get_database():
    return db


try:
    client.admin.command('ping')
    print("✅ MongoDB connection successful.")
except Exception as e:
    print(f"❌ MongoDB connection failed: {e}")