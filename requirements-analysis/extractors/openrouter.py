"""OpenRouter LLM extractor: disk cache, 429 backoff, per-model rate limit."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List

import requests

from extractors.base import validate_obligation
from lib import vocabulary as vocab_mod
from lib.types import ExtractedObligation, Paragraph

logger = logging.getLogger(__name__)


_API = "https://openrouter.ai/api/v1/chat/completions"
_PROMPT_VERSION = "v1"
_CACHE_DIR = Path(__file__).resolve().parent.parent / "extractions" / ".cache"


_SYSTEM_PROMPT = """\
You are a legal-text annotator. You extract obligations from regulatory
text. An obligation is a sentence (or clause) that contains a deontic
modal ("shall", "must", "should", "is required to", "are required to",
"is recommended to", "we recommend") AND specifies (a) WHO is bound, (b)
WHAT they must do, and (c) the ARTEFACT or object of the obligation.

Output STRICT JSON ONLY. No prose. No markdown. No explanations. Schema:

{
  "obligations": [
    {
      "verbatim": "<exact substring of the input paragraph>",
      "modal": "<one of: shall, must, should, may, is required to, are required to, is recommended to, we recommend, recommended>",
      "bearer_phrase": "<the bound party, copied from the text>",
      "predicate_phrase": "<short verb phrase, e.g. 'draw up', 'monitor', 'report'>",
      "artefact_phrase": "<the object phrase, copied from the text>"
    }
  ]
}

Rules:
* `verbatim` MUST be an exact substring of the input paragraph (character-
  for-character). If you cannot find such a substring, omit the obligation.
