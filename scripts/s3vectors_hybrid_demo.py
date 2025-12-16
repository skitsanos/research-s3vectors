import os
import time
import uuid

import boto3
import numpy as np
from botocore.exceptions import BotoCoreError, ClientError, UnknownServiceError


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing required env var: {name}")
    return value


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


def main() -> None:
    bucket = _require_env("S3V_BUCKET")
    index = _require_env("S3V_INDEX")
    dimension = _env_int("S3V_DIMENSION", 1536)
    metric = os.getenv("S3V_METRIC", "cosine")
    data_type = os.getenv("S3V_DATA_TYPE", "float32")
    k = _env_int("S3V_K", 20)

    session = boto3.Session()
    region = session.region_name or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"

    try:
        s3v = session.client("s3vectors", region_name=region)
    except UnknownServiceError as e:
        raise SystemExit(
            "boto3/botocore does not recognize 's3vectors' yet. "
            "Upgrade boto3/botocore to a version that includes Amazon S3 Vectors."
        ) from e

    print("Config")
    print(f"Bucket: {bucket}")
    print(f"Index: {index}")
    print(f"Region: {region}")
    print(f"Dimension: {dimension}")
    print(f"Metric: {metric}")
    print(f"DataType: {data_type}")
    print(f"K: {k}")
    print("")

    print("0) ensure vector bucket")
    try:
        s3v.get_vector_bucket(vectorBucketName=bucket)
        print("Vector bucket exists; continuing.")
    except ClientError as e:
        code = (e.response or {}).get("Error", {}).get("Code", "")
        if code in {"NotFoundException", "ResourceNotFoundException", "NoSuchBucket"}:
            res = s3v.create_vector_bucket(vectorBucketName=bucket)
            print("Created vector bucket:", res)
        else:
            raise

    print("")
    print("1) ensure index")
    try:
        s3v.get_index(vectorBucketName=bucket, indexName=index)
        print("Index exists; continuing.")
    except ClientError as e:
        code = (e.response or {}).get("Error", {}).get("Code", "")
        if code in {"NotFoundException", "ResourceNotFoundException"}:
            res = s3v.create_index(
                vectorBucketName=bucket,
                indexName=index,
                dataType=data_type,
                dimension=dimension,
                distanceMetric=metric,
            )
            print("Created index:", res)
        else:
            raise

    rng = np.random.default_rng(seed=int(time.time()))
    suffix = uuid.uuid4().hex[:8]
    vectors = [
        {
            "key": f"hybrid-apples-nl-{suffix}",
            "data": {"float32": rng.random(dimension, dtype=np.float32).tolist()},
            "metadata": {"category": "apples", "origin": "NL"},
        },
        {
            "key": f"hybrid-apples-de-{suffix}",
            "data": {"float32": rng.random(dimension, dtype=np.float32).tolist()},
            "metadata": {"category": "apples", "origin": "DE"},
        },
        {
            "key": f"hybrid-bananas-ec-{suffix}",
            "data": {"float32": rng.random(dimension, dtype=np.float32).tolist()},
            "metadata": {"category": "bananas", "origin": "EC"},
        },
    ]

    keys = [v["key"] for v in vectors]
    try:
        print("")
        print("2) put_vectors (category/origin metadata)")
        s3v.put_vectors(vectorBucketName=bucket, indexName=index, vectors=vectors)
        print("Inserted keys:", keys)

        print("")
        print("3) query_vectors (vector + metadata filter)")
        query = rng.random(dimension, dtype=np.float32).tolist()
        query_filter = {
            "$and": [
                {"category": {"$eq": "apples"}},
                {"origin": {"$in": ["NL", "DE"]}},
            ]
        }
        res = s3v.query_vectors(
            vectorBucketName=bucket,
            indexName=index,
            topK=k,
            queryVector={"float32": query},
            filter=query_filter,
            returnMetadata=True,
            returnDistance=True,
        )
        print("Filter:", query_filter)
        print("Results:", res)
    finally:
        print("")
        print("4) delete_vectors (cleanup)")
        s3v.delete_vectors(vectorBucketName=bucket, indexName=index, keys=keys)
        print("Deleted keys:", keys)


if __name__ == "__main__":
    try:
        main()
    except (BotoCoreError, ClientError) as e:
        raise SystemExit(str(e)) from e
