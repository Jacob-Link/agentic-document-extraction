"""
Test script to verify Gemini API key is working correctly.
Simple direct test without browser-use.
"""

import os
import google.generativeai as genai
from dotenv import load_dotenv

def test_gemini_key():
    """Test if Gemini API key is valid and working."""
    print("🔑 Testing Gemini API Key...")

    # Load environment variables
    load_dotenv()

    # Check if API key exists
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("❌ ERROR: GEMINI_API_KEY not found in environment variables")
        print("   Please add GEMINI_API_KEY to your .env file")
        return False

    print(f"✅ API key found: {api_key[:10]}...")

    try:
        # Configure the API key
        genai.configure(api_key=api_key)

        # Initialize the model
        model = genai.GenerativeModel('gemini-2.5-flash')

        # Test a simple prompt
        print("🧪 Testing API call...")

        response = model.generate_content("What is hello world?")

        print(f"✅ API Response: {response.text}")
        print("🎉 Gemini API key is working correctly!")
        return True

    except Exception as e:
        print(f"❌ ERROR: Failed to connect to Gemini API")
        print(f"   Error details: {str(e)}")
        print("   Please check your API key and internet connection")
        return False

if __name__ == "__main__":
    success = test_gemini_key()
    exit(0 if success else 1)

    # response from running file:
    # API Response: "Hello, World!" is a **traditional first program** that most people write when they start learning a new programming language or development environment. Here's a breakdown of what it is and why it's significant...