import boto3
import os
import uuid
from botocore.exceptions import ClientError


def create_s3_bucket(s3_client, bucket_name, region="us-east-2"):
    """Create an S3 bucket in the specified region."""
    try:
        s3_client.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={"LocationConstraint": region}
        )
        print(f"Bucket '{bucket_name}' created successfully in region '{region}'.")
        return True
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "BucketAlreadyOwnedByYou":
            print(f"Bucket '{bucket_name}' already exists and is owned by you.")
            return True
        elif error_code == "BucketAlreadyExists":
            print(f"Bucket '{bucket_name}' already exists and is owned by someone else.")
        else:
            print(f"Error creating bucket '{bucket_name}': {e}")
        return False


def upload_txt_files_with_uuid(s3_client, bucket_name, local_directory):
    """Upload only top-level TXT files using UUIDs as S3 object keys."""
    try:
        if not os.path.isdir(local_directory):
            print(f"Directory '{local_directory}' does not exist.")
            return False

        for file in os.listdir(local_directory):
            full_path = os.path.join(local_directory, file)
            if os.path.isfile(full_path) and file.lower().endswith(".txt"):
                unique_id = str(uuid.uuid4())
                s3_key = f"{unique_id}.txt"

                try:
                    s3_client.upload_file(
                        Filename=full_path,
                        Bucket=bucket_name,
                        Key=s3_key,
                        ExtraArgs={"ContentType": "text/plain"}
                    )
                    print(f"Uploaded '{file}' as '{s3_key}' to 's3://{bucket_name}/{s3_key}'")
                except ClientError as e:
                    print(f"Error uploading '{file}': {e}")
                    return False
        return True
    except Exception as e:
        print(f"Error processing directory '{local_directory}': {e}")
        return False


def main():
    # Configuration
    bucket_name = "my-unique-bucket-2025123243"  # Ensure this is globally unique
    region = "us-east-2"
    local_directory = os.path.join(os.getcwd(), "sample_pdfs")  # Only top-level files in this folder

    # Initialize S3 client
    try:
        s3_client = boto3.client("s3", region_name=region)
    except Exception as e:
        print(f"Error initializing S3 client: {e}")
        return

    # Create bucket if needed
    if not create_s3_bucket(s3_client, bucket_name, region):
        return

    # Upload TXT files using UUIDs
    if upload_txt_files_with_uuid(s3_client, bucket_name, local_directory):
        print("All top-level TXT files uploaded successfully using UUIDs.")
    else:
        print("Failed to upload some or all TXT files.")


if __name__ == "__main__":
    main()