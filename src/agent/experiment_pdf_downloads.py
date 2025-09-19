import asyncio
import httpx
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