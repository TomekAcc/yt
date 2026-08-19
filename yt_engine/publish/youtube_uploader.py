"""Stage 9: upload.

Resumable upload via the YouTube Data API v3, with the
altered/synthetic-content disclosure (STRATEGY.md §5) and the channel's
default privacy status (private by default -- a human publishes the video
after a final look, see README) always set explicitly rather than relying
on API defaults.
"""
from __future__ import annotations

import time
from pathlib import Path

from ..exceptions import ProviderError
from ..logging_utils import get_logger
from ..models import UploadResult, YouTubeMetadata
from .youtube_auth import get_credentials

log = get_logger(__name__)


class YouTubeUploader:
    def __init__(self, client_secrets_file: str | None, token_file: str) -> None:
        self._client_secrets_file = client_secrets_file
        self._token_file = token_file
        self._service = None

    def _get_service(self):
        if self._service is None:
            from googleapiclient.discovery import build

            creds = get_credentials(self._client_secrets_file, self._token_file)
            self._service = build("youtube", "v3", credentials=creds)
        return self._service

    def upload(self, video_path: Path, metadata: YouTubeMetadata) -> UploadResult:
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload

        service = self._get_service()
        body = {
            "snippet": {
                "title": metadata.title,
                "description": metadata.description,
                "tags": metadata.tags,
                "categoryId": metadata.category_id,
            },
            "status": {
                "privacyStatus": metadata.privacy_status,
                "selfDeclaredMadeForKids": metadata.made_for_kids,
                "containsSyntheticMedia": metadata.contains_synthetic_media,
            },
        }
        media = MediaFileUpload(str(video_path), chunksize=1024 * 1024 * 4, resumable=True, mimetype="video/mp4")
        request = service.videos().insert(part="snippet,status", body=body, media_body=media)

        video_id = _run_resumable(request)
        log.info("Uploaded video https://youtu.be/%s", video_id)

        if metadata.thumbnail_path and Path(metadata.thumbnail_path).exists():
            try:
                service.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(str(metadata.thumbnail_path), mimetype="image/jpeg"),
                ).execute()
            except HttpError as exc:
                log.warning("Video uploaded but thumbnail upload failed: %s", exc)

        return UploadResult(video_id=video_id, url=f"https://youtu.be/{video_id}")


def _run_resumable(request, max_retries: int = 6) -> str:
    from googleapiclient.errors import HttpError

    response = None
    retry = 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                log.info("Upload progress: %d%%", int(status.progress() * 100))
        except HttpError as exc:
            if exc.resp.status in (500, 502, 503, 504) and retry < max_retries:
                retry += 1
                sleep_s = 2**retry
                log.warning("Upload chunk failed (%s), retrying in %ss", exc.resp.status, sleep_s)
                time.sleep(sleep_s)
                continue
            raise ProviderError(f"YouTube upload failed: {exc}") from exc

    if "id" not in response:
        raise ProviderError(f"YouTube upload finished without a video id: {response}")
    return response["id"]
