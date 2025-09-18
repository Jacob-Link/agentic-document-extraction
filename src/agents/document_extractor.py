import os
import asyncio
import re
from typing import List, Dict, Any
from urllib.parse import urlparse
import structlog

from browser_use import Agent, ChatGoogle
from ..utils.s3_uploader import S3Uploader
from ..extractors.pdf_detector import PDFDetector

logger = structlog.get_logger(__name__)

class DocumentExtractor:
    """Main document extraction orchestrator using browser-use agent."""

    def __init__(self):
        """Initialize the document extractor with browser agent and supporting services."""
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")

        # Initialize ChatGoogle LLM
        self.llm = ChatGoogle(model="gemini-2.5-flash")

        # Initialize supporting services
        self.s3_uploader = S3Uploader()
        self.pdf_detector = PDFDetector()

        # Load NYSCR credentials for authenticated sites
        self.nyscr_username = os.getenv("NYSCR_USERNAME")
        self.nyscr_password = os.getenv("NYSCR_PASSWORD")
        self.has_nyscr_credentials = bool(self.nyscr_username and self.nyscr_password)

        logger.info("DocumentExtractor initialized successfully",
                   has_nyscr_credentials=self.has_nyscr_credentials)

    async def extract_documents(self, url: str, s3_bucket: str, s3_prefix: str) -> List[str]:
        """
        Extract PDF documents from a procurement website and upload to S3.

        Args:
            url: URL of the procurement page
            s3_bucket: S3 bucket name
            s3_prefix: S3 prefix/folder path

        Returns:
            List of S3 URIs for uploaded files
        """
        logger.info("Starting document extraction", url=url, s3_bucket=s3_bucket, s3_prefix=s3_prefix)

        try:
            # Determine platform type and create specialized task
            platform_type = self._detect_platform_type(url)
            task = self._create_extraction_task(url, platform_type)

            logger.info("Creating browser agent", platform_type=platform_type)

            # Prepare sensitive data for authentication if needed
            sensitive_data = {}
            if platform_type == "ny_state" and self.has_nyscr_credentials:
                sensitive_data = {
                    'nyscr_user': self.nyscr_username,
                    'nyscr_pass': self.nyscr_password
                }
                logger.info("Including NYSCR credentials for NY State authentication")

            # Create browser agent with specialized task
            agent_kwargs = {
                "task": task,
                "llm": self.llm,
                "use_vision": True,
                "max_failures": 3
            }

            # Add sensitive data if we have credentials
            if sensitive_data:
                agent_kwargs["sensitive_data"] = sensitive_data
                # Disable vision for security when handling credentials
                agent_kwargs["use_vision"] = False
                logger.info("Using secure mode (no vision) for credential handling")

            agent = Agent(**agent_kwargs)

            # Execute the agent task
            logger.info("Executing browser agent task")
            result = await agent.run()

            # Extract PDF URLs from agent result
            raw_pdf_urls = self._extract_pdf_urls_from_result(result)

            # Validate and filter PDF URLs using PDFDetector
            validated_pdf_urls = self.pdf_detector.validate_pdf_urls(raw_pdf_urls)
            pdf_urls = self.pdf_detector.deduplicate_urls(validated_pdf_urls)

            if not pdf_urls:
                logger.warning("No valid PDF URLs found by agent", raw_count=len(raw_pdf_urls))
                return []

            logger.info("Found valid PDF URLs", raw_count=len(raw_pdf_urls), validated_count=len(pdf_urls))

            # Download and upload PDFs to S3
            uploaded_files = []
            for pdf_url in pdf_urls:
                try:
                    s3_uri = await self.s3_uploader.download_and_upload_pdf(
                        pdf_url=pdf_url,
                        s3_bucket=s3_bucket,
                        s3_prefix=s3_prefix
                    )
                    uploaded_files.append(s3_uri)
                    logger.info("Successfully uploaded PDF", pdf_url=pdf_url, s3_uri=s3_uri)
                except Exception as e:
                    logger.error("Failed to upload PDF", pdf_url=pdf_url, error=str(e))

            logger.info("Document extraction completed", total_files=len(uploaded_files))
            return uploaded_files

        except Exception as e:
            logger.error("Document extraction failed", error=str(e))
            raise

    def _detect_platform_type(self, url: str) -> str:
        """Detect the procurement platform type from URL."""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()

        if "caleprocure.ca.gov" in domain:
            return "california_ecal"
        elif "nyscr.ny.gov" in domain:
            return "ny_state"
        elif "sourcewell-mn.gov" in domain:
            return "sourcewell"
        else:
            return "unknown"

    def _create_extraction_task(self, url: str, platform_type: str) -> str:
        """Create a specialized task prompt based on platform type."""
        base_task = f"""
Navigate to {url} and extract all PDF documents from this procurement page.

Your goal is to:
1. Navigate to the URL and wait for the page to fully load
2. Look for any "View Event Package", "Documents", "Attachments", or similar links
3. Click on document/attachment sections to reveal PDF files
4. Find all PDF links on the page (look for .pdf extensions or PDF icons)
5. Return a list of all PDF download URLs you find

"""

        platform_specific_instructions = {
            "california_ecal": """
This is a California eCal procurement site. Look for:
- "View Event Package" link or button
- Document tabs or sections
- PDF attachments in the solicitation details
- Amendment documents if available
""",
            "ny_state": """
This is a NY State procurement site that requires authentication. You have access to login credentials:
- Username: nyscr_user
- Password: nyscr_pass

Authentication steps:
1. Look for login forms, "Sign In", "Login", or "Member Login" buttons/links
2. Click the login button/link to access the login form
3. Enter nyscr_user in the username/email field
4. Enter nyscr_pass in the password field
5. Submit the login form
6. Wait for successful authentication and page redirect
7. Then navigate to document sections and look for solicitation documents and amendments

If login fails or credentials are rejected, report the authentication error.
""",
            "sourcewell": """
This is a SourceWell procurement site. Look for:
- Document tabs or sections in the tender details
- PDF attachments in the solicitation
- Any downloadable files related to the procurement
"""
        }

        specific_instructions = platform_specific_instructions.get(platform_type, "")

        # Add credential availability note for NY State
        if platform_type == "ny_state" and not self.has_nyscr_credentials:
            specific_instructions += """

NOTE: No NYSCR credentials are available. You can:
- Try to navigate any publicly accessible areas
- Look for guest/public access options
- Report if authentication is required for document access
"""

        return base_task + specific_instructions + """

Return your findings as a simple list of PDF URLs, one per line.
Focus only on legitimate PDF document URLs that contain procurement-related content.
"""

    def _extract_pdf_urls_from_result(self, result: Any) -> List[str]:
        """Extract PDF URLs from the agent's result."""
        try:
            if hasattr(result, 'content'):
                content = result.content
            elif isinstance(result, str):
                content = result
            else:
                content = str(result)

            # Extract URLs that look like PDF links
            pdf_urls = []
            lines = content.split('\n')

            for line in lines:
                line = line.strip()
                if line and ('.pdf' in line.lower() or 'pdf' in line.lower()):
                    # Try to extract URL from the line
                    if line.startswith('http'):
                        pdf_urls.append(line)
                    elif 'http' in line:
                        # Extract URL from text
                        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
                        urls = re.findall(url_pattern, line)
                        pdf_urls.extend(urls)

            logger.info("Extracted PDF URLs from agent result", count=len(pdf_urls))
            return pdf_urls

        except Exception as e:
            logger.error("Failed to extract PDF URLs from result", error=str(e))
            return []