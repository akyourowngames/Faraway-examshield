from __future__ import annotations

import json
import mimetypes
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .settings import Settings
from .store import EvidenceStore, JsonObject, UploadedFile, normalize_telegram_timestamp


class TelegramWebhook:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.telegram_bot_token and self.settings.public_url)

    def register(self) -> None:
        if not self.configured:
            return
        payload: JsonObject = {
            "url": f"{self.settings.public_url}/telegram/webhook",
            "allowed_updates": ["message", "edited_message", "channel_post", "edited_channel_post"],
            "drop_pending_updates": False,
        }
        if self.settings.telegram_webhook_secret:
            payload["secret_token"] = self.settings.telegram_webhook_secret
        self._api("setWebhook", payload)

    def validate_secret(self, received: str | None) -> bool:
        expected = self.settings.telegram_webhook_secret
        return not expected or received == expected

    def process_update(
        self,
        update: JsonObject,
        store: EvidenceStore,
        ocr_runner: Callable[[bytes, str], JsonObject],
    ) -> JsonObject:
        message = next(
            (
                update.get(name)
                for name in ("message", "edited_message", "channel_post", "edited_channel_post")
                if isinstance(update.get(name), dict)
            ),
            None,
        )
        if not isinstance(message, dict):
            return {"message": "Telegram update ignored", "processed": False}

        chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
        chat_id = str(chat.get("id") or "")
        message_id = str(message.get("message_id") or "")
        if not chat_id or not message_id:
            return {"message": "Telegram update ignored", "processed": False}
        if self.settings.telegram_chat_id and chat_id != self.settings.telegram_chat_id:
            return {"message": "Telegram update ignored", "processed": False}

        uploaded = self._download_media(message)
        created = store.create_telegram_event(
            message_id=message_id,
            chat_id=chat_id,
            timestamp=normalize_telegram_timestamp(message.get("date")),
            text=optional_text(message.get("caption") or message.get("text")),
            file=uploaded,
        )
        if created["duplicate"] or not created["evidence"]:
            return {
                "message": "Telegram update accepted",
                "processed": True,
                "duplicate": created["duplicate"],
                "evidence": created["evidence"],
            }

        queued = store.create_analysis_job(created["evidence"]["evidenceId"])
        analysis = store.run_analysis_job(queued["job"]["jobId"], ocr_runner)
        return {
            "message": "Telegram evidence processed",
            "processed": True,
            "duplicate": False,
            "evidence": analysis["evidence"],
            "job": analysis["job"],
        }

    def _download_media(self, message: JsonObject) -> UploadedFile | None:
        media = self._pick_media(message)
        if not media:
            return None
        file_info = self._api("getFile", {"file_id": media["fileId"]})
        file_path = str(file_info.get("file_path") or "")
        if not file_path:
            raise RuntimeError("Telegram did not return a file path.")
        request = urllib.request.Request(
            f"https://api.telegram.org/file/bot{self.settings.telegram_bot_token}/{file_path}"
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read()
        return UploadedFile(
            filename=media["filename"],
            content_type=media["contentType"],
            data=data,
        )

    def _pick_media(self, message: JsonObject) -> JsonObject | None:
        photos = message.get("photo")
        if isinstance(photos, list) and photos:
            photo = photos[-1]
            if isinstance(photo, dict) and photo.get("file_id"):
                return {
                    "fileId": str(photo["file_id"]),
                    "filename": f"telegram-{message.get('message_id')}.jpg",
                    "contentType": "image/jpeg",
                }

        document = message.get("document")
        if not isinstance(document, dict) or not document.get("file_id"):
            return None
        content_type = str(document.get("mime_type") or "application/octet-stream")
        if content_type not in {"image/jpeg", "image/png", "application/pdf"}:
            return None
        filename = Path(str(document.get("file_name") or "")).name
        if not filename:
            extension = mimetypes.guess_extension(content_type) or ""
            filename = f"telegram-{message.get('message_id')}{extension}"
        return {
            "fileId": str(document["file_id"]),
            "filename": filename,
            "contentType": content_type,
        }

    def _api(self, method: str, payload: JsonObject) -> JsonObject:
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/{method}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
        if not body.get("ok"):
            raise RuntimeError(str(body.get("description") or f"Telegram {method} failed."))
        result = body.get("result")
        return result if isinstance(result, dict) else {}


def optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
