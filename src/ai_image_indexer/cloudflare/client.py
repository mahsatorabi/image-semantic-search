"""Cloudflare Workers AI REST API client."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import httpx

from ai_image_indexer.config import Settings


class CloudflareAIError(Exception):
    pass


class CloudflareAIClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = httpx.Client(
            timeout=settings.request_timeout,
            trust_env=False,
            headers={
                "Authorization": f"Bearer {settings.api_token}",
                "Content-Type": "application/json",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> CloudflareAIClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _run_model(self, model: str, payload: dict[str, Any]) -> Any:
        url = (
            f"{self.settings.api_base_url}/accounts/"
            f"{self.settings.account_id}/ai/run/{model}"
        )
        last_error: Exception | None = None

        for attempt in range(self.settings.max_retries):
            try:
                response = self._client.post(url, json=payload)
                if response.status_code == 429:
                    time.sleep(2**attempt)
                    continue
                response.raise_for_status()
                body = response.json()
                if not body.get("success", True):
                    errors = body.get("errors", body)
                    raise CloudflareAIError(f"API error: {errors}")
                return body.get("result", body)
            except (httpx.HTTPError, CloudflareAIError) as exc:
                last_error = exc
                if attempt < self.settings.max_retries - 1:
                    time.sleep(2**attempt)
                continue

        raise CloudflareAIError(f"Failed after {self.settings.max_retries} attempts: {last_error}")

    @staticmethod
    def _read_image_bytes(path: Path) -> list[int]:
        return list(path.read_bytes())

    def analyze_image(self, image_path: Path) -> dict[str, str | list[str]]:
        image_bytes = self._read_image_bytes(image_path)

        caption_result = self._run_model(
            self.settings.vision_model,
            {
                "image": image_bytes,
                "prompt": (
                    "Describe this image in detail. Include objects, people, colors, "
                    "setting, mood, and any visible text."
                ),
                "max_tokens": 512,
            },
        )
        caption = self._extract_text(caption_result)

        tags_result = self._run_model(
            self.settings.vision_model,
            {
                "image": image_bytes,
                "prompt": (
                    "List 5-10 short descriptive tags for this image. "
                    "Return only comma-separated tags, no explanation."
                ),
                "max_tokens": 128,
            },
        )
        tags = self._parse_tags(self._extract_text(tags_result))

        ocr_result = self._run_model(
            self.settings.vision_model,
            {
                "image": image_bytes,
                "prompt": (
                    "Extract all visible text from this image. "
                    "If no text is visible, respond with NONE."
                ),
                "max_tokens": 256,
            },
        )
        ocr_text = self._extract_text(ocr_result)
        if ocr_text.upper().strip() in {"NONE", "N/A", ""}:
            ocr_text = ""

        return {"caption": caption, "tags": tags, "ocr_text": ocr_text}

    def embed_text(self, text: str) -> list[float]:
        result = self._run_model(
            self.settings.embedding_model,
            {"text": [text]},
        )
        return self._extract_embedding(result)

    @staticmethod
    def _extract_text(result: Any) -> str:
        if isinstance(result, str):
            return result.strip()
        if isinstance(result, dict):
            for key in ("response", "description", "caption", "text", "output"):
                if key in result and isinstance(result[key], str):
                    return result[key].strip()
            if "result" in result and isinstance(result["result"], str):
                return result["result"].strip()
        return str(result).strip()

    @staticmethod
    def _parse_tags(raw: str) -> list[str]:
        if not raw:
            return []
        parts = re.split(r"[,;\n]+", raw)
        tags = [t.strip().strip("-•").lower() for t in parts if t.strip()]
        seen: set[str] = set()
        unique: list[str] = []
        for tag in tags:
            if tag and tag not in seen:
                seen.add(tag)
                unique.append(tag)
        return unique[:15]

    @staticmethod
    def _extract_embedding(result: Any) -> list[float]:
        if isinstance(result, dict):
            data = result.get("data")
            if isinstance(data, list) and data:
                first = data[0]
                if isinstance(first, list):
                    return [float(x) for x in first]
                if isinstance(first, (int, float)):
                    return [float(x) for x in data]
        raise CloudflareAIError(f"Unexpected embedding response: {json.dumps(result)[:200]}")
