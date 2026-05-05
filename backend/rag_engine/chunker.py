from langchain_text_splitters import RecursiveCharacterTextSplitter
import uuid


class LegalDocumentChunker:
    def __init__(self):
        self.parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,
            chunk_overlap=250,
            length_function=len,
            separators=["\n\n", "\n", ".", " ", ""],
        )

        self.child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=400,
            chunk_overlap=60,
            length_function=len,
            separators=["\n\n", "\n", ".", " ", ""],
        )

    def chunk_document(self, text: str, document_id: str):
        """
        Chunks a legal document into parents and respective children,
        maintaining the sequential hierarchy for downstream reconstruction.
        """
        parent_chunks_raw = self.parent_splitter.split_text(text)

        structured_data = {
            "document_id": document_id,
            "parents": [],
            "children": [],
        }

        for parent_index, parent_text in enumerate(parent_chunks_raw):
            parent_id = f"{document_id}_p{parent_index + 1}"

            structured_data["parents"].append(
                {
                    "parent_id": parent_id,
                    "document_id": document_id,
                    "text": parent_text,
                    "sequence_order": parent_index + 1,
                }
            )

            child_chunks_raw = self.child_splitter.split_text(parent_text)

            for child_index, child_text in enumerate(child_chunks_raw):
                child_id = f"{parent_id}_c{child_index + 1}"

                structured_data["children"].append(
                    {
                        "child_id": child_id,
                        "parent_id": parent_id,
                        "document_id": document_id,
                        "text": child_text,
                        "sequence_order": child_index + 1,
                    }
                )

        return structured_data

    def process_document(self, raw_text: str, document_id: str = None):
        if not document_id:
            document_id = f"doc_{uuid.uuid4().hex[:8]}"

        structured_data = self.chunk_document(raw_text, document_id)
        return structured_data["parents"], structured_data["children"]
