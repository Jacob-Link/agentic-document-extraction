# 🤖 Agentic Document Extraction API

## 📋 Assignment Overview

This project was required to build a containerized FastAPI service using Browser Use + Gemini 2.5+ that accepts URLs and autonomously downloads solicitation PDFs to S3 storage. 

## 🎯 Current Implementation Status

**Unable to get browser-use working for PDF downloads**, so I built the entire structure with a **"dummy" file extraction system** that demonstrates all components working together:

- ✅ **Docker containerization**
- ✅ **FastAPI endpoints**
- ✅ **S3 integration**
- ✅ **Browser-Use + Gemini integration**
- ✅ **Complete technical stack skeleton**

## 🔧 Demo Functionality

Instead of PDF extraction, the current implementation:

1. **Takes the required API input format** (URL, S3 bucket, S3 prefix)
2. **Runs a demo browser task**: "Go to https://techcrunch.com, what is the main article presented - mainly about?"
3. **Prints the files which are in the specified S3 bucket**
4. **Showcases the complete technical stack structure working**

> 💡 Once PDF extraction works, it's simply a **plug-in to the existing working structure**.

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Gemini API Key
- AWS S3 credentials (with correct access permissions)

### Setup
```bash
# Create .env file with required API keys
cat > .env << EOF
GEMINI_API_KEY=your_gemini_api_key_here
AWS_ACCESS_KEY_ID=your_aws_access_key_here
AWS_SECRET_ACCESS_KEY=your_aws_secret_key_here
DEBUG=True
EOF

# Build and run
docker-compose up -d

# Test the API
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://caleprocure.ca.gov/event/0850/0000036230",
    "s3_bucket": "my-solicitations",
    "s3_prefix": "ecal/event-036230/"
  }'
```

## 🛠️ Technology Stack

| Component | Technology | Status |
|-----------|-----------|--------|
| 🌐 **Web Framework** | FastAPI 0.116.2 | ✅ Working |
| 🤖 **AI Agent** | Browser Use 0.7.8 + Gemini 2.5+ | ✅ Working |
| ☁️ **Storage** | AWS S3 (boto3 1.40.33) | ✅ Working |
| 🐳 **Container** | Docker | ✅ Working |
| 📊 **Logging** | Structlog 25.4.0 | ✅ Working |

## 📁 Project Structure

```
src/
├── api/
│   ├── main.py              # 🚀 FastAPI application
│   └── models.py            # 📋 Request/response models
├── agent/
│   └── document_extractor.py # 🤖 Browser agent (with DEBUG mode)
└── s3/
    ├── s3_uploader.py       # ☁️ S3 operations
    └── s3_dummy.py          # 🎭 Dummy S3 for demo

tests/
├── test_gemini_key.py       # 🔑 Gemini API test
└── test_s3_access.py        # 🪣 S3 access test
```

## 🎮 API Demo

**Endpoint**: `POST /extract`

**Input**:
```json
{
  "url": "https://caleprocure.ca.gov/event/0850/0000036230",
  "s3_bucket": "my-solicitations",
  "s3_prefix": "ecal/event-036230/"
}
```

**Demo Output**:
```json
{
  "status": "success",
  "files": [
    "s3://my-solicitations/ecal/event-036230/demo-file-1.pdf",
    "s3://my-solicitations/ecal/event-036230/demo-file-2.pdf"
  ],
  "message": ">>> successfully extracted 2 documents"
}
```
## 🔍 What I Tried for PDF Extraction

1. **Naive Approach**: Explicitly instructed the agent to navigate to procurement pages and click download buttons directly
2. **Browser Configuration**: Modified Chrome args and browser preferences to disable PDF viewers and force automatic downloads
3. **Link Extraction Strategy**: Instead of manual clicking, extracted href links from download buttons and processed them programmatically
4. **Custom Tool Development**: Created and registered a custom download tool to the agent for triggering HTTP downloads from href links while maintaining browser session context

## 📚 What I Have Learnt

* **Claude Code Excellence**: An incredible development tool - works best with focused, small task prompts. Let it run until achieving specific results. Running multiple terminals for non-overlapping tasks and tests maximizes efficiency.

* **Browser-Use Power & Limitations**: Powerful automation framework but lacks stability for certain complex tasks. The headless browser behavior can be unpredictable and requires deeper understanding.

* **Token Consumption Reality**: Over 6 million input tokens consumed rapidly when testing with Browser-Use + Gemini integration - cost considerations are crucial for production use.

## 🚀 What I Would Do Next (Given More Time & Resources)

### Technical Improvements
- **Upgrade to Claude Code Max** for enhanced capabilities and longer context windows
- **Investigate Browser-Use Pro**: Paid tier might offer more stable headless browser configurations and consistent behavior across devices
- **Deep Dive Learning**: Study Browser-Use architecture from fundamentals - appears learnable through systematic trial and error

---

*While I enjoyed this technical challenge, as of writing this im disappointed that the PDF extraction component could not be fully implemented within the given timeframe.*
