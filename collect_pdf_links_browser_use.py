# save as collect_pdf_links_browser_use.py
from pathlib import Path
from dotenv import load_dotenv

from browser_use import Agent, Browser
from browser_use.llm import ChatGoogle  # or ChatOpenAI/ChatAnthropic

TEST_URL = "https://caleprocure.ca.gov/event/0850/0000036230"

def main():
    load_dotenv()

    browser = Browser(
        headless=True,
        accept_downloads=False,  # we're NOT downloading in this run
        # keep flags simple & stable; add these if running in containers:
        args=[
            "--disable-features=PDFViewer",
            "--disable-print-preview",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--window-size=1400,900",
        ],

        highlight_elements=False,
        wait_between_actions=0.4,
        wait_for_network_idle_page_load_time=1.5,
    )

    task = f"""
You are collecting ALL PDF links from the event page and returning them as JSON. Do NOT try to download any file.

GOAL:
- Visit: {TEST_URL}
- Click "View Event Package".
- Scroll to the attachments table.
- For EACH attachment row, click its "View" / download icon button (these have ids like PV_ATTACH_WRK_SCM_DOWNLOAD$…).
- When the modal opens, read the direct PDF URL from the anchor with id="downloadButton" (use its `href`).
- Also capture a sensible filename (prefer the tail of the href; fall back to modal title text).
- Push each result into a global array on the page: window.__pdfs = window.__pdfs || []; window.__pdfs.push({{ filename, href }});
- Close the modal (button[data-dismiss='modal'] or a button labeled "Close").
- Repeat until all rows are processed.
- Finally, return EXACTLY the JSON array string from `window.__pdfs` via the `done` action.

HARD CONSTRAINTS:
- Never use or open a PDF viewer tab intentionally; if a new tab opens, immediately close it and continue.
- Use `execute_js` to interact with the DOM when reading attributes (e.g., `#downloadButton[href]`).
- Keep state in `window.__pdfs` so we can return it at the end.
- Be deterministic: do NOT switch tabs to interact with the PDF viewer.

USEFUL SNIPPETS (use as-is with execute_js at appropriate times):

// 0) ensure accumulator exists
(() => {{ window.__pdfs = window.__pdfs || []; return window.__pdfs.length; }})()

// 1) count attachment buttons (for logging/loop planning)
(() => {{
  return document.querySelectorAll("button[id^='PV_ATTACH_WRK_SCM_DOWNLOAD$']").length;
}})()

// 2) after clicking a row button and the modal is visible, harvest href + filename into window.__pdfs
(() => {{
  const a = document.querySelector("#downloadButton");
  const href = a?.getAttribute("href") || null;
  let filename = null;
  if (href) {{
    const tail = href.split("/").pop() || "";
    try {{
      filename = decodeURIComponent(tail).replace(/\\+/g, " ");
    }} catch (e) {{
      filename = tail;
    }}
  }}
  if (!filename) {{
    const title = document.querySelector(".modal-title")?.textContent?.trim();
    filename = (title && title.toLowerCase().endsWith(".pdf")) ? title : (title ? title + ".pdf" : "attachment.pdf");
  }}
  window.__pdfs = window.__pdfs || [];
  window.__pdfs.push({{ filename, href }});
  return window.__pdfs.length;
}})()

// 3) close the modal
(() => {{
  const btn = document.querySelector("button[data-dismiss='modal'], button.btn.btn-outline-primary, .modal-footer button");
  btn?.click();
  return true;
}})()

// 4) return final JSON array string
(() => {{
  window.__pdfs = window.__pdfs || [];
  return JSON.stringify(window.__pdfs);
}})()

Return ONLY the JSON array from step (4) in your final `done` message.
"""

    agent = Agent(
        task=task.strip(),
        llm=ChatGoogle(model="gemini-2.5-flash"),
        browser=browser,
    )

    result = agent.run_sync()

    print("\n=== Agent run finished ===")
    print(result.final_result or "")

if __name__ == "__main__":
    main()