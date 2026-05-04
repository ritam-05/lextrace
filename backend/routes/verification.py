"""
Verification Endpoint: Human-in-the-loop verification of arbitration results.
"""
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from datetime import datetime
from typing import Optional
from backend.database import Database

router = APIRouter()


@router.get("/verify/{doc_id}")
async def get_verification(doc_id: str):
    """
    GET arbitration results for a document.
    Returns both extracted data and arbitration verdicts for human review.
    """
    db = Database.get_db()
    
    try:
        # Fetch extraction document
        extraction = db.extractions.find_one({
            "document_id": doc_id,
            "extraction_type": "arbitration_result"
        })
        
        if not extraction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No arbitration result found for document {doc_id}"
            )
        
        # Convert ObjectId to string for JSON serialization
        extraction["_id"] = str(extraction.get("_id", ""))
        
        return {
            "status": "success",
            "document_id": doc_id,
            "arbitration_results": extraction.get("arbitration_results", {}),
            "arbitration_summary": extraction.get("arbitration_summary", {}),
            "regex_output": extraction.get("regex_output", {}),
            "rag_output": extraction.get("rag_output", {}),
            "verification_status": extraction.get("status", "pending_human_review"),
            "created_at": extraction.get("created_at")
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving verification data: {str(e)}"
        )


@router.post("/verify/{doc_id}/approve")
async def approve_extraction(doc_id: str, approval_data: dict):
    """
    POST human approval/rejection/edits for extracted fields.
    
    approval_data format:
    {
        "field_decisions": {
            "case_number": {"approved": true, "edited_value": null},
            "petitioner": {"approved": false, "edited_value": "Corrected Name"},
            ...
        },
        "reviewed_by": "reviewer_id",
        "notes": "Optional review notes"
    }
    """
    db = Database.get_db()
    
    try:
        # Fetch extraction document
        extraction = db.extractions.find_one({
            "document_id": doc_id,
            "extraction_type": "arbitration_result"
        })
        
        if not extraction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No arbitration result found for document {doc_id}"
            )
        
        # Build verification record
        verification = {
            "document_id": doc_id,
            "extraction_id": extraction.get("_id"),
            "human_review": approval_data.get("field_decisions", {}),
            "reviewed_by": approval_data.get("reviewed_by", "unknown"),
            "review_notes": approval_data.get("notes", ""),
            "reviewed_at": datetime.utcnow().isoformat(),
            "status": "approved"  # Mark as approved
        }
        
        # Insert verification record
        verification_result = db.verifications.insert_one(verification)
        
        # Update extraction document status
        db.extractions.update_one(
            {"_id": extraction.get("_id")},
            {"$set": {"status": "approved", "verified_at": datetime.utcnow().isoformat()}}
        )
        
        # Build final approved output (combining regex + rag + human edits)
        approved_data = _build_approved_output(
            extraction.get("arbitration_results", {}),
            approval_data.get("field_decisions", {})
        )
        
        # Insert into approved_extractions collection for dashboard
        db.approved_extractions.insert_one({
            "document_id": doc_id,
            "extraction_id": extraction.get("_id"),
            "verification_id": verification_result.inserted_id,
            "approved_data": approved_data,
            "approved_at": datetime.utcnow().isoformat(),
            "approved_by": approval_data.get("reviewed_by", "unknown")
        })
        
        return {
            "status": "success",
            "document_id": doc_id,
            "message": "Extraction approved and saved to dashboard",
            "verification_id": str(verification_result.inserted_id),
            "approved_data": approved_data
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing approval: {str(e)}"
        )


@router.post("/verify/{doc_id}/reject")
async def reject_extraction(doc_id: str, rejection_data: dict):
    """
    POST human rejection with reason.
    """
    db = Database.get_db()
    
    try:
        extraction = db.extractions.find_one({
            "document_id": doc_id,
            "extraction_type": "arbitration_result"
        })
        
        if not extraction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No arbitration result found for document {doc_id}"
            )
        
        # Update extraction status
        db.extractions.update_one(
            {"_id": extraction.get("_id")},
            {
                "$set": {
                    "status": "rejected",
                    "rejection_reason": rejection_data.get("reason", ""),
                    "rejected_by": rejection_data.get("reviewed_by", "unknown"),
                    "rejected_at": datetime.utcnow().isoformat()
                }
            }
        )
        
        return {
            "status": "success",
            "document_id": doc_id,
            "message": "Extraction rejected. Please re-upload for reprocessing.",
            "reason": rejection_data.get("reason", "")
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing rejection: {str(e)}"
        )


def _build_approved_output(arbitration_results: dict, field_decisions: dict) -> dict:
    """
    Merge arbitration results with human edits to build final approved output.
    """
    approved_output = {}
    
    for field_name, result in arbitration_results.items():
        decision = field_decisions.get(field_name, {})
        
        # If human edited the value, use that. Otherwise use arbitration final_value
        if decision.get("approved"):
            if decision.get("edited_value"):
                approved_output[field_name] = {
                    "value": decision["edited_value"],
                    "source": "human_edited",
                    "confidence": 0.99
                }
            else:
                approved_output[field_name] = {
                    "value": result.get("final_value", ""),
                    "state": result.get("state", ""),
                    "confidence": result.get("confidence", 0.0),
                    "source": "arbitration_approved"
                }
        elif decision.get("edited_value"):
            # Edited but not explicitly approved
            approved_output[field_name] = {
                "value": decision["edited_value"],
                "source": "human_provided",
                "confidence": 0.95
            }
    
    return approved_output
