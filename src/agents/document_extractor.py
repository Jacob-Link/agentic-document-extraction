import os
from typing import List
from pathlib import Path
from dotenv import load_dotenv
import structlog

from browser_use import Agent, Browser, ChatGoogle

logger = structlog.get_logger(__name__)


class DocumentExtractor:
    """
    Simplified document extractor focused on robust local PDF downloading.
    """

    def __init__(self):
        load_dotenv()

        # Configuration
        self.HOST = "caleprocure.ca.gov"
        self.download_dir = os.path.abspath(os.getenv("DISK_DOWNLOAD_DIR", "./data"))

        # LLM setup
        self.gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY environment variable is required")

        self.llm = ChatGoogle(model="gemini-2.5-flash")

        # Ensure downloads dir exists
        Path(self.download_dir).mkdir(parents=True, exist_ok=True)

        logger.info("DocumentExtractor initialized for local PDF downloading",
                    download_dir=self.download_dir)

    def extract_documents_local(self, url: str) -> List[str]:
        """
        Extract PDF documents from government procurement sites and save locally.
        Simplified approach focused on robust downloading.
        """
        self._validate_url(url)
        logger.info("Starting local document extraction", url=url, download_dir=self.download_dir)

        # Clean any previous downloads
        self._cleanup_downloads()

        # Simple browser configuration focusing on stability
        browser = Browser(
            headless=os.getenv("HEADLESS", "true").lower() == "true",
            accept_downloads=True,
            auto_download_pdfs=True,
            downloads_path=str(Path(self.download_dir).resolve()),

            # Simple browser args for stability
            args=[
                "--disable-features=PDFViewer",
                "--disable-print-preview",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],

            # Timing controls for stability
            wait_between_actions=0.6,
            wait_for_network_idle_page_load_time=2.5,
        )

        # Create focused task prompt
        task = self._create_simple_extraction_task(url)

        # Create agent
        agent = Agent(
            task=task,
            llm=self.llm,
            browser=browser,
        )

        # Run agent synchronously for simplicity
        logger.info("Running browser agent for PDF extraction")
        result = agent.run_sync()

        # Check for downloaded files
        downloaded_files = self._find_downloaded_pdfs()

        if downloaded_files:
            logger.info("✅ PDF extraction successful", files_found=len(downloaded_files))
            for file_path in downloaded_files:
                file_size = Path(file_path).stat().st_size
                logger.info("📄 PDF downloaded",
                           filename=os.path.basename(file_path),
                           size_bytes=file_size,
                           size_mb=round(file_size / 1024 / 1024, 2))
        else:
            logger.warning("⚠️ No PDF files were downloaded")

        return downloaded_files

    def _validate_url(self, url: str) -> None:
        """Validate that the URL is supported."""
        if self.HOST not in url.lower():
            raise ValueError(f"This extractor only supports {self.HOST}")

    def _create_simple_extraction_task(self, url: str) -> str:
        """Create focused task instructions for PDF extraction."""
        return f"""
You are extracting PDF files from a public event page.

GOAL:
- Visit: {url}
- Locate the section that holds documents (keywords: "View Event Package", "Documents", "Attachments", "Files", "Bid Documents").
- Open/expand the documents area if needed.
- For EACH document link or button that is a PDF (link ends with .pdf OR the UI label includes 'PDF'/'View'/'Download'):
    - Click it to trigger a download (do NOT just open in-viewer).
    - If the site opens a new tab or a modal viewer, use the UI to download the file.
- Ensure downloads are saved to the configured folder ({self.download_dir}).
- If multiple pages of documents exist, scroll and capture them all.
- When finished, list the file names you saved.

CONSTRAINTS:
- Be precise: do not click unrelated links.
- Prefer actions that trigger a real file download over just navigating to a viewer.
- If a viewer opens, look for icons or menu items named 'Download', 'Save', or a download arrow, then click it.
- Wait for network to be idle after each download action before moving on.
""".strip()


    def _find_downloaded_pdfs(self) -> List[str]:
        """Find all PDF files in the download directory, including partial downloads."""
        pdf_files: List[str] = []

        if not Path(self.download_dir).exists():
            logger.debug(f"Download directory does not exist: {self.download_dir}")
            return pdf_files

        try:
            download_path = Path(self.download_dir)

            # Log all files in download directory for debugging
            all_files = list(download_path.iterdir())
            logger.debug(f"All files in download directory: {[f.name for f in all_files if f.is_file()]}")

            # Find completed PDF files
            for file_path in download_path.glob("*.pdf"):
                if file_path.is_file():
                    file_size = file_path.stat().st_size
                    if file_size > 0:
                        pdf_files.append(str(file_path))
                        logger.debug("Found completed PDF file",
                                     file=file_path.name,
                                     size=file_size)
                    else:
                        logger.debug("Found empty PDF file (skipped)",
                                     file=file_path.name)

            # Also check for partial downloads
            for file_path in download_path.iterdir():
                if file_path.is_file():
                    name_lower = file_path.name.lower()
                    if (name_lower.endswith('.crdownload') and 'pdf' in name_lower) or \
                       (name_lower.endswith('.partial') and 'pdf' in name_lower):
                        logger.debug("Found partial PDF download",
                                     file=file_path.name,
                                     size=file_path.stat().st_size)

        except Exception as e:
            logger.error("Error scanning download directory", error=str(e))

        logger.debug(f"Total PDF files found: {len(pdf_files)}")
        return sorted(pdf_files)


    def _cleanup_downloads(self) -> None:
        """Clean up downloaded files from local directory."""
        try:
            if not Path(self.download_dir).exists():
                return

            files_removed = 0
            for file_path in Path(self.download_dir).iterdir():
                if file_path.is_file():
                    try:
                        file_path.unlink()
                        files_removed += 1
                    except Exception as e:
                        logger.warning("Failed to remove file",
                                       file=file_path.name, error=str(e))

            if files_removed > 0:
                logger.info("Cleaned up download directory",
                            files_removed=files_removed)

        except Exception as e:
            logger.warning("Download cleanup failed", error=str(e))