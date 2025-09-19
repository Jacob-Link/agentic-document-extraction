#!/usr/bin/env python3
"""
Simple test script for the simplified local PDF extraction.
"""

import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from agents.document_extractor import DocumentExtractor

def main():
    """Test the simplified local PDF extraction."""

    # Test URL from CLAUDE.md
    test_url = "https://caleprocure.ca.gov/event/0850/0000036230"

    print(f"🚀 Testing simplified PDF extraction for: {test_url}")
    print(f"📁 Downloads will be saved to: ./data/")

    try:
        # Create extractor
        extractor = DocumentExtractor()

        # Extract documents locally
        downloaded_files = extractor.extract_documents_local(test_url)

        # Show results
        if downloaded_files:
            print(f"\n✅ Successfully downloaded {len(downloaded_files)} PDF files:")
            for file_path in downloaded_files:
                file_name = os.path.basename(file_path)
                file_size = Path(file_path).stat().st_size
                print(f"   📄 {file_name} ({file_size:,} bytes)")
        else:
            print("\n❌ No PDF files were downloaded")

        return len(downloaded_files) > 0

    except Exception as e:
        print(f"\n💥 Error during extraction: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)