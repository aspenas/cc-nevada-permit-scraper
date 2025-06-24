import os
from dotenv import load_dotenv


def fetch_and_set_aws_secret(secret_name: str, region_name: str = None):
    """
    Fetch secrets from AWS Secrets Manager and set them as environment variables.
    """
    try:
        import boto3
        import json as _json
        session = boto3.session.Session()
        if region_name is None:
            region_name = session.region_name or 'us-west-2'
        client = session.client(
            service_name='secretsmanager',
            region_name=region_name
        )
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret = get_secret_value_response['SecretString']
        secret_dict = _json.loads(secret)
        for k, v in secret_dict.items():
            os.environ[k] = v
    except Exception as e:
        import logging
        logging.warning(f"Could not fetch secret from AWS: {e}")


def get_database_url():
    """
    Get the database URL from environment or AWS Secrets Manager.
    Returns the database URL as a string.
    """
    # Try to load from .env first
    load_dotenv()
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        return db_url

    # If not found, try AWS Secrets Manager
    secret_name = os.getenv('DB_SECRET_NAME', 'clark-county-permit-db')
    region_name = os.getenv('AWS_REGION', 'us-west-2')
    fetch_and_set_aws_secret(secret_name, region_name)
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        return db_url

    raise RuntimeError('DATABASE_URL not found in environment or AWS Secrets Manager.') 