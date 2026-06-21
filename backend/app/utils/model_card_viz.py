"""Server-side model card visualizations as base64 PNGs."""

import logging
import re
from typing import Any, Dict, List, Optional

from smart_model_card.visualizations import (
    generate_age_distribution_chart,
    generate_gender_pie_chart,
    generate_race_distribution_chart,
    generate_performance_metrics_bar_chart,
    generate_performance_metrics_line_chart,
)

logger = logging.getLogger(__name__)


_METRIC_RE = re.compile(
    r"\b([A-Za-z][A-Za-z0-9 _\-/]{0,30}?)\s*[:=]\s*([0-9]*\.?[0-9]+)"
)


def _parse_free_text_metrics(text: Any) -> List[Dict[str, Any]]:
    """Extract (metric_name, value) pairs from free-text, keeping values in [0, 100]."""
    if not isinstance(text, str) or not text.strip():
        return []
    out: List[Dict[str, Any]] = []
    seen = set()
    for m in _METRIC_RE.finditer(text):
        name = m.group(1).strip()
        try:
            value = float(m.group(2))
        except ValueError:
            continue
        if not (0.0 <= value <= 100.0):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({"metric_name": name, "value": value, "subgroup": "Overall"})
    return out


_PCT_PAIR_RE = re.compile(
    r"\b([A-Za-z][A-Za-z0-9 \-/]{0,40}?)\s*[:=]\s*([0-9]*\.?[0-9]+)\s*%?"
)


def _parse_pct_pairs(text: Any, label_key: str) -> List[Dict[str, Any]]:
    """Parse free-text categorical breakdowns like "Male: 54%, Female: 46%"."""
    if not isinstance(text, str) or not text.strip():
        return []
    out: List[Dict[str, Any]] = []
    seen = set()
    for m in _PCT_PAIR_RE.finditer(text):
        name = m.group(1).strip()
        try:
            value = float(m.group(2))
        except ValueError:
            continue
        if value > 100:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({label_key: name, "Count": value})
    return out


def _coerce_demographics(datasets: List[Any]) -> Dict[str, List[Dict]]:
    """Aggregate demographic distributions (age/gender/race) across datasets."""
    age: List[Dict] = []
    gender: List[Dict] = []
    race: List[Dict] = []
    for ds in datasets or []:
        if not isinstance(ds, dict):
            continue
        demo = ds.get("demographics") or ds.get("Demographics") or {}
        if not isinstance(demo, dict):
            continue

        for k in ("age_distribution", "Age Distribution", "ageDistribution"):
            v = demo.get(k)
            if isinstance(v, list):
                age.extend(item for item in v if isinstance(item, dict))
        for k in ("gender_distribution", "Gender Distribution"):
            v = demo.get(k)
            if isinstance(v, list):
                gender.extend(item for item in v if isinstance(item, dict))
        for k in ("race_distribution", "Race Distribution"):
            v = demo.get(k)
            if isinstance(v, list):
                race.extend(item for item in v if isinstance(item, dict))

        if not gender:
            for k in ("gender", "Gender", "sex", "Sex"):
                v = demo.get(k)
                if isinstance(v, str):
                    gender.extend(_parse_pct_pairs(v, "Gender"))
        if not race:
            for k in ("ethnicity", "Ethnicity", "race", "Race"):
                v = demo.get(k)
                if isinstance(v, str):
                    race.extend(_parse_pct_pairs(v, "Race"))
    return {"age_data": age, "gender_data": gender, "race_data": race}


def _safe_chart(name: str, fn, *args, **kwargs) -> Optional[str]:
    """Run a chart function, log+swallow any failure, return None on miss."""
    try:
        result = fn(*args, **kwargs)
        if not result:
            return None
        return result
    except Exception as exc:
        logger.warning("visualization '%s' failed: %s", name, exc)
        return None


def build_visualizations(metadata: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Generate the visualizations the metadata supports, grouped by section. Empty sections are omitted."""
    sections: Dict[str, Dict[str, Any]] = {"section_3": {}, "section_5": {}}

    data_section = metadata.get("3. Data & Factors") or {}
    datasets = (
        data_section.get("Source Datasets")
        or data_section.get("source_datasets")
        or []
    )
    demo = _coerce_demographics(datasets)

    if demo["age_data"]:
        img = _safe_chart(
            "age_distribution",
            generate_age_distribution_chart,
            demo["age_data"],
            "Patient age distribution",
        )
        if img:
            sections["section_3"]["age_distribution"] = {
                "image": img, "title": "Patient age distribution",
            }
    if demo["gender_data"]:
        img = _safe_chart(
            "gender_distribution",
            generate_gender_pie_chart,
            demo["gender_data"],
            "Gender distribution",
        )
        if img:
            sections["section_3"]["gender_distribution"] = {
                "image": img, "title": "Gender distribution",
            }
    if demo["race_data"]:
        img = _safe_chart(
            "race_distribution",
            generate_race_distribution_chart,
            demo["race_data"],
            "Race / ethnicity distribution",
        )
        if img:
            sections["section_3"]["race_distribution"] = {
                "image": img, "title": "Race / ethnicity distribution",
            }

    perf_section = metadata.get("5. Performance & Validation") or {}
    metrics_field = (
        perf_section.get("Claimed Metrics")
        or perf_section.get("claimed_metrics")
        or ""
    )
    metrics_data: List[Dict[str, Any]] = []
    if isinstance(metrics_field, list):
        for m in metrics_field:
            if not isinstance(m, dict):
                continue
            value = m.get("value")
            if value is None:
                continue
            try:
                metrics_data.append({
                    "metric_name": str(m.get("name") or m.get("metric_name") or "?"),
                    "value": float(value),
                    "subgroup": str(m.get("subgroup") or "Overall"),
                })
            except (TypeError, ValueError):
                continue
    else:
        metrics_data = _parse_free_text_metrics(metrics_field)

    if metrics_data:
        img = _safe_chart(
            "performance_metrics",
            generate_performance_metrics_bar_chart,
            metrics_data,
            "Claimed performance metrics",
        )
        if img:
            sections["section_5"]["performance_metrics"] = {
                "image": img, "title": "Claimed performance metrics",
                "metric_count": len(metrics_data),
            }

    fairness_field = (
        perf_section.get("Fairness Assessment")
        or perf_section.get("fairness_assessment")
        or ""
    )
    if isinstance(fairness_field, list):
        subgroup_data = []
        for m in fairness_field:
            if not isinstance(m, dict):
                continue
            try:
                subgroup_data.append({
                    "metric_name": str(m.get("name") or m.get("metric_name") or "?"),
                    "value": float(m.get("value")),
                    "subgroup": str(m.get("subgroup") or "?"),
                })
            except (TypeError, ValueError):
                continue
        if subgroup_data:
            img = _safe_chart(
                "fairness_subgroups",
                generate_performance_metrics_line_chart,
                subgroup_data,
                "Performance across subgroups",
            )
            if img:
                sections["section_5"]["fairness_subgroups"] = {
                    "image": img, "title": "Performance across subgroups",
                }

    return {k: v for k, v in sections.items() if v}
