import os
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

class Database:
    client: MongoClient = None
    db = None

    @classmethod
    def connect(cls):
        if cls.client is None:
            if not MONGO_URI:
                raise ValueError("❌ MONGO_URI is not set in the .env file.")
            
            # ServerApi('1') is highly recommended for MongoDB Atlas stability
            cls.client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
            
            try:
                # Force a call to the server to verify the connection
                cls.client.admin.command('ping')
                print("✅ Successfully connected to MongoDB Atlas Free Tier!")
            except Exception as e:
                print(f"❌ Failed to connect to MongoDB: {e}")
                raise e
            
            # Using 'lextrace_db' as the default database name
            cls.db = cls.client["lextrace_db"]

    @classmethod
    def get_db(cls):
        if cls.db is None:
            cls.connect()
        return cls.db

    @classmethod
    def close(cls):
        if cls.client:
            cls.client.close()
            print("🔌 MongoDB Atlas connection safely closed.")