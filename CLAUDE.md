# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an agentic document extraction API service that autonomously downloads solicitation PDFs from government procurement websites and uploads them to S3 storage. The service uses Browser Use with Gemini 2.5+ integration to handle complex web navigation, authentication, and document discovery.

## Technology Stack

- **Framework**: Browser Use 0.7.8 with Gemini 2.5+ integration
- **API**: FastAPI 0.116.2 + Uvicorn 0.35.0
- **Storage**: AWS S3 SDK (boto3 1.40.33)
- **Container**: Docker with headless Chromium browser support
- **Logging**: Structured logging with structlog 25.4.0
- **Async**: httpx for HTTP requests, aiofiles for file operations

## Project Structure

```
src/
├── api/
│   ├── main.py          # FastAPI application with /extract endpoint
│   └── models.py        # Pydantic request/response models
├── agents/
│   └── document_extractor.py  # Main browser agent orchestrator
├── extractors/
│   └── pdf_detector.py  # PDF URL detection and validation
└── utils/
    └── s3_uploader.py   # S3 download and upload functionality

tests/
├── test_gemini_key.py   # Test Gemini API connectivity
└── test_s3_access.py    # Test S3 bucket access
```

## API Specification

**Endpoint**: POST /extract

**Input Format**:
```json
{
  "url": "https://caleprocure.ca.gov/event/0850/0000036230",
  "s3_bucket": "my-solicitations",
  "s3_prefix": "ecal/event-036230/"
}
```

**Output Format**:
```json
{
  "status": "success",
  "files": [
    "s3://my-solicitations/ecal/event-036230/solicitation.pdf",
    "s3://my-solicitations/ecal/event-036230/amendments.pdf"
  ]
}
```

## Test URLs

The system must handle these three platform types:

1. **California eCal (No Auth)**:
   - https://caleprocure.ca.gov/event/0850/0000036230
   - https://caleprocure.ca.gov/event/2660/07A6065
   - https://caleprocure.ca.gov/event/75021/0000035944

2. **NY State (Auth Required)**:
   - https://www.nyscr.ny.gov/

3. **SourceWell (No Auth)**:
   - https://proportal.sourcewell-mn.gov/Module/Tenders/en/Tender/Detail/68914ced-5e07-409d-b301-b10001e4bbb0/#Document
   - https://proportal.sourcewell-mn.gov/Module/Tenders/en/Tender/Detail/88c9616c-5685-4cae-b7fa-9c8ad726c38d/#Document
   - https://proportal.sourcewell-mn.gov/Module/Tenders/en/Tender/Detail/321c8f90-b43d-46ae-a8e4-41ac7587bc19/#Document

## Required Environment Variables

Create `.env` file from template:
```bash
cp .env.template .env
```

Required variables:
```
GEMINI_API_KEY=your_gemini_api_key_here
AWS_ACCESS_KEY_ID=your_aws_access_key_here
AWS_SECRET_ACCESS_KEY=your_aws_secret_key_here
S3_BUCKET_NAME=my-solicitations
```

Optional variables:
```
AWS_REGION=us-east-1
NYSCR_USERNAME=your_ny_state_username
NYSCR_PASSWORD=your_ny_state_password
PORT=8000
BROWSER_HEADLESS=true
```

## Development Commands

### Local Development
```bash
# Create conda environment
conda env create -f environment.yml
conda activate agentic-extraction

# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Test API keys
python tests/test_gemini_key.py
python tests/test_s3_access.py

# Run locally
python -m uvicorn src.api.main:app --reload --port 8000
```

### Docker Deployment
```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Test health
curl http://localhost:8000/health
```

### API Testing
```bash
# Test extraction
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://caleprocure.ca.gov/event/0850/0000036230",
    "s3_bucket": "my-solicitations",
    "s3_prefix": "ecal/event-036230/"
  }'
```

## Architecture Overview

The system uses a multi-layered architecture:

1. **API Layer** (`src/api/`): FastAPI endpoints with request/response models
2. **Agent Layer** (`src/agents/`): Browser automation using browser-use + Gemini 2.5
3. **Extractor Layer** (`src/extractors/`): PDF detection and validation logic
4. **Utility Layer** (`src/utils/`): S3 upload and file management

## Key Implementation Details

### Browser Agent (`src/agents/document_extractor.py`)
- Uses browser-use with ChatGoogle LLM for autonomous navigation
- Platform-specific task prompts for different procurement sites
- Handles complex JavaScript interactions and dynamic content
- Extracts PDF URLs from agent execution results

### S3 Integration (`src/utils/s3_uploader.py`)
- Async download of PDFs using httpx
- Intelligent filename generation from URLs
- Direct S3 upload with proper content types
- Structured error handling and logging

### PDF Detection (`src/extractors/pdf_detector.py`)
- Pattern matching for PDF URLs and indicators
- URL validation and deduplication
- Support for relative and absolute PDF links

## Platform-Specific Behavior

- **California eCal**: Direct navigation to "View Event Package" sections
- **NY State**: Handles authentication flows and login requirements
- **SourceWell**: Navigates tender detail pages and document sections

## Development Notes

### Import Structure
- Use relative imports within src/ modules
- API models defined in `src/api/models.py`
- Structured logging throughout with contextual information

### Error Handling
- Comprehensive exception handling in all async operations
- Structured logging with relevant context (URLs, file counts, etc.)
- HTTP status codes for different error scenarios

### Testing
- API key validation scripts in `tests/`
- S3 connectivity verification
- Health check endpoints for monitoring

## Deployment Considerations

- Headless Chromium browser in Docker container
- Non-root user for security
- Resource limits and health checks
- Environment variable injection via docker-compose