from sentence_transformers import SentenceTransformer
from backend.database import DatabaseManager

class RAGService:
    def __init__(self):
        # 1. Grab the shared database connection
        self.db = DatabaseManager.get_db()
        
        # We need two collections for Parent-Document Retrieval
        self.parents_collection = self.db["parent_documents"]
        self.children_collection = self.db["child_chunks"]

        # 2. Initialize BGE-Large on CUDA
        print("Loading BGE-Large model on CUDA...")
        self.embedding_model = SentenceTransformer("BAAI/bge-large-en-v1.5", device="cuda")
        print("Model loaded successfully.")

    def embed_and_store(self, chunked_data: dict):
        """
        Takes the dictionary output from ParentDocumentChunker, generates embeddings 
        for the children, and pushes everything to MongoDB.
        """
        parents = chunked_data.get("parents", [])
        children = chunked_data.get("children", [])

        if not parents or not children:
            print("No data to process.")
            return

        # 1. Insert Parents into DB (No embeddings needed here)
        if parents:
            self.parents_collection.insert_many(parents)
            print(f"Inserted {len(parents)} parent documents.")

        # 2. Generate Embeddings for Children
        # Extract just the text from the children list
        child_texts = [child["text"] for child in children]
        
        # BGE requires queries to be prefixed, but documents do NOT need a prefix.
        # We batch encode on the GPU for speed.
        print(f"Generating embeddings for {len(child_texts)} child chunks...")
        embeddings = self.embedding_model.encode(child_texts, normalize_embeddings=True)

        # 3. Attach embeddings back to the child dictionaries
        for i, child in enumerate(children):
            # Convert numpy array to list for MongoDB storage
            child["embedding"] = embeddings[i].tolist() 

        # 4. Insert Children into DB
        if children:
            self.children_collection.insert_many(children)
            print(f"Inserted {len(children)} child chunks with embeddings.")

        return True