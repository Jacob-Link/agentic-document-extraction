""" this is used when env var DEBUG == True, just lists the content of a bucket """

import os
from dotenv import load_dotenv
from typing import List, Dict, Any
import structlog
import boto3
from botocore.exceptions import ClientError

logger = structlog.get_logger(__name__)

class S3DummyClient:
    """Dummy S3 client for DEBUG mode that simulates bucket operations."""

    def __init__(self):
        load_dotenv()
        self.bucket_name = os.getenv("S3_BUCKET_NAME", "default-bucket")

    async def list_bucket_contents(self, bucket: str = None, prefix: str = "") -> List[str]:
        """
        Make real boto3 call to list bucket contents.
        Returns actual file names from my-solicitations bucket.
        """
        bucket = bucket or "my-solicitations"

        logger.info("DEBUG: Listing bucket contents with real boto3 call", bucket=bucket, prefix=prefix)

        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                region_name=os.getenv('AWS_REGION', 'us-east-1')
            )

            response = s3_client.list_objects_v2(
                Bucket=bucket,
                Prefix=prefix
            )

            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    files.append(obj['Key'])

            logger.info("DEBUG: Real S3 bucket contents listed", file_count=len(files), files=files)
            return files

        except ClientError as e:
            logger.error("DEBUG: Failed to list S3 bucket contents", error=str(e))
            # Return empty list on error
            return []

    async def upload_file(self, file_path: str, bucket: str, key: str) -> str:
        """
        Simulate file upload to S3.
        Returns the S3 URI without actually uploading.
        """
        s3_uri = f"s3://{bucket}/{key}"
        logger.info("DEBUG: Simulating file upload", local_path=file_path, s3_uri=s3_uri)
        return s3_uri

    async def download_file(self, url: str, local_path: str) -> bool:
        """
        Simulate file download.
        Returns True without actually downloading.
        """
        logger.info("DEBUG: Simulating file download", url=url, local_path=local_path)
        return True