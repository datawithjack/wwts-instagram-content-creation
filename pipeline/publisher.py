"""Instagram publishing via Cloudflare R2 + Meta Graph API."""
import os
import time
import uuid

import boto3
import requests

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


def _get_r2_client():
    account_id = os.environ["R2_ACCOUNT_ID"]
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def upload_to_r2(file_path: str) -> str:
    """Upload image to Cloudflare R2 and return its public URL."""
    bucket = os.environ["R2_BUCKET_NAME"]
    public_url = os.environ["R2_PUBLIC_URL"]
    ext = os.path.splitext(file_path)[1]
    key = f"{uuid.uuid4().hex}{ext}"

    client = _get_r2_client()
    client.upload_file(
        Filename=file_path,
        Bucket=bucket,
        Key=key,
        ExtraArgs={"ContentType": f"image/{ext.lstrip('.')}"},
    )
    return f"{public_url}/{key}"


def delete_from_r2(blob_url: str) -> None:
    """Delete an object from R2 by its public URL."""
    bucket = os.environ["R2_BUCKET_NAME"]
    public_url = os.environ["R2_PUBLIC_URL"]
    key = blob_url.replace(f"{public_url}/", "")

    client = _get_r2_client()
    client.delete_object(Bucket=bucket, Key=key)


def create_container(image_url: str, caption: str) -> str:
    """Create a media container on Instagram. Returns container ID."""
    account_id = os.environ["META_INSTAGRAM_ACCOUNT_ID"]
    token = os.environ["META_ACCESS_TOKEN"]

    resp = requests.post(
        f"{GRAPH_API_BASE}/{account_id}/media",
        params={
            "image_url": image_url,
            "caption": caption,
            "access_token": token,
        },
    )
    resp.raise_for_status()
    return resp.json()["id"]


def check_container_status(container_id: str) -> str:
    """Check the status of a media container. Returns status_code string."""
    token = os.environ["META_ACCESS_TOKEN"]

    resp = requests.get(
        f"{GRAPH_API_BASE}/{container_id}",
        params={
            "fields": "status_code",
            "access_token": token,
        },
    )
    resp.raise_for_status()
    return resp.json()["status_code"]


def wait_for_container(container_id: str, max_attempts: int = 30, delay: float = 5.0) -> None:
    """Poll container status until FINISHED. Raises on ERROR or timeout."""
    for _ in range(max_attempts):
        status = check_container_status(container_id)
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"Container {container_id} failed with status ERROR")
        time.sleep(delay)
    raise TimeoutError(
        f"Container {container_id} not ready after {max_attempts} attempts"
    )


def publish_container(container_id: str) -> str:
    """Publish a ready container. Returns media ID."""
    account_id = os.environ["META_INSTAGRAM_ACCOUNT_ID"]
    token = os.environ["META_ACCESS_TOKEN"]

    resp = requests.post(
        f"{GRAPH_API_BASE}/{account_id}/media_publish",
        params={
            "creation_id": container_id,
            "access_token": token,
        },
    )
    resp.raise_for_status()
    return resp.json()["id"]


def publish(file_path: str, caption: str) -> dict:
    """Full publish flow: upload to R2 -> create container -> wait -> publish -> cleanup."""
    image_url = upload_to_r2(file_path)
    try:
        container_id = create_container(image_url, caption)
        wait_for_container(container_id)
        media_id = publish_container(container_id)
    except Exception:
        delete_from_r2(image_url)
        raise
    delete_from_r2(image_url)
    return {"media_id": media_id, "image_url": image_url}
