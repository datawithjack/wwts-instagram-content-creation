"""Instagram publishing via Cloudflare R2 + Meta Graph API."""
import os
import time
import uuid

import boto3
import requests

GRAPH_API_BASE = "https://graph.facebook.com/v22.0"


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
    """Upload file to Cloudflare R2 and return its public URL."""
    bucket = os.environ["R2_BUCKET_NAME"]
    public_url = os.environ["R2_PUBLIC_URL"]
    ext = os.path.splitext(file_path)[1].lstrip(".")
    key = f"{uuid.uuid4().hex}.{ext}"

    content_types = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "mp4": "video/mp4",
        "webm": "video/webm",
    }
    content_type = content_types.get(ext, f"application/octet-stream")

    client = _get_r2_client()
    client.upload_file(
        Filename=file_path,
        Bucket=bucket,
        Key=key,
        ExtraArgs={"ContentType": content_type},
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
    """Create an image media container on Instagram. Returns container ID."""
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


def create_reels_container(video_url: str, caption: str) -> str:
    """Create a Reels media container on Instagram. Returns container ID."""
    account_id = os.environ["META_INSTAGRAM_ACCOUNT_ID"]
    token = os.environ["META_ACCESS_TOKEN"]

    resp = requests.post(
        f"{GRAPH_API_BASE}/{account_id}/media",
        params={
            "media_type": "REELS",
            "video_url": video_url,
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


def publish_container(
    container_id: str, max_retries: int = 3, retry_delay: float = 60.0
) -> str:
    """Publish a ready container. Returns media ID.

    Retries on 403 rate-limit errors (subcode 2207051) with a delay between
    attempts. Before each retry, checks if the container was already published
    (the prior attempt may have succeeded despite returning an error).
    """
    account_id = os.environ["META_INSTAGRAM_ACCOUNT_ID"]
    token = os.environ["META_ACCESS_TOKEN"]

    for attempt in range(max_retries + 1):
        resp = requests.post(
            f"{GRAPH_API_BASE}/{account_id}/media_publish",
            params={
                "creation_id": container_id,
                "access_token": token,
            },
        )
        if resp.status_code == 200:
            return resp.json()["id"]

        # Log the error details for debugging
        error_data = resp.json().get("error", {})
        print(
            f"Publish attempt {attempt + 1}/{max_retries + 1} failed: "
            f"HTTP {resp.status_code}, code={error_data.get('code')}, "
            f"subcode={error_data.get('error_subcode')}, "
            f"message={error_data.get('message', 'unknown')}"
        )

        # On any error, check if the container was already published
        # (a prior attempt may have succeeded despite returning an error)
        try:
            status = check_container_status(container_id)
            print(f"Container status: {status}")
            if status == "PUBLISHED":
                print("Container already published — returning success.")
                return container_id
        except Exception as e:
            print(f"Status check failed: {e}")

        is_rate_limit = error_data.get("code") == 4 or resp.status_code == 403
        if is_rate_limit and attempt < max_retries:
            wait = retry_delay * (attempt + 1)
            print(f"Retrying in {wait:.0f}s...")
            time.sleep(wait)
            continue

        # Not a rate limit or out of retries — raise
        resp.raise_for_status()

    resp.raise_for_status()
    return resp.json()["id"]


def create_scheduled_container(
    image_url: str, caption: str, publish_time: "datetime"
) -> str:
    """Create a scheduled image media container on Instagram.

    The post will be auto-published by Meta at the specified time.
    Returns container ID.
    """
    from datetime import datetime, timezone

    if publish_time.tzinfo is None:
        raise ValueError("publish_time must be timezone-aware")
    if publish_time <= datetime.now(timezone.utc):
        raise ValueError("publish_time must be in the future")

    account_id = os.environ["META_INSTAGRAM_ACCOUNT_ID"]
    token = os.environ["META_ACCESS_TOKEN"]

    resp = requests.post(
        f"{GRAPH_API_BASE}/{account_id}/media",
        params={
            "image_url": image_url,
            "caption": caption,
            "scheduled_publish_time": int(publish_time.timestamp()),
            "access_token": token,
        },
    )
    resp.raise_for_status()
    return resp.json()["id"]


def schedule_post(
    file_path: str, caption: str, publish_time: "datetime"
) -> dict:
    """Upload to R2 and create a scheduled container.

    Unlike publish(), does NOT delete from R2 — Meta needs the image
    accessible until the scheduled publish time.
    """
    media_url = upload_to_r2(file_path)
    container_id = create_scheduled_container(media_url, caption, publish_time)
    return {"container_id": container_id, "image_url": media_url}


def check_recent_media(caption: str, limit: int = 5) -> bool:
    """Check if a post with this caption was recently published on Instagram.

    Queries the account's recent media to detect posts that published
    successfully despite the API returning an error.
    """
    account_id = os.environ["META_INSTAGRAM_ACCOUNT_ID"]
    token = os.environ["META_ACCESS_TOKEN"]
    try:
        resp = requests.get(
            f"{GRAPH_API_BASE}/{account_id}/media",
            params={
                "fields": "id,caption,timestamp",
                "limit": limit,
                "access_token": token,
            },
        )
        resp.raise_for_status()
        for post in resp.json().get("data", []):
            if post.get("caption") == caption:
                print(f"Post already live on Instagram (media_id={post['id']})")
                return True
    except Exception as e:
        print(f"Recent media check failed: {e}")
    return False


def create_carousel_child(
    image_url: str, max_retries: int = 2, retry_delay: float = 10.0
) -> str:
    """Create a carousel child container on Instagram. Returns container ID.

    Retries on transient 5xx errors from Meta's API.
    """
    account_id = os.environ["META_INSTAGRAM_ACCOUNT_ID"]
    token = os.environ["META_ACCESS_TOKEN"]

    for attempt in range(max_retries + 1):
        resp = requests.post(
            f"{GRAPH_API_BASE}/{account_id}/media",
            params={
                "image_url": image_url,
                "is_carousel_item": "true",
                "access_token": token,
            },
        )
        if resp.status_code >= 500 and attempt < max_retries:
            wait = retry_delay * (attempt + 1)
            print(
                f"Carousel child creation got {resp.status_code}, "
                f"retrying in {wait:.0f}s (attempt {attempt + 1}/{max_retries + 1})..."
            )
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()["id"]


def create_carousel_container(children_ids: list[str], caption: str) -> str:
    """Create a carousel container on Instagram. Returns container ID."""
    account_id = os.environ["META_INSTAGRAM_ACCOUNT_ID"]
    token = os.environ["META_ACCESS_TOKEN"]

    resp = requests.post(
        f"{GRAPH_API_BASE}/{account_id}/media",
        params={
            "media_type": "CAROUSEL",
            "children": ",".join(children_ids),
            "caption": caption,
            "access_token": token,
        },
    )
    resp.raise_for_status()
    return resp.json()["id"]


def publish_carousel(file_paths: list[str], caption: str) -> dict:
    """Full carousel publish: upload all to R2 -> child containers -> carousel -> wait -> publish -> cleanup."""
    media_urls = []
    try:
        # Upload all images to R2
        for path in file_paths:
            media_urls.append(upload_to_r2(path))

        # Delay to let R2 propagate before Meta fetches
        time.sleep(30)

        # Create children + carousel and publish (full rebuild on ERROR)
        max_container_attempts = 3
        for container_attempt in range(max_container_attempts):
            # (Re)create child containers each attempt — they expire with the parent
            children_ids = []
            for url in media_urls:
                children_ids.append(create_carousel_child(url))

            container_id = create_carousel_container(children_ids, caption)
            wait_for_container(container_id)
            try:
                media_id = publish_container(container_id)
                break
            except Exception:
                try:
                    status = check_container_status(container_id)
                except Exception:
                    status = "UNKNOWN"
                if status == "PUBLISHED":
                    media_id = container_id
                    break
                # Last resort: wait briefly for Meta to propagate, then check
                # if the post actually went live on Instagram
                time.sleep(10)
                if check_recent_media(caption):
                    print("Post confirmed live despite API errors — treating as success.")
                    media_id = container_id
                    break
                if container_attempt < max_container_attempts - 1:
                    wait = 180 * (container_attempt + 1)
                    print(
                        f"Publish failed, container status: {status} "
                        f"(attempt {container_attempt + 1}/{max_container_attempts}). "
                        f"Full rebuild in {wait}s..."
                    )
                    time.sleep(wait)
                    continue
                raise
    except Exception:
        for url in media_urls:
            delete_from_r2(url)
        raise

    # Cleanup R2
    for url in media_urls:
        delete_from_r2(url)

    return {"media_id": media_id, "media_urls": media_urls}


def _is_video(file_path: str) -> bool:
    ext = os.path.splitext(file_path)[1].lower()
    return ext in (".mp4", ".webm", ".mov")


def publish(file_path: str, caption: str) -> dict:
    """Full publish flow: upload to R2 -> create container -> wait -> publish -> cleanup."""
    media_url = upload_to_r2(file_path)
    try:
        if _is_video(file_path):
            container_id = create_reels_container(media_url, caption)
        else:
            container_id = create_container(media_url, caption)
        wait_for_container(container_id)
        media_id = publish_container(container_id)
    except Exception:
        delete_from_r2(media_url)
        raise
    delete_from_r2(media_url)
    return {"media_id": media_id, "media_url": media_url}
