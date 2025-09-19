# save as scrape_pdfs_browser_use.py
from pathlib import Path
from dotenv import load_dotenv

from browser_use import Agent, Browser
from browser_use.llm import ChatGoogle  # or ChatOpenAI/ChatAnthropic

TEST_URL = "https://caleprocure.ca.gov/event/0850/0000036230"
DATA_DIR = Path("./data")

def main():
    load_dotenv()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    browser = Browser(
        headless=True,
        accept_downloads=True,
        auto_download_pdfs=True,  # let browser-use handle PDF downloads
        downloads_path=str(DATA_DIR.resolve()),  # absolute path is best

        # Chromium launch flags go here (NOT "browser_args")
        args=[
            "--disable-features=PDFViewer",
            "--disable-print-preview",
        ],

        # timing knobs
        wait_between_actions=0.6,
        wait_for_network_idle_page_load_time=2.5,
    )

    # Focused, deterministic instructions for the agent:
    # (These align with the browser-use "LLM Quickstart" pattern—give clear step goals.  [oai_citation:1‡Browser Use](https://docs.browser-use.com/quickstart_llm))
    task = f"""
You are extracting PDF files from a public event page.

GOAL:
- Visit: {TEST_URL}
- Locate the section that holds documents (keywords: "View Event Package", "Documents", "Attachments", "Files", "Bid Documents").
- Open/expand the documents area if needed.
- For EACH document link or button that is a PDF (link ends with .pdf OR the UI label includes 'PDF'/'View'/'Download'):
    - Click it to trigger a download (do NOT just open in-viewer).
    - If the site opens a new tab or a modal viewer, use the UI to download the file.
- Ensure downloads are saved to the configured folder (./data/).
- If multiple pages of documents exist, scroll and capture them all.
- When finished, list the file names you saved.

CONSTRAINTS:
- Be precise: do not click unrelated links.
- Prefer actions that trigger a real file download over just navigating to a viewer.
- If a viewer opens, look for icons or menu items named 'Download', 'Save', or a download arrow, then click it.
- Wait for network to be idle after each download action before moving on.
"""

    agent = Agent(
        task=task.strip(),
        llm=ChatGoogle(model="gemini-2.5-flash"),
        browser=browser,
    )

    result = agent.run_sync()

    print("\n=== Agent run finished ===")
    print(result.final_result or "")
    print("\nDownloaded files:")
    for p in sorted(DATA_DIR.glob("*.pdf")):
        print(" -", p.name)

if __name__ == "__main__":
    main()