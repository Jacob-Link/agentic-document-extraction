#!/usr/bin/env python3
"""
Simple test script for single PDF download from caleprocure.ca.gov and upload to S3.

This script tests the focused extraction workflow:
1. Navigate to a California eCal procurement page
2. Download exactly ONE PDF document to local disk
3. Upload the PDF to S3
4. Clean up local files

Usage:
    python test_simple.py

Environment variables required:
    GEMINI_API_KEY - Google Gemini API key for browser-use
    AWS_ACCESS_KEY_ID - AWS access key
    AWS_SECRET_ACCESS_KEY - AWS secret key
    S3_BUCKET_NAME - S3 bucket for uploads (optional, defaults to 'my-solicitations')
"""

import os
import asyncio
import structlog
from dotenv import load_dotenv

from src.agents.document_extractor import DocumentExtractor

# Load environment variables
load_dotenv()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Test configuration
TEST_URL = "https://caleprocure.ca.gov/event/0850/0000036230"
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "my-solicitations")
S3_PREFIX = "test/single-pdf-extraction/"

async def test_single_pdf_extraction():
    """Test single PDF extraction from caleprocure.ca.gov"""

    logger.info("Starting single PDF extraction test",
                url=TEST_URL,
                bucket=S3_BUCKET,
                prefix=S3_PREFIX)

    try:
        # Verify required environment variables
        required_vars = ["GEMINI_API_KEY", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            logger.error("Missing required environment variables", missing=missing_vars)
            return False

        logger.info("Environment variables verified")

        # Initialize the document extractor
        extractor = DocumentExtractor()
        logger.info("DocumentExtractor initialized successfully")

        # Perform single PDF extraction
        logger.info("Starting extraction process...")
        extracted_files = await extractor.extract_documents(
            url=TEST_URL,
            s3_bucket=S3_BUCKET,
            s3_prefix=S3_PREFIX
        )

        # Verify results
        if extracted_files:
            logger.info("✅ Test PASSED - Single PDF extraction successful!",
                       file_count=len(extracted_files),
                       files=extracted_files)

            for file_uri in extracted_files:
                logger.info("📄 Extracted file", s3_uri=file_uri)

            return True
        else:
            logger.error("❌ Test FAILED - No files were extracted")
            return False

    except Exception as e:
        logger.error("❌ Test FAILED - Exception occurred", error=str(e), error_type=type(e).__name__)
        return False

def check_requirements():
    """Check if all requirements are met"""
    logger.info("Checking requirements...")

    # Check environment variables
    required_vars = {
        "GEMINI_API_KEY": "Google Gemini API key for browser automation",
        "AWS_ACCESS_KEY_ID": "AWS access key for S3 uploads",
        "AWS_SECRET_ACCESS_KEY": "AWS secret key for S3 uploads"
    }

    missing = []
    for var, desc in required_vars.items():
        if not os.getenv(var):
            missing.append(f"{var} - {desc}")

    if missing:
        logger.error("❌ Missing required environment variables:")
        for item in missing:
            logger.error(f"   • {item}")
        logger.info("💡 Create a .env file with these variables or export them in your shell")
        return False

    logger.info("✅ All required environment variables are set")

    # Display test configuration
    logger.info("📋 Test Configuration:")
    logger.info(f"   • Target URL: {TEST_URL}")
    logger.info(f"   • S3 Bucket: {S3_BUCKET}")
    logger.info(f"   • S3 Prefix: {S3_PREFIX}")

    return True

async def main():
    """Main test function"""
    logger.info("🚀 Single PDF Extraction Test Starting")
    logger.info("=" * 60)

    # Check requirements first
    if not check_requirements():
        logger.error("❌ Requirements check failed")
        return

    logger.info("=" * 60)

    # Run the test
    success = await test_single_pdf_extraction()

    logger.info("=" * 60)
    if success:
        logger.info("🎉 TEST COMPLETED SUCCESSFULLY!")
        logger.info("✅ Single PDF download and S3 upload working correctly")
    else:
        logger.error("💥 TEST FAILED!")
        logger.error("❌ Check the logs above for error details")

    logger.info("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())