import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

class DatabaseManager:
    client: MongoClient = None
    db = None

    @classmethod
    def connect(cls):
        """Initializes the MongoDB connection pool."""
        mongo_uri = os.getenv("MONGODB_URI")
        db_name = os.getenv("DB_NAME", "lextrace_db")
        
        if not mongo_uri:
            raise ValueError("Fatal Error: MONGODB_URI is not set in the .env file.")

        try:
            # Initialize the client. PyMongo automatically handles connection pooling.
            print("Connecting to MongoDB Atlas...")
            cls.client = MongoClient(mongo_uri)
            
            # Send a ping to confirm a successful connection
            cls.client.admin.command('ping')
            print("Successfully connected to MongoDB Atlas!")
            
            cls.db = cls.client[db_name]
        except ConnectionFailure as e:
            print(f"Could not connect to MongoDB: {e}")
            raise

    @classmethod
    def disconnect(cls):
        """Closes the connection pool."""
        if cls.client:
            print("Closing MongoDB connection...")
            cls.client.close()

    @classmethod
    def get_db(cls):
        """Returns the database instance for use in routes and services."""
        if cls.db is None:
            raise Exception("Database not initialized. Call connect() first.")
        return cls.db