"""
Simple test script to verify core document extraction works.
Tests the DocumentExtractor directly without the full API.
"""

import os
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_simple_extraction():
    """Test document extraction with the simplest California eCal URL."""

    # Check required environment variables
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ ERROR: GEMINI_API_KEY not found in .env")
        return False

    if not os.getenv("AWS_ACCESS_KEY_ID") or not os.getenv("AWS_SECRET_ACCESS_KEY"):
        print("❌ ERROR: AWS credentials not found in .env")
        return False

    print("🧪 Starting simple extraction test...")
    print("📋 URL: https://caleprocure.ca.gov/event/0850/0000036230")
    print("🪣 S3 Bucket: my-solicitations")
    print("📁 S3 Prefix: test/simple-test/")
    print()

    try:
        # Import here to catch import errors early
        from src.agents.document_extractor import DocumentExtractor

        # Initialize extractor
        print("🔧 Initializing DocumentExtractor...")
        extractor = DocumentExtractor()
        print("✅ DocumentExtractor initialized")

        # Run extraction
        print("🚀 Starting extraction (this may take 1-2 minutes)...")
        results = await extractor.extract_documents(
            url="https://caleprocure.ca.gov/event/0850/0000036230",
            s3_bucket="my-solicitations",
            s3_prefix="test/simple-test/"
        )

        # Show results
        print(f"\n🎉 Extraction completed!")
        print(f"📊 Found {len(results)} files:")
        for i, file_url in enumerate(results, 1):
            print(f"   {i}. {file_url}")

        return len(results) > 0

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Try: pip install -r requirements.txt")
        return False

    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        print(f"🔍 Error type: {type(e).__name__}")
        return False

if __name__ == "__main__":
    print("🔧 Simple Document Extraction Test")
    print("=" * 50)

    success = asyncio.run(test_simple_extraction())

    if success:
        print("\n✅ Test PASSED - Extraction working!")
    else:
        print("\n❌ Test FAILED - Check errors above")

    exit(0 if success else 1)