import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing required env var: {name}")
    return value


def main() -> None:
    bucket = _require_env("S3V_BUCKET")

    session = boto3.Session()
    region = session.region_name or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"

    try:
        sts = session.client("sts", region_name=region)
        ident = sts.get_caller_identity()
        print("STS OK")
        print(f"Account: {ident.get('Account')}")
        print(f"Arn: {ident.get('Arn')}")
    except (BotoCoreError, ClientError) as e:
        raise SystemExit(f"STS call failed: {e}") from e

    try:
        s3 = session.client("s3", region_name=region)
        s3.head_bucket(Bucket=bucket)
        print("S3 OK")
        print(f"Bucket: {bucket}")
        print(f"Region: {region}")
    except ClientError as e:
        code = (e.response or {}).get("Error", {}).get("Code")
        raise SystemExit(f"S3 head_bucket failed for {bucket} ({code}): {e}") from e
    except BotoCoreError as e:
        raise SystemExit(f"S3 head_bucket failed for {bucket}: {e}") from e


if __name__ == "__main__":
    main()
