"""
Fixed PDF download script with proper Playwright/Chromium configuration for headless downloads
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
import structlog
from browser_use import Agent, ChatGoogle, Browser

logger = structlog.get_logger(__name__)

async def test_pdf_downloads_with_proper_config():
    """Test PDF download with proper headless configuration."""
    load_dotenv()

    # Create downloads directory with absolute path
    downloads_dir = Path("./downloads").resolve()
    downloads_dir.mkdir(exist_ok=True)

    print(f"Downloads directory: {downloads_dir}")

    try:
        # Initialize LLM with Gemini
        llm = ChatGoogle(model='gemini-2.5-flash')

        # Configure browser with proper download settings for headless mode
        # The key is to set browser preferences correctly
        browser = Browser(
            headless=False,
            downloads_path=str(downloads_dir),
            # These are the critical settings for headless downloads
            # browser_type="chromium",  # assuming explicitly use chromium
            accept_downloads=True,
            auto_download_pdfs=True,
        )

        # Enhanced task that includes download verification
        task = f"""
        Go to https://caleprocure.ca.gov/event/0850/0000036230

        1. Wait 3 seconds for page to load
        2. Click "View Event Package" button
        3. Wait 5 seconds for page to load
        4. Scroll down to find the attachments section
        5. For EACH PDF download button you find:
           a. Click the download button
           b. Wait 3 seconds for modal to appear
           c. Click "Download Attachment" in the modal
           d. Wait 15 seconds for download to complete (IMPORTANT: wait full time)
           e. Close the modal if it's still open
           f. Check if the file was downloaded to {downloads_dir}
        
        CRITICAL: After each download, wait the full 15 seconds and verify the download completed.
        Do NOT proceed to the next download until you've confirmed the previous one finished.
        
        At the end, list all files that should be in the downloads directory.
        """

        agent = Agent(
            task=task,
            llm=llm,
            browser=browser
        )

        logger.info("Starting PDF download with proper configuration")

        # Run the agent
        result = await agent.run()

        logger.info("Agent completed", result=result.final_result())

        # Wait extra time for any pending downloads
        print("Waiting additional 15 seconds for any pending downloads...")
        await asyncio.sleep(15)

        # Check for files in multiple locations
        locations_to_check = [
            downloads_dir,
            Path.home() / "Downloads",
            Path("/tmp"),
            Path.cwd(),  # Current working directory
        ]

        all_found_files = []

        for location in locations_to_check:
            if location.exists():
                try:
                    pdf_files = list(location.glob("*.pdf"))
                    # Check for recently modified PDFs (last 30 minutes)
                    import time
                    current_time = time.time()
                    recent_pdfs = [f for f in pdf_files if current_time - f.stat().st_mtime < 1800]

                    if recent_pdfs:
                        print(f"\nFound recent PDFs in {location}:")
                        for pdf in recent_pdfs:
                            print(f"  - {pdf.name} ({pdf.stat().st_size} bytes)")
                            all_found_files.append(pdf)
                except PermissionError:
                    pass

        if all_found_files:
            print(f"\n✅ Total PDFs found: {len(all_found_files)}")
        else:
            print("\n❌ No PDF files were found in any location")

        return all_found_files

    except Exception as e:
        logger.error("PDF download test failed", error=str(e))
        print(f"Test failed: {e}")
        return []

if __name__ == "__main__":
    asyncio.run(test_pdf_downloads_with_proper_config())