import os
import boto3
import json
import random
import string
from botocore.exceptions import ClientError


def lambda_handler(event, context):
    secret_arn = os.environ["DB_SECRET_ARN"]
    db_instance_id = os.environ["DB_INSTANCE_ID"]
    region = os.environ.get("AWS_REGION", "us-west-2")

    secrets_client = boto3.client("secretsmanager", region_name=region)
    rds_client = boto3.client("rds", region_name=region)

    # Fetch current secret
    secret = secrets_client.get_secret_value(SecretId=secret_arn)
    secret_dict = json.loads(secret["SecretString"])

    # Generate new password
    new_password = ''.join(
        random.choices(
            string.ascii_letters + string.digits + string.punctuation, k=16
        )
    )

    # Update RDS instance password
    try:
        rds_client.modify_db_instance(
            DBInstanceIdentifier=db_instance_id,
            MasterUserPassword=new_password,
            ApplyImmediately=True
        )
    except ClientError as e:
        print(f"Failed to update RDS password: {e}")
        raise

    # Update secret in Secrets Manager
    secret_dict["password"] = new_password
    secrets_client.put_secret_value(
        SecretId=secret_arn,
        SecretString=json.dumps(secret_dict)
    )

    return {"status": "success"} 