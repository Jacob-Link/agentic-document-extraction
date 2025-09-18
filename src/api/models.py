from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional

class ExtractRequest(BaseModel):
    """Request model for PDF extraction endpoint."""
    url      : HttpUrl = Field(..., description="URL of the procurement page to extract PDFs from")
    s3_bucket: str     = Field(..., description="S3 bucket name to upload files to"       , min_length=1)
    s3_prefix: str     = Field(..., description="S3 prefix/folder path for uploaded files", min_length=1)

class ExtractResponse(BaseModel):
    """Response model for PDF extraction endpoint."""
    status : str           = Field(...       , description="Status of the extraction operation")
    files  : List[str]     = Field(default=[], description="List of S3 URIs for uploaded files")
    message: Optional[str] = Field(None      , description="Additional message or error details")

class ErrorResponse(BaseModel):
    """Error response model."""
    error  : str           = Field(..., description="Error message")
    details: Optional[str] = Field(None, description="Additional error details")