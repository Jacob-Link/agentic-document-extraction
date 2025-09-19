"""
the document extractor will have 2 states, depending on the .env var "DEBUG",
if DEBUG == True : the agent will run a dummy agent returning the exact time, based on search...
if DEBUG == False: the agent will run the task it is set out to run, extracting the pdf links for future download.
"""

import os
from dotenv import load_dotenv
from datetime import datetime
from typing import List
import structlog
from browser_use import Agent, ChatGoogle

logger = structlog.get_logger(__name__)

class DocumentExtractor:
    """Document extraction service with DEBUG mode support."""

    def __init__(self):
        load_dotenv()
        self.debug_mode = os.getenv("DEBUG", "false").lower() == "true"

    async def extract_documents(self, url: str, s3_bucket: str, s3_prefix: str) -> List[str]:
        """
        Extract documents from a URL and upload to S3.
        In DEBUG mode, returns dummy S3 URIs with timestamp-based names.
        """
        if self.debug_mode:
            return await self._debug_extract(url, s3_bucket, s3_prefix)
        else:
            return await self._real_extract(url, s3_bucket, s3_prefix)

    async def _debug_extract(self, url: str, s3_bucket: str, s3_prefix: str) -> List[str]:
        """DEBUG mode: return dummy S3 URIs with timestamp-based names."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        logger.info("Running in DEBUG mode", url=url, timestamp=timestamp)

        # Test browser-use capability with simple search task
        try:
            llm = ChatGoogle(model='gemini-2.5-flash')
            agent = Agent(
                task="search for a fun fact regarding ai",
                llm=llm,
            )
            result = await agent.run()
            logger.info("Browser-use test completed", fun_fact=result)
        except Exception as e:
            logger.warning("Browser-use test failed", error=str(e))

        # Generate dummy file names based on timestamp
        dummy_files = [
            f"s3://{s3_bucket}/{s3_prefix}solicitation_{timestamp}.pdf",
            f"s3://{s3_bucket}/{s3_prefix}amendments_{timestamp}.pdf"
        ]

        logger.info("DEBUG extraction completed", files=dummy_files)
        return dummy_files

    async def _real_extract(self, url: str, s3_bucket: str, s3_prefix: str) -> List[str]:
        """Production mode: real browser automation and PDF extraction."""
        # TODO: Implement real browser automation with Browser Use + Gemini
        raise NotImplementedError("Real extraction not yet implemented - use DEBUG=true for MVP testing")
