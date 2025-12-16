import os
import json
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
    index_type = os.getenv("S3V_INDEX_TYPE", "flat")
    k = _env_int("S3V_K", 5)
    filter_kind = os.getenv("S3V_FILTER_KIND")
    filter_json = (os.getenv("S3V_FILTER_JSON") or "").strip()
    cleanup = (os.getenv("S3V_CLEANUP") or "").strip().lower() in {"1", "true", "yes"}
    min_similarity = os.getenv("S3V_MIN_SIMILARITY")
    min_similarity_f = float(min_similarity) if min_similarity else None

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
    print(f"Type: {index_type}")
    print(f"K: {k}")
    if filter_kind:
        print(f"Filter kind: {filter_kind}")
    if filter_json:
        print(f"Filter JSON: {filter_json}")
    if min_similarity_f is not None:
        print(f"Min similarity: {min_similarity_f}")
    print(f"Cleanup: {cleanup}")
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
    print("1) create_index")
    try:
        res = s3v.create_index(
            vectorBucketName=bucket,
            indexName=index,
            dataType=data_type,
            dimension=dimension,
            distanceMetric=metric,
        )
        print("Created:", res)
    except ClientError as e:
        code = (e.response or {}).get("Error", {}).get("Code", "")
        if code.lower() in {"resourcealreadyexistsexception", "conflictexception", "alreadyexists"}:
            print("Already exists; continuing.")
        else:
            raise
    except BotoCoreError:
        raise

    print("")
    print("2) put_vectors")
    rng = np.random.default_rng(seed=int(time.time()))
    v1 = rng.random(dimension, dtype=np.float32).tolist()
    v2 = rng.random(dimension, dtype=np.float32).tolist()
    suffix = uuid.uuid4().hex[:8]
    items = [
        {
            "key": f"smoke-1-{suffix}",
            "data": {"float32": v1},
            "metadata": {"kind": "smoke", "n": "1"},
        },
        {
            "key": f"smoke-2-{suffix}",
            "data": {"float32": v2},
            "metadata": {"kind": "smoke", "n": "2"},
        },
    ]

    res = s3v.put_vectors(vectorBucketName=bucket, indexName=index, vectors=items)
    print("Put:", res)

    print("")
    print("3) query_vectors")
    query = rng.random(dimension, dtype=np.float32).tolist()
    query_args = dict(
        vectorBucketName=bucket,
        indexName=index,
        topK=k,
        queryVector={"float32": query},
        returnMetadata=True,
        returnDistance=True,
    )
    if filter_json:
        try:
            query_args["filter"] = json.loads(filter_json)
        except json.JSONDecodeError as e:
            raise SystemExit(f"Invalid JSON in S3V_FILTER_JSON: {e}") from e
    elif filter_kind:
        query_args["filter"] = {"kind": filter_kind}

    res = s3v.query_vectors(**query_args)
    vectors = list(res.get("vectors") or [])
    if min_similarity_f is not None:
        if res.get("distanceMetric") != "cosine":
            raise SystemExit("S3V_MIN_SIMILARITY currently only supported when distanceMetric=cosine")
        vectors = [v for v in vectors if (1.0 - float(v.get("distance"))) >= min_similarity_f]
        res = dict(res)
        res["vectors"] = vectors
    print("Query:", res)

    if filter_kind:
        bad = [
            v.get("key")
            for v in (res.get("vectors") or [])
            if (v.get("metadata") or {}).get("kind") != filter_kind
        ]
        if bad:
            raise SystemExit(f"Filter validation failed; non-matching vectors returned: {bad}")

    if cleanup:
        print("")
        print("4) delete_vectors (cleanup)")
        keys = [v["key"] for v in items]
        res = s3v.delete_vectors(vectorBucketName=bucket, indexName=index, keys=keys)
        print("Deleted:", res)


if __name__ == "__main__":
    main()
