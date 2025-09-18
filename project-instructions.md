# AI Engineer Home Task - Agentic Document

# Extraction API

## Objective

Build a containerized API service using Browser Use + Gemini 2.5+ that accepts URLs and
autonomously downloads solicitation PDFs to S3 storage.

## API Requirements

**Input:** POST /extract

**Output:** List of uploaded S3 file paths

## Test URLs (All Platform Types)

**California eCal (No Auth):**

- https://caleprocure.ca.gov/event/0850/0000036230 (view event package
- https://caleprocure.ca.gov/event/2660/07A6065 (view event package)
- https://caleprocure.ca.gov/event/75021/0000035944 (view event package)

**NY State (Auth Required - credentials provided):**

**SourceWell (No Auth):**
https://proportal.sourcewell-mn.gov/Module/Tenders/en/Tender/Detail/68914ced-5e07-409d-
b301-b10001e4bbb0/#Document

```
{
"url": "https://caleprocure.ca.gov/event/0850/0000036230",
"s3_bucket": "my-solicitations",
"s3_prefix": "ecal/event-036230/"
}
```
```
{
"status": "success",
"files": [
"s3://my-solicitations/ecal/event-036230/solicitation.pdf",
"s3://my-solicitations/ecal/event-036230/amendments.pdf"
]
}
```
```
https://www.nyscr.ny.gov/ (browse and select any 2 solicitations)
```

https://proportal.sourcewell-mn.gov/Module/Tenders/en/Tender/Detail/88c9616c-5685-4cae-
b7fa-9c8ad726c38d/#Document

https://proportal.sourcewell-mn.gov/Module/Tenders/en/Tender/Detail/321c8f90-b43d-46ae-
a8e4-41ac7587bc19/#Document

## Technical Stack

## Key Features

Most of the below items can be handled by browser use

## Configuration (Environment Variables)

## Docker Deployment

## Deliverables

## Success Criteria

```
Framework: Browser Use with Gemini 2.5+ integration
API: FastAPI
Storage: AWS S3 SDK (boto3)
Container: Docker with headless browser support
```
1. **Autonomous Navigation:** Agent handles authentication, JavaScript, dynamic content
2. **Document Discovery:** Intelligently finds and downloads all PDF attachments
3. **S3 Integration:** Direct upload to configurable S3 buckets with proper naming
4. **Error Handling:** Retry logic, timeout management, detailed logging

```
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
GEMINI_API_KEY=your_gemini_key
```
```
docker-compose up -d
curl -X POST http://localhost:8000/extract \
-H "Content-Type: application/json" \
-d '{"url": "https://caleprocure.ca.gov/event/0850/0000036230",
"s3_bucket": "test-bucket", "s3_prefix": "test/"}'
```
1. **Source Code** with FastAPI/Flask application
2. **Dockerfile + docker-compose.yml** for one-command deployment
3. **README** with setup and usage instructions
4. **Test Results** showing successful S3 uploads from all platform types


## Time Estimate: 4-6 hours

## Submission

GitHub repository with working Docker setup and demonstration of S3 uploads from test
URLs.

```
✅ Containerized API accepts URL + S3 parameters
✅ Successfully extracts PDFs from all three platform types
✅ Uploads files to S3 with proper naming/organization
✅ Handles authentication automatically (NYSCR)
✅ Returns accurate S3 file paths in API response
```

