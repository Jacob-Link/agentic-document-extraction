import os
import re
import time
from typing import List, Any
from urllib.parse import urlparse, urlsplit, urlunsplit, quote
import structlog
import boto3
import httpx
import asyncio
from dotenv import load_dotenv

from browser_use import Agent, Browser, ChatGoogle

logger = structlog.get_logger(__name__)

class DocumentExtractor:
    """
    CaleProcure-only extractor focused on single PDF download:
      - Downloads ONE PDF file to disk (downloads_path=/tmp/browser_downloads).
      - Polls until the PDF is fully written.
      - Uploads to S3.
      - Deletes local files afterwards.
    """
    load_dotenv()
    HOST = "caleprocure.ca.gov"
    
    def __init__(self):
        self.download_dir = os.getenv("DISK_DOWNLOAD_DIR")

        # LLM required by browser-use Agent
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")

        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")

        self.llm = ChatGoogle(model="gemini-2.5-flash")

        # S3 via env creds (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION)
        self.s3 = boto3.client("s3")

        # Ensure downloads dir exists
        os.makedirs(self.download_dir, exist_ok=True)

        logger.info("CaleProcure DocumentExtractor initialized (single PDF download mode)",
                    download_dir=self.download_dir)

    # ---------------- Public API ----------------

    async def extract_documents(self, url: str, s3_bucket: str, s3_prefix: str) -> List[str]:
        """
        Extract a single PDF from CaleProcure and upload to S3, deleting local files afterward.
        """
        self._assert_caleprocure(url)
        logger.info("Starting CaleProcure extraction", url=url, bucket=s3_bucket, prefix=s3_prefix)

        # Clean any leftovers from previous runs (best-effort)
        self._purge_local_pdfs()

        # Configure a real Browser with a persistent downloads path
        browser = Browser(
            headless=True if os.getenv("HEADLESS").upper() == "TRUE" else False,
            is_local=True,
            keep_alive=False,                # fine: we persist to disk
            user_data_dir=None,              # set a path if you want login/cookies persistence
            accept_downloads=True,
            downloads_path=self.download_dir,
            auto_download_pdfs=True,
            allowed_domains=[f"*.{self.HOST}", f"https://{self.HOST}"],
            minimum_wait_page_load_time=0.5,
            wait_for_network_idle_page_load_time=1.5,
            wait_between_actions=1.0,
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

        # Parse agent results for multiple recovery strategies
        result_content = str(result)
        uploaded_uris: List[str] = []

        # STRATEGY A: Extract direct PDF URLs
        direct_urls = self._extract_pdf_urls_from_result(result)
        direct_urls = [u for u in direct_urls if self._is_caleprocure_pdf(u)]
        logger.info("STRATEGY A - Direct URLs extracted", count=len(direct_urls), urls=direct_urls)

        if direct_urls:
            success = await self._try_direct_download(direct_urls[0], s3_bucket, s3_prefix)
            if success:
                uploaded_uris.append(success)

        # STRATEGY B: Look for JavaScript URLs in result
        if not uploaded_uris:
            js_urls = self._extract_javascript_urls_from_result(result_content)
            logger.info("STRATEGY B - JavaScript URLs found", count=len(js_urls), urls=js_urls)

            for js_url in js_urls:
                try:
                    success = await self._try_direct_download(js_url, s3_bucket, s3_prefix)
                    if success:
                        uploaded_uris.append(success)
                        break
                except Exception as e:
                    logger.warning("Failed JavaScript URL download", url=js_url, error=str(e))

        # STRATEGY C: Check if download was triggered
        if not uploaded_uris and "DOWNLOAD_TRIGGERED" in result_content:
            logger.info("STRATEGY C - Download was triggered, waiting for files...")
            downloaded_paths = self._wait_for_pdf_downloads(timeout_sec=30, settle_sec=2.0)

            if downloaded_paths:
                first_path = downloaded_paths[0]
                try:
                    s3_uri = self._upload_path_to_s3(first_path, s3_bucket, s3_prefix)
                    uploaded_uris.append(s3_uri)
                    logger.info("STRATEGY C successful - Browser download completed", local=first_path, s3_uri=s3_uri)
                except Exception as e:
                    logger.error("Failed to upload triggered download", local=first_path, error=str(e))

        # STRATEGY D: Construct URLs from form patterns
        if not uploaded_uris:
            logger.info("STRATEGY D - Attempting URL construction from patterns...")
            constructed_urls = self._construct_urls_from_patterns(result_content, url)

            for construct_url in constructed_urls:
                try:
                    success = await self._try_direct_download(construct_url, s3_bucket, s3_prefix)
                    if success:
                        uploaded_uris.append(success)
                        logger.info("STRATEGY D successful", constructed_url=construct_url)
                        break
                except Exception as e:
                    logger.warning("Failed constructed URL", url=construct_url, error=str(e))

        # Final fallback: Wait for any browser downloads
        if not uploaded_uris:
            logger.info("All strategies failed, final fallback: checking for any downloads...")
            downloaded_paths = self._wait_for_pdf_downloads(timeout_sec=15, settle_sec=1.0)

            if downloaded_paths:
                first_path = downloaded_paths[0]
                try:
                    s3_uri = self._upload_path_to_s3(first_path, s3_bucket, s3_prefix)
                    uploaded_uris.append(s3_uri)
                    logger.info("Final fallback successful", local=first_path, s3_uri=s3_uri)
                except Exception as e:
                    logger.error("Failed final fallback upload", local=first_path, error=str(e))

        if not uploaded_uris:
            logger.error("All download strategies failed - no files extracted")

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
You are browsing California eProcurement (caleprocure.ca.gov) to download procurement documents.

Navigate to: {url}

STEP-BY-STEP INSTRUCTIONS:

1. INITIAL NAVIGATION:
   - Go to the provided URL
   - Wait for the page to fully load
   - Look for the main content area

2. FIND THE DOCUMENTS SECTION:
   - Look for a button, link, or tab labeled:
     * "View Event Package"
     * "Event Package"
     * "Documents"
     * "Attachments"
     * "Files"
   - This is usually prominently displayed on the page
   - Click this button/link to access the documents

3. LOCATE PDF DOCUMENTS:
   - After clicking, you should see a list or table of documents
   - Look for files with .pdf extension or PDF icons
   - Common document names include:
     * "Solicitation.pdf"
     * "RFP.pdf"
     * "Amendment.pdf"
     * "Notice.pdf"
     * Any filename ending in .pdf

4. EXTRACT THE FIRST PDF (MULTIPLE STRATEGIES):
   - Find the FIRST PDF document in the list
   - Try these strategies in order:

   STRATEGY A - Direct URL:
   - Look for direct links to .pdf files in href attributes
   - Right-click on PDF links and "Copy link address"
   - Report the URL if found

   STRATEGY B - JavaScript Investigation:
   - If no direct URLs, investigate the download buttons
   - Use browser console to inspect onclick handlers
   - Execute: document.querySelector('[button-selector]').getAttribute('onclick')
   - Look for URL patterns in the JavaScript code
   - Try executing the download function and monitor network requests

   STRATEGY C - Force Download:
   - Click the download button for the first PDF
   - Allow 5-10 seconds for download to trigger
   - Report "DOWNLOAD_TRIGGERED" if clicking appears successful

   STRATEGY D - HTML Analysis:
   - Examine form actions, hidden fields, or AJAX endpoints
   - Look for patterns like /download?id=xxx or /attachment/xxx
   - Inspect network requests in browser developer tools

5. REPORT RESULTS:
   - Format: "STRATEGY_X: [result]"
   - Examples:
     * "STRATEGY_A: https://caleprocure.ca.gov/files/doc.pdf"
     * "STRATEGY_B: Found URL in onclick: /download?id=12345"
     * "STRATEGY_C: DOWNLOAD_TRIGGERED for QnA_file.pdf"
     * "STRATEGY_D: Found form action: /secure-download"

IMPORTANT NOTES:
- Try ALL strategies if earlier ones fail
- Use browser developer tools actively (F12)
- Monitor network tab for requests when clicking download
- JavaScript-based downloads are common on government sites
- Don't give up if first approach fails

SUCCESS CRITERIA: Extract usable information via any strategy above.
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

    # ---------------- Strategy helper methods ----------------

    async def _try_direct_download(self, pdf_url: str, s3_bucket: str, s3_prefix: str) -> str:
        """Try to download a PDF URL directly and upload to S3. Returns S3 URI on success."""
        try:
            logger.info("Attempting direct download", pdf_url=pdf_url)
            local_path = await self._download_pdf_directly(pdf_url)
            s3_uri = self._upload_path_to_s3(local_path, s3_bucket, s3_prefix)
            logger.info("Direct download successful", local=local_path, s3_uri=s3_uri)
            return s3_uri
        except Exception as e:
            logger.warning("Direct download failed", url=pdf_url, error=str(e))
            return None

    def _extract_javascript_urls_from_result(self, content: str) -> List[str]:
        """Extract URLs from JavaScript patterns in agent result."""
        urls = []

        # Look for common JavaScript URL patterns
        patterns = [
            r'onclick.*?["\']([^"\']*\.pdf[^"\']*)["\']',  # onclick with PDF
            r'/download\?[^"\']*',  # download query parameters
            r'/attachment/[^"\']*',  # attachment paths
            r'href\s*=\s*["\']([^"\']*download[^"\']*)["\']',  # download hrefs
            r'action\s*=\s*["\']([^"\']*download[^"\']*)["\']',  # form actions
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                if match and not match.startswith('javascript:'):
                    # Make absolute URL if relative
                    if match.startswith('/'):
                        match = f"https://{self.HOST}{match}"
                    urls.append(match)

        # Deduplicate while preserving order
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        return unique_urls

    def _construct_urls_from_patterns(self, content: str, base_url: str) -> List[str]:
        """Construct possible PDF URLs from common government site patterns."""
        constructed = []

        # Extract event/ID patterns from base URL
        event_match = re.search(r'/event/([^/]+)/([^/]+)', base_url)
        if event_match:
            org_code, event_id = event_match.groups()

            # Common government procurement PDF URL patterns
            patterns = [
                f"https://{self.HOST}/event/{org_code}/{event_id}/files/solicitation.pdf",
                f"https://{self.HOST}/event/{org_code}/{event_id}/attachment/1.pdf",
                f"https://{self.HOST}/download?event={event_id}&doc=1",
                f"https://{self.HOST}/files/{event_id}/documents/solicitation.pdf",
            ]
            constructed.extend(patterns)

        # Look for ID patterns in the content
        id_patterns = re.findall(r'(?:id|ID|Id)["\']?\s*[:=]\s*["\']?(\w+)', content)
        for doc_id in id_patterns[:3]:  # Try first 3 IDs found
            constructed.extend([
                f"https://{self.HOST}/download?id={doc_id}",
                f"https://{self.HOST}/attachment/{doc_id}.pdf",
                f"https://{self.HOST}/files/{doc_id}",
            ])

        return constructed

    # ---------------- Direct download / Download wait / cleanup / S3 ----------------

    async def _download_pdf_directly(self, pdf_url: str) -> str:
        """
        Download PDF directly using httpx to our download directory.
        Returns the local file path.
        """
        try:
            logger.info("Starting direct PDF download", url=pdf_url)

            # Generate filename from URL
            parsed = urlparse(pdf_url)
            filename = os.path.basename(parsed.path)
            if not filename or not filename.lower().endswith('.pdf'):
                filename = f"document_{int(time.time())}.pdf"

            local_path = os.path.join(self.download_dir, filename)

            # Download with httpx
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                logger.info("Fetching PDF content", url=pdf_url)
                response = await client.get(pdf_url)
                response.raise_for_status()

                # Validate content type
                content_type = response.headers.get('content-type', '').lower()
                logger.info("Response received", content_type=content_type, size=len(response.content))

                # Check PDF magic bytes
                if len(response.content) >= 4:
                    if response.content[:4] != b'%PDF':
                        logger.warning("Content may not be a valid PDF",
                                     first_bytes=response.content[:20].hex())

                # Save to download directory
                with open(local_path, 'wb') as f:
                    f.write(response.content)

                logger.info("PDF downloaded successfully",
                           local_path=local_path,
                           size_bytes=len(response.content))
                return local_path

        except Exception as e:
            logger.error("Failed to download PDF directly", url=pdf_url, error=str(e))
            raise

    def _wait_for_pdf_downloads(self, timeout_sec: int = 45, settle_sec: float = 1.5) -> List[str]:
        """
        Poll the downloads folder until at least one stable .pdf appears.
        Stable == file exists, not .crdownload/.partial, and size stops changing for settle_sec.
        Returns a list of absolute file paths.
        """
        start = time.time()
        last_sizes = {}

        logger.info("Starting download wait", timeout_sec=timeout_sec, settle_sec=settle_sec, download_dir=self.download_dir)

        def list_pdf_candidates() -> List[str]:
            if not os.path.exists(self.download_dir):
                return []
            out = []
            all_files = os.listdir(self.download_dir)
            for f in all_files:
                fl = f.lower()
                full_path = os.path.join(self.download_dir, f)
                # Include any file that might be a PDF (even with download suffixes)
                if (fl.endswith(".pdf") or fl.endswith(".crdownload") or
                    fl.endswith(".partial") or ".pdf" in fl):
                    out.append(full_path)
                    logger.debug("Found potential PDF file", file=f, path=full_path)
            return out

        def list_final_pdfs() -> List[str]:
            """Get only completed PDF files (no download suffixes)"""
            if not os.path.exists(self.download_dir):
                return []
            out = []
            for f in os.listdir(self.download_dir):
                fl = f.lower()
                if fl.endswith(".pdf") and not fl.endswith(".crdownload") and not fl.endswith(".partial"):
                    out.append(os.path.join(self.download_dir, f))
            return out

        stable_paths: List[str] = []
        last_check_time = start

        while time.time() - start < timeout_sec:
            current_time = time.time()

            # Check for any download activity first
            all_candidates = list_pdf_candidates()
            final_pdfs = list_final_pdfs()

            # Log progress every 5 seconds
            if current_time - last_check_time >= 5:
                logger.info("Download wait progress",
                           elapsed=int(current_time - start),
                           total_files=len(all_candidates),
                           completed_pdfs=len(final_pdfs))
                last_check_time = current_time

            if not final_pdfs:
                time.sleep(1.0)  # Check more frequently
                continue

            # track sizes to detect settling
            stable_now = []
            for path in final_pdfs:
                try:
                    sz = os.path.getsize(path)
                    logger.debug("Checking file size", file=os.path.basename(path), size=sz)
                except FileNotFoundError:
                    continue
                prev = last_sizes.get(path)
                last_sizes[path] = sz
                if prev is not None and prev == sz and sz > 0:  # Must have content
                    stable_now.append(path)

            if stable_now:
                logger.info("Found stable files, waiting for settle period", files=[os.path.basename(p) for p in stable_now])
                time.sleep(settle_sec)
                confirm = []
                for path in stable_now:
                    try:
                        current_size = os.path.getsize(path)
                        if current_size == last_sizes.get(path) and current_size > 0:
                            confirm.append(path)
                            logger.info("File confirmed stable", file=os.path.basename(path), size=current_size)
                    except FileNotFoundError:
                        pass
                if confirm:
                    stable_paths = sorted(set(confirm))
                    break

            time.sleep(1.0)  # Check every second

        logger.info("Download wait completed", stable_files=len(stable_paths), elapsed=int(time.time() - start))
        return stable_paths

    def _purge_local_pdfs(self) -> None:
        """Delete any PDFs in the downloads dir (best-effort cleanup)."""
        if not os.path.exists(self.download_dir):
            return
        for f in os.listdir(self.download_dir):
            if f.lower().endswith(".pdf") or f.endswith(".crdownload") or f.endswith(".partial"):
                path = os.path.join(self.download_dir, f)
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