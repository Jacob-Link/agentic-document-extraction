import asyncio
import httpx
from pathlib import Path
from pydantic import BaseModel, Field
from browser_use.browser import BrowserSession
import structlog

logger = structlog.get_logger(__name__)

class DownloadPDFAction(BaseModel):
    """Pydantic model for PDF download tool parameters."""
    pdf_url: str = Field(description="The URL of the PDF file to download")
    filename: str = Field(description="The filename to save the PDF as (e.g., 'document.pdf')")

async def download_pdf_with_session(
    params: DownloadPDFAction,
    browser_session: BrowserSession,
    download_dir: Path
) -> str:
    """
    Custom tool to download a PDF using the browser session's cookies.

    Args:
        params: The download parameters (URL and filename)
        browser_session: The browser session with cookies
        download_dir: Directory to save the file

    Returns:
        Path to the downloaded file
    """
    try:
        logger.info(f"Downloading PDF from {params.pdf_url}")

        # Get cookies from the browser session
        cookies = {}
        if hasattr(browser_session, 'session') and browser_session.session:
            # Extract cookies from the browser session
            try:
                # Get the current page cookies
                browser_cookies = await browser_session.session.context.cookies()
                cookies = {cookie['name']: cookie['value'] for cookie in browser_cookies}
                logger.info(f"Using {len(cookies)} cookies from browser session")
            except Exception as e:
                logger.warning(f"Could not extract cookies: {e}")

        # Create download directory if it doesn't exist
        download_dir.mkdir(exist_ok=True)

        # Download the file using httpx with session cookies
        async with httpx.AsyncClient(cookies=cookies, timeout=30.0) as client:
            # Add headers to mimic browser request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/pdf,application/octet-stream,*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }

            response = await client.get(params.pdf_url, headers=headers, follow_redirects=True)
            response.raise_for_status()

            # Validate it's a PDF
            content_type = response.headers.get('content-type', '').lower()
            if len(response.content) >= 4 and response.content[:4] == b'%PDF':
                logger.info(f"Valid PDF detected, size: {len(response.content)} bytes")
            elif 'pdf' in content_type:
                logger.info(f"PDF content-type detected: {content_type}")
            else:
                logger.warning(f"Unexpected content-type: {content_type}")

            # Save the file
            file_path = download_dir / params.filename
            with open(file_path, 'wb') as f:
                f.write(response.content)

            logger.info(f"Successfully downloaded {params.filename} to {file_path}")
            return str(file_path)

    except Exception as e:
        error_msg = f"Failed to download {params.pdf_url}: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)