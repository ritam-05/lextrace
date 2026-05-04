import re
import uuid
from typing import List, Dict, Tuple

class LegalDocumentChunker:
    def __init__(self, parent_chunk_size: int = 1500, child_chunk_size: int = 400):
        self.parent_chunk_size = parent_chunk_size
        self.child_chunk_size = child_chunk_size
        
        # 1. Boilerplate Vaporizer
        # Targets "Page X of Y", isolated page numbers, and common court headers
        self.header_footer_pattern = re.compile(
            r"(?i)(page\s+\d+\s+of\s+\d+|^\s*\d+\s*$|in the high court of.+|signature not verified)",
            re.MULTILINE
        )
        
        # 2. Abbreviation-Safe Sentence Splitter (The Secret Weapon)
        # Uses Negative Lookbehinds. It splits on a period + space ONLY IF 
        # it is NOT preceded by legal abbreviations like v, vs, u/s, No, Hon'ble, etc.
        self.sentence_end_pattern = re.compile(
            r"(?<!\bv)(?<!\bvs)(?<!\bu/s)(?<!\bNo)(?<!Hon'ble)(?<!\bMr)(?<!\bO)(?<!\bR)\.\s+"
        )

    def sanitize(self, raw_text: str) -> str:
        """Strips repeating headers/footers before chunking even begins."""
        # Remove headers and footers
        clean = self.header_footer_pattern.sub("", raw_text)
        
        # Fix broken lines (single newlines in the middle of sentences caused by PyMuPDF)
        clean = re.sub(r"(?<!\n)\n(?!\n)", " ", clean)
        
        # Collapse multiple whitespace/newlines into clean paragraph breaks
        clean = re.sub(r"\n{3,}", "\n\n", clean)
        clean = re.sub(r" {2,}", " ", clean)
        
        return clean.strip()

    def split_into_chunks(self, text: str, max_chars: int) -> List[str]:
        """Custom semantic splitter that respects legal abbreviations and paragraph boundaries."""
        chunks = []
        current_chunk = ""
        
        # Split by actual paragraphs first (safest semantic boundary in legal text)
        paragraphs = text.split("\n\n")
        
        for para in paragraphs:
            # If a single paragraph is massive, we must split it by sentences safely
            if len(para) > max_chars:
                sentences = self.sentence_end_pattern.split(para)
                for sentence in sentences:
                    # Re-attach the period that was consumed by the regex split
                    sentence = sentence.strip() + ". " 
                    
                    if len(current_chunk) + len(sentence) <= max_chars:
                        current_chunk += sentence
                    else:
                        if current_chunk: 
                            chunks.append(current_chunk.strip())
                        current_chunk = sentence
            else:
                # If paragraph fits, add it to the current chunk
                if len(current_chunk) + len(para) + 2 <= max_chars:
                    current_chunk += para + "\n\n"
                else:
                    if current_chunk: 
                        chunks.append(current_chunk.strip())
                    current_chunk = para + "\n\n"
                    
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        return chunks

    def process_document(self, raw_text: str, document_id: str = None) -> Tuple[List[Dict], List[Dict]]:
        """
        Executes the single-pass extraction, yielding clean parents and children 
        directly into system RAM.
        """
        if not document_id:
            document_id = f"doc_{uuid.uuid4().hex[:8]}"

        parent_documents = []
        child_chunks = []

        # Phase 1: Aggressive Sanitization
        clean_text = self.sanitize(raw_text)

        # Phase 2: Semantic Parent Generation (No forced arbitrary overlap)
        parent_texts = self.split_into_chunks(clean_text, self.parent_chunk_size)

        for i, parent_text in enumerate(parent_texts):
            parent_id = f"{document_id}_p{i}"
            parent_documents.append({
                "parent_id": parent_id,
                "document_id": document_id,
                "text": parent_text,
                "status": "active"
            })

            # Phase 3: Semantic Child Generation strictly within parent bounds
            child_texts = self.split_into_chunks(parent_text, self.child_chunk_size)
            
            for j, child_text in enumerate(child_texts):
                child_chunks.append({
                    "child_id": f"{parent_id}_c{j}",
                    "parent_id": parent_id,
                    "document_id": document_id,
                    "text": child_text
                })

        print(f"🔪 Legal Chunking Complete: Generated {len(parent_documents)} Parents and {len(child_chunks)} Children.")
        return parent_documents, child_chunks