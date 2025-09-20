import os
import traceback
from fastapi import FastAPI
from dotenv import load_dotenv
import structlog
import uvicorn

from src.api.models import ExtractRequest, ExtractResponse
from src.agent.document_extractor import DocumentExtractor

load_dotenv()

logger = structlog.get_logger(__name__)

app = FastAPI(
    title="Agentic Document Extraction API",
    description="Autonomous PDF extraction from government procurement websites",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
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

@app.post("/extract", response_model=ExtractResponse)
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

        return ExtractResponse(status = "success",
                               files  = extracted_files,
                               message= f">>> successfully extracted {len(extracted_files)} documents",
                               )

    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(">>> Unexpected error during extraction", error=str(e), traceback=error_traceback)
        return ExtractResponse(status = "failed",
                               files  = None,
                               message= f"Error: {str(e)}\n\nFull traceback:\n{error_traceback}",
                               )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
