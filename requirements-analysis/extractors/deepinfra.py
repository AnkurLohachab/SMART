"""DeepInfra LLM extractor with a temperature sweep for self-consistency."""
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

_API = "https://api.deepinfra.com/v1/openai/chat/completions"
_PROMPT_VERSION = "v1-deepinfra"
_CACHE_DIR = Path(__file__).resolve().parent.parent / "extractions" / ".cache"

DEFAULT_TEMPS = ((0.0, 1), (0.3, 2), (0.7, 2))


from extractors.openrouter import _SYSTEM_PROMPT, _USER_TEMPLATE


@dataclass
class DeepInfraConfig:
    api_key: str
    model: str
    timeout_s: float = 60.0
    max_retries: int = 4
    backoff_base_s: float = 5.0
    call_delay_s: float = 0.0
    temps: tuple = DEFAULT_TEMPS


class DeepInfraExtractor:
    def __init__(self, model: str, *,
                 api_key: str | None = None,
                 timeout_s: float = 60.0,
                 max_retries: int = 4,
                 _http=None,
                 _enable_cache: bool = True,
                 temps: tuple = DEFAULT_TEMPS) -> None:
        self.cfg = DeepInfraConfig(
            api_key=api_key or os.environ.get("DEEPINFRA_API_KEY", ""),
            model=model,
            timeout_s=timeout_s,
            max_retries=max_retries,
            backoff_base_s=float(os.environ.get("DEEPINFRA_BACKOFF_BASE_S", "5")),
            call_delay_s=float(os.environ.get("DEEPINFRA_CALL_DELAY_S", "0")),
            temps=temps,
        )
        if not self.cfg.api_key:
            raise RuntimeError(
                "DEEPINFRA_API_KEY not set; pass api_key=… or export it."
            )
        self._post = _http or self._post_real
        self.name = f"deepinfra[{model}]"
        self._known_modals = set(vocab_mod.load().modal_tiers.keys())
        self._enable_cache = _enable_cache
        if _enable_cache:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._last_call_ts: float = 0.0


    def _cache_path(self, paragraph_text: str, temperature: float, sample_idx: int) -> Path:
        h = hashlib.sha256()
        h.update(self.cfg.model.encode())
        h.update(b"\x00")
        h.update(_PROMPT_VERSION.encode())
        h.update(b"\x00")
        h.update(f"T={temperature}".encode())
        h.update(b"\x00")
        h.update(f"S={sample_idx}".encode())
        h.update(b"\x00")
        h.update(paragraph_text.encode("utf-8", errors="replace"))
        return _CACHE_DIR / f"{h.hexdigest()}.json"

    def _read_cache(self, paragraph_text: str, temperature: float, sample_idx: int) -> dict | None:
        if not self._enable_cache:
            return None
        p = self._cache_path(paragraph_text, temperature, sample_idx)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text())
        except Exception:
            return None

    def _write_cache(self, paragraph_text: str, temperature: float, sample_idx: int, payload: dict) -> None:
        if not self._enable_cache:
            return
        try:
            self._cache_path(paragraph_text, temperature, sample_idx).write_text(json.dumps(payload))
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
                        "[%s] %d on attempt %d — sleeping %.1fs",
                        self.cfg.model, r.status_code, attempt, backoff,
                    )
                    time.sleep(backoff)
                    continue
                raise RuntimeError(f"deepinfra {r.status_code}: {r.text[:300]}")
            except requests.RequestException as exc:
                last_err = exc
                time.sleep(self.cfg.backoff_base_s * min(8, 2 ** attempt))
        raise RuntimeError(f"deepinfra failed after retries: {last_err!r}")


    def _one_call(self, p: Paragraph, temperature: float, sample_idx: int) -> str:
        cached = self._read_cache(p.text, temperature, sample_idx)
        if cached is not None:
            return cached.get("content", "")
        body = {
            "model": self.cfg.model,
            "temperature": temperature,
            "max_tokens": 1024,
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
            logger.warning("deepinfra post failed for %s/%s T=%.1f S=%d: %s",
                           p.doc_id, p.locator, temperature, sample_idx, exc)
            return ""
        content = (resp.get("choices") or [{}])[0].get("message", {}).get("content", "")
        self._write_cache(p.text, temperature, sample_idx, {"content": content})
        return content


    def extract(self, p: Paragraph) -> List[ExtractedObligation]:
        out: List[ExtractedObligation] = []
        for temperature, n_samples in self.cfg.temps:
            for sample_idx in range(n_samples):
                content = self._one_call(p, temperature, sample_idx)
                rows = _parse_json_obligations(content)
                for r in rows:
                    try:
                        modal = " ".join(str(r.get("modal", "")).lower().split())
                        if modal not in self._known_modals:
                            continue
                        ob = ExtractedObligation(
                            extractor=f"{self.name}@T{temperature}#{sample_idx}",
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
                        logger.debug("dropped row from %s/%s T=%.1f S=%d: %s",
                                     p.doc_id, p.locator, temperature, sample_idx, exc)
                        continue
        return out


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
