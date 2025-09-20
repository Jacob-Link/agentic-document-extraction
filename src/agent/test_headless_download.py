"""
Fixed PDF download script with proper browser configuration
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
import structlog
from browser_use import Agent, ChatGoogle, Browser

logger = structlog.get_logger(__name__)

async def test_pdf_downloads():
    """Test headless PDF download from California eCal procurement site."""
    load_dotenv()

    # Create downloads directory with absolute path
    downloads_dir = Path("./downloads").absolute()
    downloads_dir.mkdir(exist_ok=True)

    print(f"Downloads directory: {downloads_dir}")

    try:
        # Initialize LLM with Gemini
        llm = ChatGoogle(model='gemini-2.5-flash')

        # Configure browser with proper download settings
        browser = Browser(
            headless=True,
            accept_downloads=True,
            downloads_path=str(downloads_dir),
            auto_download_pdfs=True
        )

        # More explicit task with download verification
        task = f"""
        Navigate to https://caleprocure.ca.gov/event/0850/0000036230 and:
        1. Find and click the "View Event Package" link or button
        2. Wait for the page to load completely (wait 5 seconds)
        3. Scroll down to find the attachments section
        4. Identify all PDF download buttons on the page
        5. For each PDF download button:
           - Click the button
           - Wait for download modal to appear
           - Click "Download Attachment" in the modal
           - Wait 8-10 seconds for download to complete
           - Close any modal that appears
        6. Verify downloads by checking if files exist in {downloads_dir}
        7. Report the names and file sizes of all downloaded PDF files
        
        IMPORTANT: After each download, wait sufficient time and verify the file was created.
        """

        agent = Agent(
            task=task,
            llm=llm,
            browser=browser
        )

        logger.info("Starting PDF download test", url="https://caleprocure.ca.gov/event/0850/0000036230")

        # Run the agent
        result = await agent.run()

        logger.info("Agent task completed", result=result.final_result())

        # Wait a bit more for any pending downloads
        await asyncio.sleep(5)

        # Check downloaded files more thoroughly
        all_files = list(downloads_dir.iterdir())
        pdf_files = list(downloads_dir.glob("*.pdf"))

        print(f"\nAll files in downloads directory: {[f.name for f in all_files]}")
        print(f"PDF files found: {[f.name for f in pdf_files]}")

        logger.info("Download verification",
                   total_files=len(all_files),
                   pdf_count=len(pdf_files),
                   files=[f.name for f in all_files])

        if pdf_files:
            print(f"✅ Successfully downloaded {len(pdf_files)} PDF files:")
            for file in pdf_files:
                print(f"   - {file.name} ({file.stat().st_size} bytes)")
        else:
            print("❌ No PDF files were downloaded")
            if all_files:
                print("But found these files:", [f.name for f in all_files])

        return pdf_files

    except Exception as e:
        logger.error("PDF download test failed", error=str(e))
        print(f"❌ Test failed: {e}")
        return []

if __name__ == "__main__":
    asyncio.run(test_pdf_downloads())