#!/bin/bash
set -euo pipefail

# Accept three positional arguments.
if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <book-url> <bucket-name> <expiration-seconds>"
    exit 1
fi

# Give the arguments clear names.
URL="$1"
BUCKET="$2"
EXPIRATION="$3"

# Get the file name from the URL.
FILENAME="$(basename "$URL")"

# Download the book into the books folder.
mkdir -p books
curl --fail --location "$URL" --output "books/$FILENAME"

# Create the bucket if it does not already exist.
if aws s3 ls "s3://$BUCKET" > /dev/null 2>&1; then
    echo "Bucket already exists: $BUCKET"
else
    aws s3 mb "s3://$BUCKET" --region us-east-1
fi

# Upload the book without changing public access settings.
aws s3 cp "books/$FILENAME" "s3://$BUCKET/$FILENAME" \
    --content-type "text/plain; charset=utf-8"

# Print a temporary link to the private book.
aws s3 presign "s3://$BUCKET/$FILENAME" \
    --expires-in "$EXPIRATION" \
    --region us-east-1
