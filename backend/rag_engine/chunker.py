import uuid
from langchain_text_splitters import RecursiveCharacterTextSplitter

class ParentDocumentChunker:
    def __init__(self):
        # 1. Parent Splitter: Large chunks for LLM context (approx 1500 chars)
        self.parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,
            chunk_overlap=0, # No overlap needed for parents if split by paragraphs cleanly
            separators=["\n\n", "\n"]
        )
        
        # 2. Child Splitter: Small chunks for accurate Vector Search (approx 400 chars)
        # 400 chars is roughly 100 tokens, perfect for bge-large semantic matching
        self.child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=400,
            chunk_overlap=50,
            separators=["\n\n", "\n", ".", " "]
        )

    def process_document(self, raw_text: str, source_doc_id: str, case_name: str) -> dict:
        """
        Takes raw text and splits it into Parent and Child document dictionaries
        ready for MongoDB insertion.
        """
        if not raw_text or not raw_text.strip():
            return {"parents": [], "children": []}

        parents_data = []
        children_data = []

        # Step 1: Create Parent Chunks
        parent_chunks = self.parent_splitter.split_text(raw_text)

        for i, parent_text in enumerate(parent_chunks):
            # Generate a unique ID for this specific parent paragraph
            parent_id = str(uuid.uuid4())
            
            # Create the exact citation format you want the LLM to output
            citation_tag = f"[{case_name} - Paragraph {i+1}]"

            # Build Parent Record
            parents_data.append({
                "parent_id": parent_id,
                "source_doc_id": source_doc_id,
                "text": parent_text,
                "citation": citation_tag
            })

            # Step 2: Create Child Chunks strictly from this Parent
            child_chunks = self.child_splitter.split_text(parent_text)
            
            for child_text in child_chunks:
                child_id = str(uuid.uuid4())
                
                # Build Child Record (This is what gets embedded!)
                children_data.append({
                    "child_id": child_id,
                    "parent_id": parent_id, # The crucial link for PDR
                    "source_doc_id": source_doc_id,
                    "text": child_text
                })

        return {"parents": parents_data, "children": children_data}

# --- Local Test ---
if __name__ == "__main__":
    sample_text = "The court hereby orders the Ministry of Finance to audit the records. \n\n This must be completed within 90 days. Failure to comply will result in a penalty. \n\n Furthermore, the respondent is directed to submit all tax filings from the year 2024."
    
    chunker = ParentDocumentChunker()
    # Using your name as a dummy doc ID for testing
    data = chunker.process_document(sample_text, source_doc_id="doc_straws", case_name="State vs. XYZ")
    
    print(f"Generated {len(data['parents'])} Parents and {len(data['children'])} Children.")
    print("First Child Document:", data['children'][0])