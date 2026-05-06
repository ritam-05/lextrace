from langchain_text_splitters import RecursiveCharacterTextSplitter
import uuid
from typing import Iterable


def _page_from_overlaps(
    start: int,
    end: int,
    spans: list[dict],
    fallback_page: int | None = None,
) -> int | None:
    best_page = fallback_page
    best_overlap = 0

    for span in spans:
        overlap = max(0, min(end, span["end"]) - max(start, span["start"]))
        if overlap > best_overlap:
            best_overlap = overlap
            best_page = span["page"]

    return best_page


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

    def chunk_document(
        self,
        text: str,
        document_id: str,
        page_spans: list[dict] | None = None,
    ):
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

        search_start = 0

        for parent_index, parent_text in enumerate(parent_chunks_raw):
            parent_id = f"{document_id}_p{parent_index + 1}"
            parent_start = text.find(parent_text, search_start)
            if parent_start == -1:
                parent_start = text.find(parent_text)
            if parent_start == -1:
                parent_start = search_start

            parent_end = parent_start + len(parent_text)
            parent_page = (
                _page_from_overlaps(parent_start, parent_end, page_spans or [])
                if page_spans
                else None
            )

            parent_payload = {
                "parent_id": parent_id,
                "document_id": document_id,
                "text": parent_text,
                "sequence_order": parent_index + 1,
            }
            if parent_page is not None:
                parent_payload["page"] = parent_page

            structured_data["parents"].append(parent_payload)

            child_chunks_raw = self.child_splitter.split_text(parent_text)
            child_search_start = parent_start

            for child_index, child_text in enumerate(child_chunks_raw):
                child_id = f"{parent_id}_c{child_index + 1}"
                child_start = text.find(child_text, child_search_start)
                if child_start == -1:
                    child_start = text.find(child_text, parent_start, parent_end)
                if child_start == -1:
                    child_start = child_search_start

                child_end = child_start + len(child_text)
                child_page = (
                    _page_from_overlaps(
                        child_start,
                        child_end,
                        page_spans or [],
                        fallback_page=parent_page,
                    )
                    if page_spans
                    else None
                )

                child_payload = {
                    "child_id": child_id,
                    "parent_id": parent_id,
                    "document_id": document_id,
                    "text": child_text,
                    "sequence_order": child_index + 1,
                }
                if child_page is not None:
                    child_payload["page"] = child_page

                structured_data["children"].append(child_payload)
                child_search_start = child_end

            search_start = parent_end

        return structured_data

    def process_document(
        self,
        raw_text: str,
        document_id: str = None,
        source_paragraphs: Iterable | None = None,
    ):
        if not document_id:
            document_id = f"doc_{uuid.uuid4().hex[:8]}"

        page_spans = None
        if source_paragraphs is not None:
            text_parts = []
            page_spans = []
            offset = 0

            for paragraph in source_paragraphs:
                paragraph_text = getattr(paragraph, "text", "")
                paragraph_page = getattr(paragraph, "page", None)
                if not paragraph_text:
                    continue

                if text_parts:
                    text_parts.append("\n\n")
                    offset += 2

                start = offset
                text_parts.append(paragraph_text)
                offset += len(paragraph_text)
                if paragraph_page is not None:
                    page_spans.append(
                        {
                            "start": start,
                            "end": offset,
                            "page": paragraph_page,
                        }
                    )

            if text_parts:
                raw_text = "".join(text_parts)

        structured_data = self.chunk_document(raw_text, document_id, page_spans)
        return structured_data["parents"], structured_data["children"]
