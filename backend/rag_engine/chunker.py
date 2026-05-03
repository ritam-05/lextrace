import uuid
from typing import List, Dict, Tuple
from langchain_text_splitters import RecursiveCharacterTextSplitter

class ParentDocumentChunker:
    def __init__(
        self, 
        parent_chunk_size: int = 1500, 
        parent_overlap: int = 150,
        child_chunk_size: int = 400, 
        child_overlap: int = 50
    ):
        """
        Initializes the chunkers for Parent Document Retrieval.
        Legal text requires overlap so sentences aren't brutally cut in half.
        """
        # The parent splitter creates the large context windows for the LLM
        self.parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=parent_chunk_size,
            chunk_overlap=parent_overlap,
            separators=["\n\n", "\n", ".", " ", ""]
        )
        
        # The child splitter creates the small target windows for vector search
        self.child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=child_chunk_size,
            chunk_overlap=child_overlap,
            separators=["\n\n", "\n", ".", " ", ""]
        )

    def process_document(self, raw_text: str, document_id: str = None) -> Tuple[List[Dict], List[Dict]]:
        """
        Takes a sanitized PDF text string and yields parent and linked child dictionaries.
        Keeps everything strictly in system RAM (Single-Pass Extraction constraint).
        """
        if not document_id:
            # Fallback ID if not provided by Track A
            document_id = f"doc_{uuid.uuid4().hex[:8]}"

        parent_documents = []
        child_chunks = []

        # 1. First Pass: Split raw text into large parent chunks
        parent_texts = self.parent_splitter.split_text(raw_text)

        for i, parent_text in enumerate(parent_texts):
            # Generate a deterministic ID for tracing (e.g., doc_123_p0)
            parent_id = f"{document_id}_p{i}"
            
            parent_documents.append({
                "parent_id": parent_id,
                "document_id": document_id,
                "text": parent_text,
                "status": "active" # For future HITL flagging
            })

            # 2. Second Pass: Split THIS specific parent chunk into smaller children
            child_texts = self.child_splitter.split_text(parent_text)
            
            for j, child_text in enumerate(child_texts):
                child_id = f"{parent_id}_c{j}"
                
                child_chunks.append({
                    "child_id": child_id,
                    "parent_id": parent_id, # The crucial linkage
                    "document_id": document_id,
                    "text": child_text
                    # We leave "embedding" empty here. Phase 3 handles that.
                })

        print(f"🔪 Chunking Complete: Generated {len(parent_documents)} Parents and {len(child_chunks)} Children.")
        
        # We return both arrays cleanly to system memory
        return parent_documents, child_chunks

# Quick test block to ensure it works isolated from the DB
if __name__ == "__main__":
    dummy_text = "This is a mock judgment. " * 200 # Roughly a page of text
    chunker = ParentDocumentChunker()
    parents, children = chunker.process_document(dummy_text, "test_judgment")
    print(f"Sample Child Map -> {children[0]['child_id']} links to {children[0]['parent_id']}")