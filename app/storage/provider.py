from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StoredAsset:
    key: str
    url: str
    content_type: str


class ObjectStorage:
    """Provider-neutral object storage boundary.

    Production implementations can target S3, Cloudflare R2, Supabase Storage,
    or another managed object store without changing agent code.
    """

    def upload(self, key: str, data: bytes, content_type: str) -> StoredAsset:
        raise NotImplementedError

    def signed_url(self, key: str, expires_seconds: int = 3600) -> str:
        raise NotImplementedError
