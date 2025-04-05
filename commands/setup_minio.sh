#!/bin/sh

# MinIO alias setup
mc alias set minio http://${MINIO_HOST}:9000 ${MINIO_ROOT_USER} ${MINIO_ROOT_PASSWORD}

# Check if the bucket exists
if ! mc ls minio/${MINIO_STORAGE} > /dev/null 2>&1; then
  echo "Bucket ${MINIO_STORAGE} does not exist, creating..."
  mc mb minio/${MINIO_STORAGE}
  echo "Bucket ${MINIO_STORAGE} created!"
else
  echo "Bucket ${MINIO_STORAGE} already exists, skipping creation."
fi

