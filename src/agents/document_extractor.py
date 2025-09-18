import os
import re
import time
from typing import List, Any
from urllib.parse import urlparse, urlsplit, urlunsplit, quote
import structlog
import boto3

from browser_use import Agent, Browser, ChatGoogle

logger = structlog.get_logger(__name__)


class DocumentExtractor:
    """
    CaleProcure-only extractor (Option 1):
      - Persist downloads to disk (downloads_path=/tmp/browser_downloads).
      - Poll until PDFs are fully written.
      - Upload to S3.
      - Delete local files afterwards.
    """

    HOST = "caleprocure.ca.gov"
    DOWNLOAD_DIR = "/tmp/browser_downloads"

    def __init__(self):
        # LLM required by browser-use Agent
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")

        self.llm = ChatGoogle(model="gemini-2.5-flash")

        # S3 via env creds (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION)
        self.s3 = boto3.client("s3")

        # Ensure downloads dir exists
        os.makedirs(self.DOWNLOAD_DIR, exist_ok=True)

        logger.info("CaleProcure DocumentExtractor initialized (Option 1: persistent downloads)",
                    download_dir=self.DOWNLOAD_DIR)

    # ---------------- Public API ----------------

    async def extract_documents(self, url: str, s3_bucket: str, s3_prefix: str) -> List[str]:
        """
        Extract PDFs from CaleProcure and upload to S3, deleting local files afterward.
        """
        self._assert_caleprocure(url)
        logger.info("Starting CaleProcure extraction", url=url, bucket=s3_bucket, prefix=s3_prefix)

        # Clean any leftovers from previous runs (best-effort)
        self._purge_local_pdfs()

        # Configure a real Browser with a persistent downloads path
        browser = Browser(
            headless=True,                   # set False to watch locally
            is_local=True,
            keep_alive=False,                # fine: we persist to disk
            user_data_dir=None,              # set a path if you want login/cookies persistence
            accept_downloads=True,
            downloads_path=self.DOWNLOAD_DIR,
            auto_download_pdfs=True,
            allowed_domains=[f"*.{self.HOST}", f"https://{self.HOST}"],
            minimum_wait_page_load_time=0.25,
            wait_for_network_idle_page_load_time=0.75,
            wait_between_actions=0.5,
        )

        # Deterministic flow: View Event Package -> click each attachment to download
        task = self._create_caleprocure_task(url)
        agent = Agent(
            task=task,
            llm=self.llm,
            browser=browser,   # <-- critical: pass the configured Browser
            use_vision=False,
            max_failures=5,
        )

        # Run the agent
        result = await agent.run()

        # Optional: parse visible direct .pdf links (not relied upon by this flow)
        direct_urls = self._extract_pdf_urls_from_result(result)
        direct_urls = [u for u in direct_urls if self._is_caleprocure_pdf(u)]
        logger.info("Agent returned direct URLs (optional)", count=len(direct_urls))

        # Wait for the files to land & settle
        downloaded_paths = self._wait_for_pdf_downloads(timeout_sec=45, settle_sec=1.5)
        logger.info("Found browser-downloaded PDFs", count=len(downloaded_paths), files=downloaded_paths)

        # Upload all to S3
        uploaded_uris: List[str] = []
        for path in downloaded_paths:
            try:
                s3_uri = self._upload_path_to_s3(path, s3_bucket, s3_prefix)
                uploaded_uris.append(s3_uri)
                logger.info("Uploaded PDF to S3", local=path, s3_uri=s3_uri)
            except Exception as e:
                logger.error("Failed to upload PDF to S3", local=path, error=str(e))

        # Always delete local files afterward (best-effort)
        self._purge_local_pdfs()

        logger.info("CaleProcure extraction completed", total_files=len(uploaded_uris))
        return uploaded_uris

    # ---------------- Task / URL helpers ----------------

    def _assert_caleprocure(self, url: str) -> None:
        if self.HOST not in urlparse(url).netloc.lower():
            raise ValueError("This extractor only supports caleprocure.ca.gov")

    def _create_caleprocure_task(self, url: str) -> str:
        return f"""
Navigate to {url}.

Follow this exact sequence:
1) Find and click a button or link with text containing "View Event Package" (or "Event Package").
2) Wait for the document page to fully load.
3) Locate the list/table of attachments/documents (PDFs).
4) Click each document's download link/button so the browser saves the PDF files locally.
   The environment is configured to automatically accept downloads and save PDFs to disk.
5) If a link opens a new tab or preview, proceed to ensure the file is downloaded.

Finally:
- If you can see any direct .pdf links on the page, list them (one per line).
- The primary goal is that the files are downloaded locally.
"""

    @staticmethod
    def _normalize_url(url: str) -> str:
        try:
            parts = urlsplit(url)
            path = quote(parts.path, safe="/-._~")
            return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))
        except Exception:
            return url

    def _is_caleprocure_pdf(self, url: str) -> bool:
        p = urlparse(url)
        return (self.HOST in p.netloc.lower()) and (".pdf" in p.path.lower())

    # ---------------- Result parsing ----------------

    def _extract_pdf_urls_from_result(self, result: Any) -> List[str]:
        """Optional: extract direct .pdf links from the agent's output."""
        try:
            content = getattr(result, "content", result)
            content = content if isinstance(content, str) else str(content)
            content = content.replace("\\n", "\n")

            pat = r'https?://[^\s<>"\']+\.pdf(?:\?[^\s<>"\']*)?'
            found = re.findall(pat, content, flags=re.IGNORECASE)

            cleaned, seen = [], set()
            for u in found:
                u = u.strip().rstrip('.,;)"\'')
                if u not in seen:
                    seen.add(u)
                    cleaned.append(u)

            logger.info("Extracted PDF URLs from agent output",
                        total_chars=len(content), raw_count=len(found), unique_count=len(cleaned))
            return cleaned
        except Exception as e:
            logger.error("Failed to extract PDF URLs from result", error=str(e))
            return []

    # ---------------- Download wait / cleanup / S3 ----------------

    def _wait_for_pdf_downloads(self, timeout_sec: int = 45, settle_sec: float = 1.5) -> List[str]:
        """
        Poll the downloads folder until at least one stable .pdf appears.
        Stable == file exists, not .crdownload/.partial, and size stops changing for settle_sec.
        Returns a list of absolute file paths.
        """
        start = time.time()
        last_sizes = {}

        def list_pdf_candidates() -> List[str]:
            if not os.path.exists(self.DOWNLOAD_DIR):
                return []
            out = []
            for f in os.listdir(self.DOWNLOAD_DIR):
                fl = f.lower()
                if fl.endswith(".pdf") and not fl.endswith(".crdownload") and not fl.endswith(".partial"):
                    out.append(os.path.join(self.DOWNLOAD_DIR, f))
            return out

        stable_paths: List[str] = []

        while time.time() - start < timeout_sec:
            cand = list_pdf_candidates()
            if not cand:
                time.sleep(0.5)
                continue

            # track sizes to detect settling
            stable_now = []
            for path in cand:
                try:
                    sz = os.path.getsize(path)
                except FileNotFoundError:
                    continue
                prev = last_sizes.get(path)
                last_sizes[path] = sz
                if prev is not None and prev == sz:
                    stable_now.append(path)

            if stable_now:
                time.sleep(settle_sec)
                confirm = []
                for path in stable_now:
                    try:
                        if os.path.getsize(path) == last_sizes.get(path):
                            confirm.append(path)
                    except FileNotFoundError:
                        pass
                if confirm:
                    stable_paths = sorted(set(confirm))
                    break

            time.sleep(0.5)

        return stable_paths

    def _purge_local_pdfs(self) -> None:
        """Delete any PDFs in the downloads dir (best-effort cleanup)."""
        if not os.path.exists(self.DOWNLOAD_DIR):
            return
        for f in os.listdir(self.DOWNLOAD_DIR):
            if f.lower().endswith(".pdf") or f.endswith(".crdownload") or f.endswith(".partial"):
                path = os.path.join(self.DOWNLOAD_DIR, f)
                try:
                    os.remove(path)
                except Exception as e:
                    logger.warning("Failed to remove local file", path=path, error=str(e))

    def _upload_path_to_s3(self, path: str, bucket: str, prefix: str) -> str:
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        key = self._s3_key_for_local(path, prefix)
        with open(path, "rb") as f:
            self.s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=f.read(),
                ContentType="application/pdf",
            )
        return f"s3://{bucket}/{key}"

    @staticmethod
    def _s3_key_for_local(local_path: str, prefix: str) -> str:
        filename = os.path.basename(local_path) or "download.pdf"
        prefix = prefix.strip("/")
        return f"{prefix}/{filename}" if prefix else filename

# TODO: 1. split up into tasks - first successfully locally download single PDF. if downloaded, stop.
#       2. download pdf and upload it to S3.
#       3. run on full page and extract all PDFs.