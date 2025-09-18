import re
from typing import List, Set
from urllib.parse import urljoin, urlparse
import structlog

logger = structlog.get_logger(__name__)

class PDFDetector:
    """Utility class for detecting and validating PDF URLs."""

    def __init__(self):
        """Initialize PDF detector with common patterns."""
        self.pdf_patterns = [
            r'\.pdf$',
            r'\.pdf\?',
            r'\.pdf#',
            r'/pdf/',
            r'application/pdf',
            r'content-type.*pdf'
        ]

        self.pdf_indicators = [
            'solicitation',
            'amendment',
            'addendum',
            'document',
            'attachment',
            'rfp',
            'rfq',
            'bid',
            'proposal'
        ]

        logger.info("PDFDetector initialized")

    def extract_pdf_urls_from_html(self, html_content: str, base_url: str) -> List[str]:
        """
        Extract potential PDF URLs from HTML content.

        Args:
            html_content: HTML content to parse
            base_url: Base URL for resolving relative links

        Returns:
            List of potential PDF URLs
        """
        pdf_urls = set()

        try:
            # Find all href attributes
            href_pattern = r'href\s*=\s*["\']([^"\']+)["\']'
            hrefs = re.findall(href_pattern, html_content, re.IGNORECASE)

            for href in hrefs:
                if self._is_likely_pdf_url(href):
                    # Resolve relative URLs
                    full_url = urljoin(base_url, href)
                    pdf_urls.add(full_url)

            # Find direct PDF URLs in text
            url_pattern = r'https?://[^\s<>"\']+\.pdf(?:\?[^\s<>"\']*)?'
            direct_urls = re.findall(url_pattern, html_content, re.IGNORECASE)
            pdf_urls.update(direct_urls)

            logger.info("Extracted PDF URLs from HTML", count=len(pdf_urls))
            return list(pdf_urls)

        except Exception as e:
            logger.error("Failed to extract PDF URLs from HTML", error=str(e))
            return []

    def _is_likely_pdf_url(self, url: str) -> bool:
        """Check if a URL is likely to be a PDF."""
        url_lower = url.lower()

        # Check for PDF file extension
        for pattern in self.pdf_patterns:
            if re.search(pattern, url_lower):
                return True

        # Check for PDF-related keywords
        for indicator in self.pdf_indicators:
            if indicator in url_lower:
                return True

        return False

    def validate_pdf_urls(self, urls: List[str]) -> List[str]:
        """
        Validate and filter PDF URLs.

        Args:
            urls: List of URLs to validate

        Returns:
            List of validated PDF URLs
        """
        validated_urls = []

        for url in urls:
            if self._is_valid_pdf_url(url):
                validated_urls.append(url)

        logger.info("Validated PDF URLs", original_count=len(urls), validated_count=len(validated_urls))
        return validated_urls

    def _is_valid_pdf_url(self, url: str) -> bool:
        """Validate if a URL is a proper PDF URL."""
        try:
            # Parse URL
            parsed = urlparse(url)

            # Must have scheme and netloc
            if not parsed.scheme or not parsed.netloc:
                return False

            # Check if it's HTTP/HTTPS
            if parsed.scheme not in ['http', 'https']:
                return False

            # Check if it looks like a PDF
            if self._is_likely_pdf_url(url):
                return True

            return False

        except Exception:
            return False

    def deduplicate_urls(self, urls: List[str]) -> List[str]:
        """Remove duplicate URLs while preserving order."""
        seen = set()
        deduplicated = []

        for url in urls:
            # Normalize URL for comparison
            normalized = self._normalize_url(url)
            if normalized not in seen:
                seen.add(normalized)
                deduplicated.append(url)

        logger.info("Deduplicated URLs", original_count=len(urls), deduplicated_count=len(deduplicated))
        return deduplicated

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication."""
        try:
            parsed = urlparse(url)
            # Remove fragment and normalize query parameters
            normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                # Sort query parameters for consistent comparison
                query_params = sorted(parsed.query.split('&'))
                normalized += '?' + '&'.join(query_params)
            return normalized.lower()
        except Exception:
            return url.lower()