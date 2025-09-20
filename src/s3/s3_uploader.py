import os
import asyncio
import time
from urllib.parse import urlparse
import boto3
from botocore.exceptions import ClientError
import httpx
import structlog

logger = structlog.get_logger(__name__)

class S3Uploader:
    """Handles downloading PDFs and uploading them to S3."""

    def __init__(self):
        """Initialize S3 client with credentials from environment."""
        self.aws_access_key_id     = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.aws_region            = os.getenv("AWS_REGION", "us-east-1")

        if not self.aws_access_key_id or not self.aws_secret_access_key:
            raise ValueError("AWS credentials are required (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)")

        self.s3_client = boto3.client(
            's3',
            aws_access_key_id     = self.aws_access_key_id,
            aws_secret_access_key = self.aws_secret_access_key,
            region_name           = self.aws_region
        )

        logger.info("S3Uploader initialized successfully")

    async def download_and_upload_pdf(self, pdf_url: str, s3_bucket: str, s3_prefix: str) -> str:
        """
        Download a PDF from URL and upload it to S3.

        Args:
            pdf_url: URL of the PDF to download
            s3_bucket: S3 bucket name
            s3_prefix: S3 prefix/folder path

        Returns:
            S3 URI of the uploaded file
        """
        try:
            logger.info("Starting PDF download and upload", pdf_url=pdf_url)

            # Generate a filename from the URL
            filename = self._generate_filename_from_url(pdf_url)
            s3_key   = f"{s3_prefix.rstrip('/')}/{filename}"

            # Handle local files vs remote URLs
            if pdf_url.startswith('file://'):
                pdf_content = await self._read_local_file(pdf_url)
            else:
                pdf_content = await self._download_pdf(pdf_url)

            # Upload to S3
            await self._upload_to_s3(pdf_content, s3_bucket, s3_key)

            s3_uri = f"s3://{s3_bucket}/{s3_key}"
            logger.info("Successfully uploaded PDF to S3", s3_uri=s3_uri)

            return s3_uri

        except Exception as e:
            logger.error("Failed to download and upload PDF", pdf_url=pdf_url, error=str(e))
            raise

    async def _download_pdf(self, pdf_url: str) -> bytes:
        """Download PDF content from URL."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(pdf_url, follow_redirects=True)
                response.raise_for_status()

                # Verify content type
                content_type = response.headers.get('content-type', '').lower()
                if 'pdf' not in content_type and not pdf_url.lower().endswith('.pdf'):
                    logger.warning("Content may not be PDF", content_type=content_type, url=pdf_url)

                # Additional validation: check if content starts with PDF magic bytes
                if len(response.content) >= 4:
                    pdf_header = response.content[:4]
                    if pdf_header != b'%PDF':
                        logger.error("Downloaded content is not a valid PDF file",
                                   content_type=content_type,
                                   url=pdf_url,
                                   first_bytes=pdf_header.hex() if pdf_header else "empty")
                        raise ValueError(f"Downloaded content is not a PDF file: {content_type}")

                logger.info("Downloaded PDF successfully", size_bytes=len(response.content))
                return response.content

        except httpx.HTTPError as e:
            logger.error("HTTP error downloading PDF", error=str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error downloading PDF", error=str(e))
            raise

    async def _read_local_file(self, file_url: str) -> bytes:
        """Read PDF content from local file."""
        try:
            # Convert file:// URL to local path
            file_path = file_url.replace('file://', '')

            with open(file_path, 'rb') as f:
                content = f.read()

            # Validate PDF content
            if len(content) >= 4:
                pdf_header = content[:4]
                if pdf_header != b'%PDF':
                    logger.error("Local file is not a valid PDF",
                               file_path=file_path,
                               first_bytes=pdf_header.hex())
                    raise ValueError(f"File is not a PDF: {file_path}")

            logger.info("Read local PDF file successfully",
                       file_path=file_path,
                       size_bytes=len(content))
            return content

        except Exception as e:
            logger.error("Error reading local PDF file", file_url=file_url, error=str(e))
            raise

    async def _upload_to_s3(self, content: bytes, bucket: str, key: str) -> None:
        """Upload content to S3."""
        try:
            # Run the S3 upload in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.s3_client.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=content,
                    ContentType='application/pdf'
                )
            )

            logger.info("Uploaded to S3 successfully", bucket=bucket, key=key, size_bytes=len(content))

        except ClientError as e:
            logger.error("S3 upload failed", error=str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error uploading to S3", error=str(e))
            raise

    def _generate_filename_from_url(self, url: str) -> str:
        """Generate a suitable filename from the PDF URL."""
        try:
            parsed_url = urlparse(url)
            path = parsed_url.path

            # Extract filename from path
            if path:
                filename = path.split('/')[-1]
                if filename and '.' in filename:
                    return filename

            # If no good filename found, generate one
            # Use the last part of the path or a generic name
            if path:
                path_parts = [p for p in path.split('/') if p]
                if path_parts:
                    base_name = path_parts[-1].replace('.', '_')
                    return f"{base_name}.pdf"

            # Last resort: use domain and timestamp
            domain = parsed_url.netloc.replace('.', '_')
            timestamp = str(int(time.time()))
            return f"{domain}_{timestamp}.pdf"

        except Exception as e:
            logger.warning("Failed to generate filename from URL, using generic name", error=str(e))
            timestamp = str(int(time.time()))
            return f"document_{timestamp}.pdf"