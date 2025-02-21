import boto3
from botocore.client import Config
import os


class S3:
    def __init__(self):
        self.connection = S3.get_connection()

    def upload_public_read_file(self, source_file_path, bucket, destination_file_path):
        self.connection.upload_file(source_file_path, bucket, destination_file_path, ExtraArgs={'ACL': 'public-read'})

    @staticmethod
    def get_connection():
        print("S3_KEY:", os.getenv('S3_KEY'))
        print("S3_SECRET:", os.getenv('S3_SECRET'))
        print("S3_REGION:", os.getenv('S3_REGION'))
        print("S3_URL:", os.getenv('S3_URL'))

        connection = boto3.client(
            's3',
            aws_access_key_id=os.getenv('S3_KEY'),
            aws_secret_access_key=os.getenv('S3_SECRET'),
            region_name=os.getenv('S3_REGION'),
            config=Config(signature_version='s3v4', s3={'url': os.getenv('S3_URL')}),
        )
        return connection
