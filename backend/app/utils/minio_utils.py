
from minio import Minio
from minio.error import S3Error
from app.config import settings
import uuid
import json
import io
import hashlib
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

minio_client = Minio(
    settings.MINIO_ENDPOINT.replace("http://", "").replace("https://", ""),
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE
)

bucket_name = settings.MINIO_BUCKET_NAME
try:
    found = minio_client.bucket_exists(bucket_name)
    if not found:
        minio_client.make_bucket(bucket_name)
        logger.info(f"Bucket '{bucket_name}' created.")
    else:
        logger.info(f"Bucket '{bucket_name}' already exists.")
except S3Error as e:
    logger.error(f"Error checking/creating bucket: {e}")
    raise e

def upload_model_card_json(model_data: dict, user_uuid: str) -> str:
    """Upload the model card JSON to MinIO and return the storage URL."""
    object_name = f"model_cards/{user_uuid}/{uuid.uuid4()}.json"
    try:
        json_bytes = json.dumps(model_data).encode('utf-8')
        data_stream = io.BytesIO(json_bytes)
        data_length = len(json_bytes)

        minio_client.put_object(
            bucket_name,
            object_name,
            data=data_stream,
            length=data_length,
            content_type='application/json'
        )
        storage_url = f"{settings.MINIO_URL}/{bucket_name}/{object_name}"
        return storage_url
    except S3Error as e:
        logger.error(f"MinIO upload error: {e}")
        raise e

async def upload_to_minio(file_key: str, file_data: bytes, content_type: str = 'application/json') -> str:
    """Upload data to MinIO and return the storage URL."""
    try:
        data_stream = io.BytesIO(file_data)
        data_length = len(file_data)

        minio_client.put_object(
            bucket_name,
            file_key,
            data=data_stream,
            length=data_length,
            content_type=content_type
        )
        storage_url = f"{settings.MINIO_URL}/{bucket_name}/{file_key}"
        return storage_url
    except S3Error as e:
        logger.error(f"MinIO upload error: {e}")
        raise e

async def get_from_minio(file_key_or_url: str) -> bytes:
    """Retrieve data from MinIO by object key or full URL."""
    try:
        file_key = file_key_or_url
        if file_key.startswith('http://') or file_key.startswith('https://'):
            parts = file_key.split(f'/{bucket_name}/')
            if len(parts) > 1:
                file_key = parts[1]
            else:
                from urllib.parse import urlparse
                parsed = urlparse(file_key)
                file_key = parsed.path.lstrip('/')
                if file_key.startswith(f'{bucket_name}/'):
                    file_key = file_key[len(bucket_name)+1:]

        response = minio_client.get_object(bucket_name, file_key)
        file_data = response.read()
        response.close()
        response.release_conn()
        return file_data
    except S3Error as e:
        logger.error(f"MinIO get error: {e}")
        raise e



def compute_content_hash(content: bytes) -> str:
    """Return the hex-encoded SHA-256 hash of content."""
    return hashlib.sha256(content).hexdigest()


def generate_privacy_preserving_reference(file_key: str, content_hash: str) -> str:
    """Return a content-addressable reference that doesn't expose the raw storage path."""
    return f"sha256:{content_hash}"


async def upload_to_minio_with_hash(
    file_key: str,
    file_data: bytes,
    content_type: str = 'application/json'
) -> Tuple[str, str, str]:
    """Upload data to MinIO and return (internal_url, content_hash, privacy_reference)."""
    try:
        content_hash = compute_content_hash(file_data)

        data_stream = io.BytesIO(file_data)
        data_length = len(file_data)

        minio_client.put_object(
            bucket_name,
            file_key,
            data=data_stream,
            length=data_length,
            content_type=content_type
        )

        internal_url = f"{settings.MINIO_URL}/{bucket_name}/{file_key}"

        privacy_reference = generate_privacy_preserving_reference(file_key, content_hash)

        return (internal_url, content_hash, privacy_reference)

    except S3Error as e:
        logger.error(f"MinIO upload error: {e}")
        raise e


async def verify_content_integrity(file_key_or_url: str, expected_hash: str) -> bool:
    """Return True if stored content matches expected_hash."""
    try:
        content = await get_from_minio(file_key_or_url)
        actual_hash = compute_content_hash(content)
        return actual_hash == expected_hash
    except Exception as e:
        logger.error(f"Content integrity verification failed: {e}")
        return False


_storage_mapping = {}


def register_storage_mapping(privacy_reference: str, internal_url: str):
    """Register mapping from privacy reference to internal storage URL."""
    _storage_mapping[privacy_reference] = internal_url


def resolve_storage_location(privacy_reference: str) -> Optional[str]:
    """Resolve a privacy reference to its internal storage URL, or None."""
    return _storage_mapping.get(privacy_reference)