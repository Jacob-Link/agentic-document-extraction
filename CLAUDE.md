# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an agentic document extraction API service that autonomously downloads solicitation PDFs from government procurement websites and uploads them to S3 storage. The service uses Browser Use with Gemini 2.5+ integration to handle complex web navigation, authentication, and document discovery.

## Technology Stack

- **Framework**: Browser Use with Gemini 2.5+ integration
- **API**: FastAPI
- **Storage**: AWS S3 SDK (boto3)
- **Container**: Docker with headless browser support

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

```
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
GEMINI_API_KEY=your_gemini_key
```

## Development Commands

```bash
# Start the service
docker-compose up -d

# Test the API
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -d '{"url": "https://caleprocure.ca.gov/event/0850/0000036230", "s3_bucket": "test-bucket", "s3_prefix": "test/"}'
```

## Key Requirements

1. **Autonomous Navigation**: Handle authentication, JavaScript, and dynamic content automatically
2. **Document Discovery**: Intelligently find and download all PDF attachments from procurement pages
3. **S3 Integration**: Upload files to configurable S3 buckets with proper naming conventions
4. **Error Handling**: Implement retry logic, timeout management, and detailed logging
5. **Multi-Platform Support**: Handle different procurement website architectures and authentication methods

## Success Criteria

- ✅ Containerized API accepts URL + S3 parameters
- ✅ Successfully extracts PDFs from all three platform types
- ✅ Uploads files to S3 with proper naming/organization
- ✅ Handles authentication automatically (NYSCR)
- ✅ Returns accurate S3 file paths in API response