* If a sentence contains no obligation matching the modals above, omit it.
* Do NOT invent obligations not present in the paragraph.
* Output an empty array `[]` for paragraphs with no obligations.
"""


_USER_TEMPLATE = (
    "Paragraph (locator={locator}, doc_id={doc_id}):\n"
    "------\n"
    "{text}\n"
    "------\n"
    "Extract obligations as JSON."
)


@dataclass
class OpenRouterConfig:
    api_key: str
    model: str
    timeout_s: float = 60.0
    max_retries: int = 6
    backoff_base_s: float = 30.0
    call_delay_s: float = 4.0
    temperature: float = 0.0


class OpenRouterExtractor:
    def __init__(self, model: str, *,
                 api_key: str | None = None,
                 timeout_s: float = 60.0,
                 max_retries: int = 6,
                 _http=None,
                 _enable_cache: bool = True) -> None:
        self.cfg = OpenRouterConfig(
            api_key=api_key or os.environ.get("OPENROUTER_API_KEY", ""),
            model=model,
            timeout_s=timeout_s,
            max_retries=max_retries,
            backoff_base_s=float(os.environ.get("OPENROUTER_BACKOFF_BASE_S", "30")),
            call_delay_s=float(os.environ.get("OPENROUTER_CALL_DELAY_S", "4")),
        )
        if not self.cfg.api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY not set; pass api_key=… or export it."
            )
        self._post = _http or self._post_real
        self.name = f"openrouter[{model}]"
        self._known_modals = set(vocab_mod.load().modal_tiers.keys())
        self._enable_cache = _enable_cache
        if _enable_cache:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._last_call_ts: float = 0.0


    def _cache_path(self, paragraph_text: str) -> Path:
        h = hashlib.sha256()
        h.update(self.cfg.model.encode())
        h.update(b"\x00")
        h.update(_PROMPT_VERSION.encode())
        h.update(b"\x00")
        h.update(paragraph_text.encode("utf-8", errors="replace"))
        return _CACHE_DIR / f"{h.hexdigest()}.json"

    def _read_cache(self, paragraph_text: str) -> dict | None:
        if not self._enable_cache:
            return None
        p = self._cache_path(paragraph_text)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text())
        except Exception:
            return None

    def _write_cache(self, paragraph_text: str, payload: dict) -> None:
        if not self._enable_cache:
            return
        try:
            self._cache_path(paragraph_text).write_text(json.dumps(payload))
        except Exception as exc:
            logger.warning("cache write failed: %s", exc)


    def _rate_limit_sleep(self) -> None:
        if self.cfg.call_delay_s <= 0:
            return
        elapsed = time.monotonic() - self._last_call_ts
        wait = self.cfg.call_delay_s - elapsed
        if wait > 0:
            time.sleep(wait)

    def _post_real(self, body: dict) -> dict:
        last_err: Exception | None = None
        for attempt in range(self.cfg.max_retries):
            self._rate_limit_sleep()
            try:
                r = requests.post(
                    _API,
                    headers={
                        "Authorization": f"Bearer {self.cfg.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/AnkurLohachab/SMART",
                        "X-Title": "SMART legal-evaluation harness",
                    },
                    json=body,
                    timeout=self.cfg.timeout_s,
                )
                self._last_call_ts = time.monotonic()
                if r.status_code == 200:
                    return r.json()
                if r.status_code in (429, 502, 503, 504):
                    last_err = RuntimeError(f"transient {r.status_code}: {r.text[:160]}")
                    backoff = self.cfg.backoff_base_s * min(8, 2 ** attempt)
                    logger.info(
                        "[%s] %d on attempt %d — sleeping %ds",
                        self.cfg.model, r.status_code, attempt, int(backoff),
                    )
                    time.sleep(backoff)
                    continue
                raise RuntimeError(f"openrouter {r.status_code}: {r.text[:300]}")
            except requests.RequestException as exc:
                self._last_call_ts = time.monotonic()
                last_err = exc
                time.sleep(self.cfg.backoff_base_s * min(8, 2 ** attempt))
        raise RuntimeError(f"openrouter failed after retries: {last_err!r}")


    def extract(self, p: Paragraph) -> List[ExtractedObligation]:
        cached = self._read_cache(p.text)
        if cached is not None:
            content = cached.get("content", "")
        else:
            body = {
                "model": self.cfg.model,
                "temperature": self.cfg.temperature,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user",
                     "content": _USER_TEMPLATE.format(
                         locator=p.locator, doc_id=p.doc_id, text=p.text[:4000]
                     )},
                ],
            }
            try:
                resp = self._post(body)
            except Exception as exc:
                logger.warning("openrouter post failed for %s/%s: %s",
                               p.doc_id, p.locator, exc)
                return []
            content = (resp.get("choices") or [{}])[0].get("message", {}).get("content", "")
            self._write_cache(p.text, {"content": content})
        rows = self._parse_json_obligations(content)

        out: List[ExtractedObligation] = []
        for r in rows:
            try:
                modal = " ".join(str(r.get("modal", "")).lower().split())
                if modal not in self._known_modals:
                    continue
                ob = ExtractedObligation(
                    extractor=self.name,
                    doc_id=p.doc_id,
                    locator=p.locator,
                    verbatim=str(r.get("verbatim", "")).strip(),
                    modal=modal,
                    bearer_phrase=str(r.get("bearer_phrase", "")).strip()[:300],
                    predicate_phrase=str(r.get("predicate_phrase", "")).strip()[:80],
                    artefact_phrase=str(r.get("artefact_phrase", "")).strip()[:300],
                )
                validate_obligation(ob, p)
                out.append(ob)
            except (ValueError, TypeError) as exc:
                logger.debug("dropping row from %s/%s: %s", p.doc_id, p.locator, exc)
                continue
        return out


    @staticmethod
    def _parse_json_obligations(content: str) -> list[dict]:
        if not content:
            return []
        m = re.search(r"```(?:json)?\s*([\s\S]+?)```", content)
        if m:
            content = m.group(1)
        first = content.find("{")
        if first < 0:
            return []
        depth = 0
        end = -1
        for i, c in enumerate(content[first:], start=first):
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end < 0:
            return []
        try:
            obj = json.loads(content[first:end])
        except json.JSONDecodeError:
            return []
        rows = obj.get("obligations") if isinstance(obj, dict) else None
        return rows if isinstance(rows, list) else []
