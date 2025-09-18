#!/usr/bin/env python3
"""
Test script to verify AWS S3 access is working correctly.
"""

import os
import boto3
from dotenv import load_dotenv
from botocore.exceptions import ClientError, NoCredentialsError

def test_s3_access():
    """Test if AWS S3 credentials are valid and bucket is accessible."""
    print("🪣 Testing AWS S3 Access...")

    # Load environment variables
    load_dotenv()

    # Check if AWS credentials exist
    access_key = os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    bucket_name = "my-solicitations"

    if not access_key:
        print("❌ ERROR: AWS_ACCESS_KEY_ID not found in environment variables")
        print("   Please add AWS_ACCESS_KEY_ID to your .env file")
        return False

    if not secret_key:
        print("❌ ERROR: AWS_SECRET_ACCESS_KEY not found in environment variables")
        print("   Please add AWS_SECRET_ACCESS_KEY to your .env file")
        return False

    print(f"✅ AWS credentials found")
    print(f"   Access Key: {access_key[:10]}...")
    print(f"   Target Bucket: {bucket_name}")

    try:
        # Initialize S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )

        # Test 1: Check if bucket exists and we can access it
        print("🧪 Testing bucket access...")
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            print(f"✅ Bucket '{bucket_name}' is accessible")
        except ClientError as e:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                print(f"❌ ERROR: Bucket '{bucket_name}' does not exist")
                print("   Please create the bucket in AWS Console")
                return False
            elif error_code == 403:
                print(f"❌ ERROR: Access denied to bucket '{bucket_name}'")
                print("   Please check bucket permissions")
                return False
            else:
                raise

        # Test 2: Upload hello_world.txt to testing/ prefix
        print("🧪 Testing file upload...")
        test_content = "Hello World from S3 test!"
        test_key = "testing/hello_world.txt"

        s3_client.put_object(
            Bucket=bucket_name,
            Key=test_key,
            Body=test_content.encode('utf-8'),
            ContentType='text/plain'
        )
        print(f"✅ File uploaded: s3://{bucket_name}/{test_key}")

        # Test 3: List files in testing/ prefix
        print("🧪 Testing bucket listing...")
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix="testing/",
            MaxKeys=10
        )

        if 'Contents' in response:
            print(f"✅ Found {len(response['Contents'])} files in testing/ prefix:")
            for obj in response['Contents']:
                print(f"   - {obj['Key']} ({obj['Size']} bytes)")
        else:
            print("✅ No files found in testing/ prefix")

        print("🎉 S3 access is working correctly!")
        return True

    except NoCredentialsError:
        print("❌ ERROR: Invalid AWS credentials")
        print("   Please check your AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
        return False

    except ClientError as e:
        print(f"❌ ERROR: AWS S3 operation failed")
        print(f"   Error details: {e}")
        return False

    except Exception as e:
        print(f"❌ ERROR: Unexpected error occurred")
        print(f"   Error details: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_s3_access()
    exit(0 if success else 1)

    # response from running file:
    # Testing AWS S3 Access...
    # AWS credentials found
    # Access Key: AKIAQ3EGQK...
    # Target Bucket: my-solicitations
    # Testing bucket access...
    # Bucket 'my-solicitations' is accessible
    # Testing file upload...
    # File uploaded: s3://my-solicitations/testing/hello_world.txt
    # Testing bucket listing...
    # Found 1 files in testing/ prefix:
    # testing/hello_world.txt (25 bytes)
    # S3 access is working correctly!