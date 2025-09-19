import asyncio
from pathlib import Path
from dotenv import load_dotenv
from browser_use import Agent, ChatGoogle, Browser
from browser_use.tools.service import Tools
import structlog

from .custom_download_tool import DownloadPDFAction, download_pdf_with_session

logger = structlog.get_logger(__name__)

async def download_pdfs_with_custom_tool():
    """Download PDFs using custom tool with session cookies."""
    load_dotenv()

    # Create data directory
    data_dir = Path("./data")
    data_dir.mkdir(exist_ok=True)

    # Configure browser
    browser = Browser(
        headless=True,
        disable_security=True,
        keep_alive=False,
    )

    # Initialize LLM
    llm = ChatGoogle(model='gemini-2.5-flash')

    # Create custom tools instance
    tools = Tools()

    # Register our custom PDF download tool
    @tools.registry.action(
        'Download a PDF file using the current browser session cookies and authentication',
        param_model=DownloadPDFAction,
    )
    async def download_pdf_tool(params: DownloadPDFAction, browser_session):
        return await download_pdf_with_session(params, browser_session, data_dir)

    # Create agent with custom tools
    agent = Agent(
        task="""
        Go to https://caleprocure.ca.gov/event/0850/0000036230

        Wait 5 seconds for the page to fully load.
        Press on the "View Event Package" button.
        Wait 5 seconds for the page to fully load.

        Find all PDF download buttons/links on the page. For each PDF file, I need you to:

        1. Right-click on the download button to inspect it
        2. Extract the actual href/URL that the download button points to
        3. Get the filename from the button text or URL
        4. Use the download_pdf_tool to download each file

        The expected PDFs are:
        - Liquid_Files_Instructions.pdf
        - CSL_1499_Generative_AI_Impact_Assessment_Form.pdf
        - QnA_46_GenAI_Level_2_Provisions_-_Minimum_Requirements.pdf
        - QnA_46_GenAI_Level_3_Provisions_-_Full_Requirements.pdf
        - QnA_208_8k_FY_25-26_Proposed_Budget_-_June_2025_Meeting.pdf
        - QnA208_May_25_Commission_-_FY25_-26_Business_Plan.pdf

        For each PDF, call download_pdf_tool with:
        - pdf_url: the extracted download URL
        - filename: the PDF filename

        Use the custom download tool instead of clicking download buttons.
        """,
        llm=llm,
        browser=browser,
        tools=tools,
        max_failures=5
    )

    try:
        logger.info("Starting PDF download with custom tool")
        result = await agent.run()
        logger.info("Custom PDF download completed", result=result.final_result())

        # List downloaded files
        downloaded_files = list(data_dir.glob("*.pdf"))
        logger.info(f"Downloaded {len(downloaded_files)} PDF files", files=[f.name for f in downloaded_files])

        return downloaded_files

    except Exception as e:
        logger.error("Error during custom PDF download", error=str(e))
        raise
    finally:
        try:
            if hasattr(browser, 'session') and browser.session:
                await browser.session.close()
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")

if __name__ == "__main__":
    asyncio.run(download_pdfs_with_custom_tool())