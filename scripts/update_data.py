#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Safer auto-update script for BDBV dashboard.

Design principle:
- Automated scripts are good at "finding signals", not at making final public-health
  claims from unstructured web pages.
- Therefore this script writes auto-extracted numbers to data/candidates.json by default.
- It does NOT append to data/timeseries.json unless AUTO_APPEND_OFFICIAL=true and
  the candidate passes strict validation rules. The workflow provided with this package
  sets AUTO_APPEND_OFFICIAL=false.

Main safeguards:
1. Reject likely years such as 2026 when interpreted as case counts.
2. Reject numbers near "suspected", "probable", "contacts", "health zones", "%", etc.
3. Extract only from local context windows that mention Bundibugyo/Ebola plus cases/deaths/recovered.
4. Mark every candidate with confidence, warnings and source URL.
5. Keep official/quasi-official and media candidates separated.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

TIMESERIES = DATA_DIR / "timeseries.json"
NEWS = DATA_DIR / "news.json"
CANDIDATES = DATA_DIR / "candidates.json"

AUTO_APPEND_OFFICIAL = os.getenv("AUTO_APPEND_OFFICIAL", "false").lower() == "true"
AUTO_APPEND_MEDIA = os.getenv("AUTO_APPEND_MEDIA", "false").lower() == "true"

QUERY = '(Bundibugyo OR "Ebola Bundibugyo" OR "Bundibugyo virus") (DRC OR Congo OR Uganda OR Ebola)'

# Prefer pages that are about the current situation, not archive/list pages.
OFFICIAL_SOURCES = [
    {
        "name": "CDC Current Situation",
        "url": "https://www.cdc.gov/ebola/situation-summary/index.html",
        "type": "official",
        "append_allowed": False,  # candidate only unless manually reviewed
    },
    {
        "name": "ECDC outbreak page",
        "url": "https://www.ecdc.europa.eu/en/ebola-outbreak-democratic-republic-congo-and-uganda",
        "type": "quasi_official",
        "append_allowed": False,
    },
    {
        "name": "WHO Disease Outbreak News index",
        "url": "https://www.who.int/emergencies/disease-outbreak-news",
        "type": "official_index",
        "append_allowed": False,  # index pages are too risky for numeric extraction
    },
    {
        "name": "WHO AFRO Ebola topic",
        "url": "https://www.afro.who.int/health-topics/ebola-disease",
        "type": "official_index",
        "append_allowed": False,
    },
    {
        "name": "Africa CDC news",
        "url": "https://africacdc.org/news/",
        "type": "quasi_official_index",
        "append_allowed": False,
    },
]

BAD_CONTEXT_WORDS = [
    "suspected", "probable", "contacts", "contact", "health zones", "health zone",
    "districts", "laboratory samples", "samples", "alerts", "tested", "testing",
    "pui", "under investigation", "previous outbreak", "historical", "history",
    "since 1976", "1976", "2024", "2025", "2027", "percentage", "%", "percent"
]

GOOD_CASE_WORDS = [
    "confirmed cases", "confirmed case", "confirmed infections", "confirmed infection",
    "laboratory-confirmed cases", "confirmed", "case count"
]
GOOD_DEATH_WORDS = ["deaths", "death", "fatalities", "died"]
GOOD_RECOVERY_WORDS = ["recovered", "recovery", "discharged", "survivors"]

DISEASE_WORDS = ["bundibugyo", "ebola", "bdbv"]
LOCATION_WORDS = ["drc", "democratic republic of the congo", "congo", "uganda"]


def today() -> str:
    return dt.datetime.utcnow().date().isoformat()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        print(f"[WARN] Failed to read {path}; using default.", file=sys.stderr)
        return default


def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch(url: str, timeout: int = 25) -> Optional[str]:
    headers = {
        "User-Agent": "BDBV-dashboard-monitor/1.1 (+https://github.com/)",
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    }
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"[WARN] fetch failed: {url} ({e})", file=sys.stderr)
        return None


