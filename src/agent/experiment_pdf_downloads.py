import asyncio
from pathlib import Path
from dotenv import load_dotenv
from browser_use import Agent, ChatGoogle, Browser
import structlog

logger = structlog.get_logger(__name__)

async def download_pdfs_from_caleprocure():
    """Download all PDFs from the California procurement page."""
    load_dotenv()

    # Create data directory if it doesn't exist
    data_dir = Path("./data")
    data_dir.mkdir(exist_ok=True)

    # Try using a specific Chrome executable and more aggressive PDF viewer disabling
    chrome_args = [
        "--disable-plugins",
        "--disable-extensions",
        "--disable-pdf-extension",
        "--disable-print-preview",
        "--disable-web-security",
        "--allow-running-insecure-content",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        f"--user-data-dir={data_dir.absolute()}/chrome-profile",
        "--no-first-run",
        "--disable-default-apps",
        "--disable-popup-blocking",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-backgrounding-occluded-windows"
    ]

    browser = Browser(
        headless=True,
        downloads_path=str(data_dir.absolute()),
        accept_downloads=True,
        auto_download_pdfs=True,
        args=chrome_args,
        disable_security=True,
        keep_alive=False,  # Change to False to allow proper cleanup
        wait_between_actions=1.0,
        executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"  # Explicit Chrome path on macOS
    )

    # Initialize LLM
    llm = ChatGoogle(model='gemini-2.5-flash')

    # Create agent to click download buttons with Chrome PDF viewer disabled
    agent = Agent(
        task="""
        Go to https://caleprocure.ca.gov/event/0850/0000036230

        Wait 5 seconds for the page to fully load.
        Press on the "View Event Package" button.
        Wait 5 seconds for the page to fully load.

        Find all PDF download buttons/links on the page.
        Click each download button for PDF files.

        After each download click:
        - Wait 5 seconds for the download to complete
        - Close any download modals that appear
        - Wait 2 seconds before next download

        With Chrome PDF viewer disabled, files should download directly.
        """,
        llm=llm,
        browser=browser,
        max_failures=5
    )

    try:
        logger.info("Starting PDF download task with proper waits")
        result = await agent.run()
        logger.info("PDF download task completed", result=result.final_result())

        # Wait additional time for any pending downloads to complete
        logger.info("Waiting 10 seconds for any pending downloads to complete...")
        await asyncio.sleep(10)

        # List downloaded files
        downloaded_files = list(data_dir.glob("*.pdf"))
        logger.info(f"Downloaded {len(downloaded_files)} PDF files", files=[f.name for f in downloaded_files])

        # Also check if any files are in a temporary state (e.g., .crdownload)
        temp_files = list(data_dir.glob("*.crdownload"))
        if temp_files:
            logger.warning(f"Found {len(temp_files)} files still downloading: {[f.name for f in temp_files]}")
            logger.info("Waiting additional 10 seconds for incomplete downloads...")
            await asyncio.sleep(10)
            downloaded_files = list(data_dir.glob("*.pdf"))
            logger.info(f"Final count: {len(downloaded_files)} PDF files")

        return downloaded_files

    except Exception as e:
        logger.error("Error during PDF extraction/download", error=str(e))
        raise
    finally:
        try:
            # More aggressive browser cleanup
            if hasattr(browser, 'session') and browser.session:
                await browser.session.close()
            elif hasattr(browser, 'close'):
                await browser.close()
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")

        # Force exit after cleanup
        import sys
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(download_pdfs_from_caleprocure())
#
# """PDF Download Agent that intelligently finds and downloads all PDF attachments from a page."""
#
# import asyncio
# import logging
# from pathlib import Path
# from typing import List, Optional
#
# from browser_use import Agent, BrowserProfile, ChatGoogle
# from browser_use.browser.events import FileDownloadedEvent
#
# logger = logging.getLogger(__name__)
#
#
# class PDFDownloadAgent:
#     """Agent that navigates pages and downloads all PDF attachments found."""
#
#     def __init__(self, gemini_api_key: str, downloads_path: str = "./downloads"):
#         """Initialize the PDF download agent.
#
#         Args:
#             gemini_api_key: Google Gemini API key for LLM operations
#             downloads_path: Directory to save downloaded PDFs
#         """
#         self.downloads_path = Path(downloads_path)
#         self.downloads_path.mkdir(parents=True, exist_ok=True)
#
#         # Initialize the browser agent with Gemini LLM
#         self.llm = ChatGoogle(model="gemini-2.5-flash", api_key=gemini_api_key)
#         self.downloaded_files: List[str] = []
#
#     async def download_pdfs(self, url: str) -> List[str]:
#         """Download all PDF attachments from the given URL.
#
#         Args:
#             url: The webpage URL to search for PDFs
#
#         Returns:
#             List of paths to downloaded PDF files
#         """
#         logger.info(f"Starting PDF download from: {url}")
#
#         # Create task prompt for the agent
#         task_prompt = f"""
#         Navigate to {url} and intelligently find and download all PDF attachments for this page.
#
#         Instructions:
#         1. First navigate to the provided URL
#         2. Look for any links, buttons, or sections that contain PDF documents
#         3. If you see a "View Event Package" or similar section, click on it to reveal PDFs
#         4. Find all PDF links on the page (look for .pdf extensions, download icons, or "PDF" text)
#         5. Click on each PDF link to download the files
#         6. Continue until all PDF attachments have been downloaded
#
#         Focus on:
#         - Document packages or attachments sections
#         - Solicitation documents
#         - Proposal packages
#         - Amendment files
#         - Any other PDF documents related to the procurement
#
#         Return when all PDFs have been successfully downloaded.
#         """
#
#         # Set up file download tracking
#         self.downloaded_files = []
#
#         def on_file_downloaded(event: FileDownloadedEvent):
#             """Track downloaded files."""
#             if event.file_type == 'pdf' or event.path.lower().endswith('.pdf'):
#                 self.downloaded_files.append(event.path)
#                 logger.info(f"PDF downloaded: {event.file_name} -> {event.path}")
#
#         # Create browser profile with download settings
#         browser_profile = BrowserProfile(
#             auto_download_pdfs=True,  # Enable automatic PDF downloads
#             downloads_path=str(self.downloads_path),
#             headless=True,  # Run in headless mode for production
#             accept_downloads=True,  # Allow downloads
#         )
#
#         # Create and configure the agent
#         agent = Agent(
#             task=task_prompt,
#             llm=self.llm,
#             browser_profile=browser_profile
#         )
#
#         # Subscribe to download events
#         agent.browser_session.event_bus.on(FileDownloadedEvent, on_file_downloaded)
#
#         try:
#             # Run the agent
#             result = await agent.run()
#             logger.info(f"Agent completed. Result: {result}")
#
#             # Wait a moment for any final downloads to complete
#             await asyncio.sleep(2)
#
#             if self.downloaded_files:
#                 logger.info(f"Successfully downloaded {len(self.downloaded_files)} PDF files:")
#                 for file_path in self.downloaded_files:
#                     logger.info(f"  - {file_path}")
#             else:
#                 logger.warning("No PDF files were downloaded")
#
#             return self.downloaded_files
#
#         except Exception as e:
#             logger.error(f"Error during PDF download: {e}")
#             raise
#         finally:
#             # Clean up
#             try:
#                 await agent.close()
#             except Exception as e:
#                 logger.warning(f"Error closing agent: {e}")
#
#     def run_sync(self, url: str) -> List[str]:
#         """Synchronous wrapper for download_pdfs.
#
#         Args:
#             url: The webpage URL to search for PDFs
#
#         Returns:
#             List of paths to downloaded PDF files
#         """
#         return asyncio.run(self.download_pdfs(url))
#
#
# async def main():
#     """Example usage of the PDF download agent."""
#     import os
#     from dotenv import load_dotenv
#
#     load_dotenv()
#
#     gemini_api_key = os.getenv("GEMINI_API_KEY")
#     if not gemini_api_key:
#         raise ValueError("GEMINI_API_KEY environment variable is required")
#
#     # Initialize the agent
#     agent = PDFDownloadAgent(
#         gemini_api_key=gemini_api_key,
#         downloads_path="./downloads"
#     )
#
#     # Test URLs from the project
#     test_urls = [
#         "https://caleprocure.ca.gov/event/0850/0000036230",
#         "https://caleprocure.ca.gov/event/2660/07A6065",
#     ]
#
#     for url in test_urls:
#         try:
#             print(f"\n--- Testing URL: {url} ---")
#             downloaded_files = await agent.download_pdfs(url)
#             print(f"Downloaded {len(downloaded_files)} PDF files:")
#             for file_path in downloaded_files:
#                 print(f"  - {file_path}")
#         except Exception as e:
#             print(f"Error processing {url}: {e}")
#
#
# if __name__ == "__main__":
#     asyncio.run(main())