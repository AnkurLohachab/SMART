"""LLM-as-judge panel: majority vote on whether two obligations are the same provision."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Iterable

import requests

logger = logging.getLogger(__name__)

_API = "https://api.deepinfra.com/v1/openai/chat/completions"
_PROMPT_VERSION = "judge-v1"
_CACHE_DIR = Path(__file__).resolve().parent.parent / "extractions" / ".judge_cache"


JUDGE_MODELS = [
    "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "Qwen/Qwen2.5-72B-Instruct",
]


_JUDGE_PROMPT = """\
You are a legal-text adjudicator. Two extraction systems produced
different (or no) representations of an obligation in a source paragraph.
Your job: decide whether they refer to the SAME regulatory obligation.

Return STRICT JSON ONLY:

{
  "verdict": "same" | "different" | "partial-overlap" | "neither-is-correct",
  "supporting_substring": "<verbatim substring from the paragraph>",
  "score": 0.0 to 1.0,
  "rationale": "<one short sentence>"
}

Rules:
* `supporting_substring` MUST be a verbatim substring of the input
  paragraph (you'll be penalised if it's not). If you cannot find such a
  substring, set verdict to `neither-is-correct`.
* `score` = your confidence the verdict is right (1.0 = certain).
"""


def _post(api_key: str, body: dict, timeout_s: float = 60.0) -> dict | None:
    for attempt in range(3):
        try:
            r = requests.post(
                _API,
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json=body,
                timeout=timeout_s,
            )
            if r.status_code == 200:
                return r.json()
            time.sleep(2 * (attempt + 1))
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
    return None


def _cache_path(model: str, paragraph: str, a: str, b: str) -> Path:
    h = hashlib.sha256()
    h.update(model.encode()); h.update(b"\x00")
    h.update(_PROMPT_VERSION.encode()); h.update(b"\x00")
    h.update(paragraph.encode("utf-8")); h.update(b"\x00")
    h.update(a.encode("utf-8")); h.update(b"\x00")
    h.update(b.encode("utf-8"))
    return _CACHE_DIR / f"{h.hexdigest()}.json"


def _parse_json(content: str) -> dict | None:
    if not content:
        return None
    m = re.search(r"```(?:json)?\s*([\s\S]+?)```", content)
    if m:
        content = m.group(1)
    first = content.find("{")
    if first < 0:
        return None
    depth, end = 0, -1
    for i, c in enumerate(content[first:], start=first):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end < 0:
        return None
    try:
        return json.loads(content[first:end])
    except json.JSONDecodeError:
        return None


def judge_one(model: str, paragraph: str, tuple_a: str, tuple_b: str,
              api_key: str | None = None) -> dict:
    """One judge response: parsed JSON or an {error: ...} dict."""
    api_key = api_key or os.environ.get("DEEPINFRA_API_KEY", "")
    if not api_key:
        return {"error": "DEEPINFRA_API_KEY not set", "verdict": None}

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p_cache = _cache_path(model, paragraph, tuple_a, tuple_b)
    if p_cache.exists():
        try:
            return json.loads(p_cache.read_text())
        except Exception:
            pass

    user_prompt = (
        f"Paragraph (verbatim):\n------\n{paragraph[:3500]}\n------\n\n"
        f"Tuple A: {tuple_a}\n"
        f"Tuple B: {tuple_b}\n\n"
        "Decide and return JSON."
    )
    body = {
        "model": model,
        "temperature": 0.0,
        "max_tokens": 600,
        "messages": [
            {"role": "system", "content": _JUDGE_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }
    resp = _post(api_key, body)
    if resp is None:
        return {"error": "transport_failure", "verdict": None}
    content = (resp.get("choices") or [{}])[0].get("message", {}).get("content", "")
    parsed = _parse_json(content) or {"error": "parse_failure", "raw": content[:200]}

    sub_str = parsed.get("supporting_substring", "")
    if sub_str and sub_str not in paragraph:
        parsed["error"] = "verbatim_not_in_paragraph"
        parsed["verdict"] = "neither-is-correct"

    p_cache.write_text(json.dumps(parsed))
    return parsed


def judge_panel(paragraph: str, tuple_a: str, tuple_b: str,
                models: list[str] | None = None) -> dict:
    """Run all judge models; return per-model and aggregate verdict."""
    models = models or JUDGE_MODELS
    per_model: dict[str, dict] = {}
    for m in models:
        per_model[m] = judge_one(m, paragraph, tuple_a, tuple_b)
    valid = [r for r in per_model.values()
             if r.get("verdict") in ("same", "different", "partial-overlap")]
    verdict_counts: dict[str, int] = {}
    score_sum, score_n = 0.0, 0
    for r in valid:
        v = r["verdict"]
        verdict_counts[v] = verdict_counts.get(v, 0) + 1
        try:
            score_sum += float(r.get("score", 0))
            score_n += 1
        except (TypeError, ValueError):
            pass
    if not verdict_counts:
        majority = "no_consensus"
        agreement = 0.0
    else:
        majority = max(verdict_counts.items(), key=lambda kv: kv[1])[0]
        agreement = verdict_counts[majority] / len(valid)
    return {
        "per_model": per_model,
        "majority_verdict": majority,
        "agreement_fraction": agreement,
        "mean_confidence": (score_sum / score_n) if score_n else 0.0,
        "n_valid_judges": len(valid),
    }
