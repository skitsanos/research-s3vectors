# research-s3vectors

Practical, runnable Python examples for Amazon S3 Vectors using `boto3`, driven by `Taskfile` tasks.

This repo currently covers:
- Verifying AWS credentials (STS + access to the configured vector bucket)
- Creating a vector bucket and index (if missing)
- Inserting vectors (`PutVectors`)
- Querying similar vectors (`QueryVectors`)
- Metadata filtering (`filter` using `$eq`, `$in`, `$and`, etc.)
- Cleanup (`DeleteVectors`)

## Requirements

- Python 3.10+
- A configured AWS identity with permissions for Amazon S3 Vectors in your region
- `task` CLI installed (Taskfile runner)

## Setup

1) Create venv + install deps:

```bash
task install
```

2) Create `.env` from the example and fill values:

```bash
cp .env.example .env
```

## Environment variables

The Taskfiles load `.env` automatically.

### AWS auth (pick one)

- Recommended (supports SSO and shared config):
  - `AWS_PROFILE`
  - `AWS_REGION`
  - `AWS_SDK_LOAD_CONFIG=1`
- Or static keys:
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`
  - `AWS_SESSION_TOKEN` (only if using temporary creds)

### S3 Vectors config

- `S3V_BUCKET` — vector bucket name
- `S3V_INDEX` — vector index name
- `S3V_DIMENSION` — embedding dimension (e.g. `1536`)
- `S3V_DATA_TYPE` — currently `float32`
- `S3V_METRIC` — `cosine` or `euclidean` (depends on your installed `botocore` model)
- `S3V_K` — top-k results for queries

## What we observed about the SDK API shape

The examples in this repo use the API shape exposed by your installed `boto3/botocore` model for `s3vectors`:

- Create vector bucket: `create_vector_bucket(vectorBucketName=...)`
- Create index: `create_index(vectorBucketName=..., indexName=..., dataType='float32', dimension=..., distanceMetric='cosine'|'euclidean')`
- Put vectors: `put_vectors(vectorBucketName=..., indexName=..., vectors=[{'key':..., 'data':{'float32':[...]}, 'metadata':{...}}])`
- Query: `query_vectors(..., topK=..., queryVector={'float32':[...]}, filter=..., returnMetadata=True, returnDistance=True)`
- Delete: `delete_vectors(..., keys=[...])`

If you find blog/docs snippets using names like `create_vector_index` or `search`, map them to the operations above.

## Tasks (recommended way to run)

### Check AWS credentials + bucket access

```bash
task app:check-aws-credentials
```

Runs `scripts/check_aws_credentials.py`:
- `sts.get_caller_identity()`
- `s3.head_bucket(Bucket=$S3V_BUCKET)` (verifies you can reach the bucket name you configured)

### Smoke test (create bucket/index, put, query)

```bash
task app:s3vectors-smoke
```

Runs `scripts/s3vectors_smoke.py`:
- Ensures vector bucket exists
- Creates index if missing
- Inserts 2 random vectors
- Queries `topK=$S3V_K`

Optional env overrides for the smoke script:
- `S3V_FILTER_JSON` — metadata filter JSON (e.g. `{"kind":{"$in":["smoke"]}}`)
- `S3V_MIN_SIMILARITY` — client-side threshold for cosine only (`similarity = 1 - distance`)
- `S3V_CLEANUP=true` — deletes the vectors inserted by the script

### Metadata filter smoke test (uses `$in` and cleans up)

```bash
task app:s3vectors-smoke-filter
```

### Hybrid demo: category/origin filter (with cleanup)

```bash
task app:s3vectors-hybrid-demo
```

Runs `scripts/s3vectors_hybrid_demo.py`:
- Inserts vectors with metadata like `{"category":"apples","origin":"NL"}` etc.
- Queries with a compound filter:

```json
{
  "$and": [
    {"category": {"$eq": "apples"}},
    {"origin": {"$in": ["NL", "DE"]}}
  ]
}
```

- Deletes the inserted vectors even if the query fails

## Notes

- `.env` is ignored by git, but treat it as sensitive (AWS/OpenAI keys, etc.). Prefer using `AWS_PROFILE`/SSO instead of long-lived static keys.