def clean_text(raw: str) -> str:
    try:
        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        txt = soup.get_text(" ")
    except Exception:
        txt = raw
    txt = html.unescape(txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()


def to_int(num: str) -> Optional[int]:
    try:
        return int(re.sub(r"[,\s]", "", num))
    except Exception:
        return None


def has_any(text: str, words: List[str]) -> bool:
    t = text.lower()
    return any(w in t for w in words)


def is_likely_year(value: int) -> bool:
    return 1900 <= value <= 2100


def reject_number_by_context(value: int, window: str) -> Optional[str]:
    low = window.lower()
    if is_likely_year(value):
        return "likely_year"
    if any(w in low for w in BAD_CONTEXT_WORDS):
        return "bad_context_word"
    if re.search(rf"{value}\s*%", window):
        return "percentage"
    if value > 100000:
        return "implausibly_large"
    return None


def number_candidates_near_keywords(text: str, keywords: List[str], metric: str) -> List[Tuple[int, str, int]]:
    """
    Return (value, window, score).
    Score is based on local context. Higher is better.
    """
    low = text.lower()
    out: List[Tuple[int, str, int]] = []
    for kw in keywords:
        for m in re.finditer(re.escape(kw.lower()), low):
            start = max(0, m.start() - 140)
            end = min(len(text), m.end() + 140)
            window = text[start:end]
            nums = re.findall(r"(?<![\d.])\d{1,3}(?:,\d{3})+|\b\d{1,5}\b", window)
            for n in nums:
                value = to_int(n)
                if value is None:
                    continue
                reason = reject_number_by_context(value, window)
                if reason:
                    continue
                score = 0
                wl = window.lower()
                if has_any(wl, DISEASE_WORDS):
                    score += 3
                if has_any(wl, LOCATION_WORDS):
                    score += 2
                if metric == "cases" and has_any(wl, ["confirmed", "laboratory-confirmed"]):
                    score += 4
                if metric == "deaths" and has_any(wl, GOOD_DEATH_WORDS):
                    score += 3
                if metric == "recovered" and has_any(wl, GOOD_RECOVERY_WORDS):
                    score += 3
                # Penalize vague windows.
                if "suspected" in wl or "probable" in wl:
                    score -= 5
                out.append((value, window, score))
    return out


def pick_metric(text: str, keywords: List[str], metric: str) -> Tuple[Optional[int], List[str], int]:
    cands = number_candidates_near_keywords(text, keywords, metric)
    warnings: List[str] = []
    if not cands:
        return None, ["no_candidate_found"], 0

    # Keep reasonably high context score.
    cands = [c for c in cands if c[2] >= 4]
    if not cands:
        return None, ["only_low_confidence_candidates"], 0

    # In cumulative outbreak summaries, the highest valid number near "confirmed cases"
    # often reflects the cumulative count, but we do not trust it enough for auto append.
    cands.sort(key=lambda x: (x[2], x[0]), reverse=True)
    value, window, score = cands[0]

    if len({v for v, _, _ in cands}) > 1:
        warnings.append("multiple_possible_numbers")

    return value, warnings, score


def extract_metrics_safely(text: str, source_type: str) -> Dict[str, Any]:
    low = text.lower()
    warnings: List[str] = []

    if not has_any(low, DISEASE_WORDS):
        warnings.append("missing_disease_keyword")
    if not has_any(low, LOCATION_WORDS):
        warnings.append("missing_location_keyword")

    cases, w1, s1 = pick_metric(text, GOOD_CASE_WORDS, "cases")
    deaths, w2, s2 = pick_metric(text, GOOD_DEATH_WORDS, "deaths")
    recovered, w3, s3 = pick_metric(text, GOOD_RECOVERY_WORDS, "recovered")

    warnings.extend(w1 + w2 + w3)

    # Consistency checks
    if cases is not None and deaths is not None and deaths > cases:
        warnings.append("deaths_greater_than_cases")
    if cases is not None and recovered is not None and recovered > cases:
        warnings.append("recovered_greater_than_cases")

    # Confidence score
    score = max(s1, s2, s3)
    if cases is not None:
        score += 2
    if deaths is not None:
        score += 1
    if recovered is not None:
        score += 1
    if source_type in ("official", "quasi_official"):
        score += 2
    if source_type.endswith("_index"):
        score -= 3
        warnings.append("index_page_not_safe_for_auto_timeseries")

    if warnings:
        score -= min(4, len(set(warnings)))

    confidence = "low"
    if score >= 10 and cases is not None and not any(w in warnings for w in ["missing_disease_keyword", "missing_location_keyword", "index_page_not_safe_for_auto_timeseries"]):
        confidence = "medium"
    if score >= 13 and cases is not None and source_type in ("official", "quasi_official") and not warnings:
        confidence = "high"

    return {
        "cases": cases,
        "deaths": deaths,
        "recovered": recovered,
        "confidence": confidence,
        "score": score,
        "warnings": sorted(set(warnings)),
    }


def fetch_gdelt_news() -> List[Dict[str, Any]]:
    url = (
        "https://api.gdeltproject.org/api/v2/doc/doc?"
        f"query={quote(QUERY)}&mode=artlist&format=json&maxrecords=30&sort=hybridrel"
    )
    raw = fetch(url, timeout=30)
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except Exception as e:
        print(f"[WARN] GDELT JSON parse failed: {e}", file=sys.stderr)
        return []

    rows: List[Dict[str, Any]] = []
    for a in payload.get("articles", [])[:30]:
        title = a.get("title") or ""
        link = a.get("url") or ""
        domain = a.get("domain") or ""
        seen = a.get("seendate") or ""
        date = seen[:8] if seen else today().replace("-", "")
        if len(date) == 8 and date.isdigit():
            date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
        else:
            date = today()
        if not link or not title:
            continue
        rows.append({
            "date": date,
            "title": title,
            "source": domain or "GDELT",
            "url": link,
            "summary": title,
            "status": "auto_media",
        })
    return rows


def merge_news(existing: List[Dict[str, Any]], new_rows: List[Dict[str, Any]], keep: int = 40) -> List[Dict[str, Any]]:
    by_url: Dict[str, Dict[str, Any]] = {}
    for row in existing + new_rows:
        url = row.get("url")
        if not url:
            continue
        by_url[url] = row
    rows = list(by_url.values())
    rows.sort(key=lambda r: r.get("date", ""), reverse=True)
    return rows[:keep]


def build_candidates_from_sources(news_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []

    for src in OFFICIAL_SOURCES:
        raw = fetch(src["url"])
        if not raw:
            continue
        text = clean_text(raw)
        metrics = extract_metrics_safely(text, src["type"])

        if any(metrics.get(k) is not None for k in ["cases", "deaths", "recovered"]) or metrics.get("warnings"):
            candidates.append({
                "date": today(),
                "source": src["name"],
                "source_type": src["type"],
                "url": src["url"],
                "cases": metrics.get("cases"),
                "deaths": metrics.get("deaths"),
                "recovered": metrics.get("recovered"),
                "confidence": metrics.get("confidence"),
                "score": metrics.get("score"),
                "warnings": metrics.get("warnings"),
                "status": "auto_official_candidate",
                "note": "自动提取候选数据。进入正式 timeseries.json 前必须人工复核原文上下文。",
                "auto_append_allowed_by_source": src.get("append_allowed", False),
            })
        time.sleep(0.5)

    # Media remains news/candidate only.
    for n in news_rows[:20]:
        title = n.get("title", "")
        if not title:
            continue
        if re.search(r"\b\d{2,5}\b", title):
            candidates.append({
                "date": n.get("date") or today(),
                "source": n.get("source") or "media",
                "source_type": "media",
                "url": n.get("url"),
                "cases": None,
                "deaths": None,
                "recovered": None,
                "confidence": "low",
                "score": 0,
                "warnings": ["media_title_number_only"],
                "status": "media_candidate",
                "note": title,
                "auto_append_allowed_by_source": False,
            })

    return candidates


def append_official_timeseries_if_confident(candidates: List[Dict[str, Any]]) -> bool:
    if not AUTO_APPEND_OFFICIAL:
        return False

    rows: List[Dict[str, Any]] = load_json(TIMESERIES, [])
    if not rows:
        return False

    latest_official_cases = max([r.get("cases") or 0 for r in rows if r.get("type") == "official"], default=0)

    eligible = [
        c for c in candidates
        if c.get("source_type") in ("official", "quasi_official")
        and c.get("confidence") == "high"
        and c.get("auto_append_allowed_by_source") is True
        and isinstance(c.get("cases"), int)
        and (c.get("cases") or 0) > latest_official_cases
        and not c.get("warnings")
    ]

    if not eligible:
        return False

    # Even with high confidence, write a cautious note.
    best = max(eligible, key=lambda c: c.get("cases") or 0)
    rows.append({
        "date": best.get("date") or today(),
        "cases": best.get("cases"),
        "deaths": best.get("deaths"),
        "recovered": best.get("recovered"),
        "type": "official",
        "source": "AUTO-HIGH-CONFIDENCE: " + (best.get("source") or "official source"),
        "url": best.get("url"),
        "note": "自动高置信追加；仍建议人工复核。若有误请删除本条并修正脚本规则。",
    })
    rows.sort(key=lambda r: r.get("date", ""))
    save_json(TIMESERIES, rows)
    return True


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)

    existing_news = load_json(NEWS, [])
    gdelt_news = fetch_gdelt_news()
    merged_news = merge_news(existing_news, gdelt_news)
    save_json(NEWS, merged_news)

    candidates = build_candidates_from_sources(gdelt_news)
    old_candidates = load_json(CANDIDATES, [])
    combined = candidates + old_candidates

    seen = set()
    deduped = []
    for c in combined:
        key = (c.get("date"), c.get("source"), c.get("url"), c.get("cases"), c.get("deaths"), c.get("recovered"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)

    save_json(CANDIDATES, deduped[:100])
    changed_timeseries = append_official_timeseries_if_confident(deduped)

    print(json.dumps({
        "date": today(),
        "gdelt_news": len(gdelt_news),
        "news_total": len(merged_news),
        "candidates": len(deduped),
        "timeseries_appended": changed_timeseries,
        "auto_append_official": AUTO_APPEND_OFFICIAL,
        "auto_append_media": AUTO_APPEND_MEDIA,
        "safety_mode": "candidate_first",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
