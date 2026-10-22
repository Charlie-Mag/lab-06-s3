#!/usr/bin/env python3
"""Download books and upload them to a public S3 bucket."""
import json
import logging
import os
import sys
import time

import boto3
import requests
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# Create one S3 client for all functions to use.
s3 = boto3.client("s3", region_name="us-east-1")


def parse_args():
    """Read the three command-line arguments."""
    if len(sys.argv) < 4:
        log.error(
            "Usage: stage_books.py <book_urls.txt> <index.html> <bucket>"
        )
        sys.exit(1)

    list_file = sys.argv[1]
    index_path = sys.argv[2]
    bucket = sys.argv[3]

    return list_file, index_path, bucket

def download_books(list_file, dest_dir):
    """Download the books and return their local file paths."""
    os.makedirs(dest_dir, exist_ok=True)
    file_paths = []

    with open(list_file, "r") as f:
        for line in f:
            url = line.strip()

            # Skip blank lines.
            if url == "":
                continue

            filename = url.split("/")[-1]
            path = os.path.join(dest_dir, filename)

            # Reuse books that were already downloaded.
            if os.path.exists(path):
                log.info(f"Already downloaded: {path}")
                file_paths.append(path)
                continue

            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()

                with open(path, "wb") as book:
                    book.write(response.content)

                file_paths.append(path)
                log.info(f"Downloaded: {path}")
            except requests.RequestException as e:
                log.error(f"Error downloading {url}: {e}")

            time.sleep(1)

    return file_paths

def create_bucket(bucket):
    """Check for an existing bucket or create a new one."""
    try:
        s3.head_bucket(Bucket=bucket)
        log.info(f"Bucket already exists: {bucket}")
        return True
    except ClientError as e:
        error_code = e.response["Error"]["Code"]

        # Only try creating a bucket if it was not found.
        if error_code != "404":
            log.error(f"Error checking bucket {bucket}: {e}")
            return False

    try:
        s3.create_bucket(Bucket=bucket)
        log.info(f"Created bucket: {bucket}")
        return True
    except ClientError as e:
        log.error(f"Error creating bucket {bucket}: {e}")
        return False

def make_public(bucket):
    """Allow anyone to read objects in the bucket."""
    try:
        s3.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False,
            },
        )

        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{bucket}/*",
                }
            ],
        }

        s3.put_bucket_policy(
            Bucket=bucket,
            Policy=json.dumps(policy),
        )

        log.info(f"Bucket is publicly readable: {bucket}")
        return True
    except ClientError as e:
        log.error(f"Error making bucket public {bucket}: {e}")
        return False

def upload_files(bucket, file_paths):
    """Upload the books and return the number uploaded."""
    uploaded = 0

    for path in file_paths:
        key = os.path.basename(path)

        try:
            with open(path, "rb") as f:
                s3.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=f,
                    ContentType="text/plain; charset=utf-8",
                )

            log.info(f"Uploaded {path} to s3://{bucket}/{key}")
            uploaded = uploaded + 1
        except FileNotFoundError:
            log.error(f"Local file not found: {path}")
        except ClientError as e:
            log.error(f"Error uploading {path}: {e}")

    return uploaded

def upload_index(bucket, index_path):
    """Upload the collection's index page."""
    try:
        with open(index_path, "rb") as f:
            s3.put_object(
                Bucket=bucket,
                Key="index.html",
                Body=f,
                ContentType="text/html",
            )

        log.info(f"Uploaded index page to s3://{bucket}/index.html")
        return True
    except FileNotFoundError:
        log.error(f"Local file not found: {index_path}")
        return False
    except ClientError as e:
        log.error(f"Error uploading index page: {e}")
        return False

def main():
    """Download the books and publish the collection."""
    list_file, index_path, bucket = parse_args()

    file_paths = download_books(list_file, "books")

    if len(file_paths) == 0:
        log.error("No books are available to upload.")
        sys.exit(1)

    if not create_bucket(bucket):
        sys.exit(1)

    if not make_public(bucket):
        sys.exit(1)

    uploaded = upload_files(bucket, file_paths)
    index_uploaded = upload_index(bucket, index_path)

    if uploaded == len(file_paths) and index_uploaded:
        log.info(f"Success! Uploaded {uploaded} books and the index page.")
        log.info(f"https://{bucket}.s3.amazonaws.com/index.html")
    else:
        log.error(f"Upload incomplete: {uploaded} of {len(file_paths)} books.")
        log.error(f"Index page uploaded: {index_uploaded}")
        log.info(f"Index page URL: https://{bucket}.s3.amazonaws.com/index.html")
        sys.exit(1)


if __name__ == "__main__":
    main()
