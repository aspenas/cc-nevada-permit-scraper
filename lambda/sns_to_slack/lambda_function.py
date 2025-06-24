import os
import json
import boto3
import urllib.request

def lambda_handler(event, context):
    secret_name = os.environ["SLACK_SECRET_NAME"]
    region_name = os.environ["AWS_REGION"]
    
    # Fetch Slack webhook from Secrets Manager
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)
    get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    webhook_url = get_secret_value_response['SecretString']
    
    # Parse SNS message
    for record in event["Records"]:
        sns = record["Sns"]
        message = sns["Message"]
        subject = sns.get("Subject", "Permit Scraper Alert")
        slack_data = {
            "text": f"*{subject}*\n{message}"
        }
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(slack_data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        try:
            with urllib.request.urlopen(req) as response:
                response.read()
        except Exception as e:
            print(f"Error posting to Slack: {e}")
    return {"status": "ok"} 