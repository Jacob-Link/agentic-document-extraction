import os
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import structlog

from .models import ExtractRequest, ExtractResponse, ErrorResponse
from ..agents.document_extractor import DocumentExtractor

load_dotenv()

logger = structlog.get_logger(__name__)

app = FastAPI(
    title="Agentic Document Extraction API",
    description="Autonomous PDF extraction from government procurement websites",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "Agentic Document Extraction API is running", "status": "healthy"}

@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
        "aws_configured": bool(os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"))
    }

@app.post("/extract", response_model=ExtractResponse, responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def extract_documents(request: ExtractRequest):
    """
    Extract PDF documents from a procurement website and upload to S3.

    This endpoint accepts a URL pointing to a government procurement page,
    autonomously navigates the site, discovers PDF documents, downloads them,
    and uploads them to the specified S3 bucket with proper naming.
    """
    try:
        logger.info("Starting document extraction", url=str(request.url), s3_bucket=request.s3_bucket, s3_prefix=request.s3_prefix)

        # Initialize the document extractor
        extractor = DocumentExtractor()

        # Perform the extraction
        extracted_files = await extractor.extract_documents(
            url=str(request.url),
            s3_bucket=request.s3_bucket,
            s3_prefix=request.s3_prefix
        )

        logger.info("Document extraction completed", file_count=len(extracted_files))

        return ExtractResponse(
            status="success",
            files=extracted_files,
            message=f"Successfully extracted {len(extracted_files)} documents"
        )

    except ValueError as e:
        logger.error("Validation error during extraction", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error("Unexpected error during extraction", error=str(e))
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)