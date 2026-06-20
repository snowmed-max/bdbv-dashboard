#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto-update public BDBV dashboard data.

What this script does:
1. Fetches latest news from GDELT and updates data/news.json.
2. Fetches selected official/public-health pages and extracts candidate numbers.
3. Writes all extracted candidates to data/candidates.json.
4. Optionally appends a new official row to data/timeseries.json when a higher
   confirmed-case count is found from official/quasi-official sources.

Important:
- This script is intentionally conservative. It marks automatically extracted
  official metrics as "auto_official_candidate" and keeps source URLs.
- Media numbers are NOT appended to timeseries by default. They update news.json
  and candidates.json only.
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
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

TIMESERIES = DATA_DIR / "timeseries.json"
REGIONAL = DATA_DIR / "regional.json"
NEWS = DATA_DIR / "news.json"
CANDIDATES = DATA_DIR / "candidates.json"

AUTO_APPEND_OFFICIAL = os.getenv("AUTO_APPEND_OFFICIAL", "true").lower() == "true"
AUTO_APPEND_MEDIA = os.getenv("AUTO_APPEND_MEDIA", "false").lower() == "true"

QUERY = '(Bundibugyo OR "Ebola Bundibugyo" OR "Bundibugyo virus") (DRC OR Congo OR Uganda OR Ebola)'

OFFICIAL_SOURCES = [
    {
        "name": "CDC Current Situation",
        "url": "https://www.cdc.gov/ebola/situation-summary/index.html",
        "type": "official",
    },
    {
        "name": "WHO Disease Outbreak News",
        "url": "https://www.who.int/emergencies/disease-outbreak-news",
        "type": "official",
    },
    {
        "name": "WHO AFRO Ebola topic",
        "url": "https://www.afro.who.int/health-topics/ebola-disease",
        "type": "official",
    },
    {
        "name": "ECDC Ebola outbreak page",
        "url": "https://www.ecdc.europa.eu/en/ebola-outbreak-democratic-republic-congo-and-uganda",
        "type": "quasi_official",
    },
    {
        "name": "Africa CDC news",
        "url": "https://africacdc.org/news/",
        "type": "quasi_official",
    },
]


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


def fetch(url: str, timeout: int = 20) -> Optional[str]:
    headers = {
        "User-Agent": "BDBV-dashboard-monitor/1.0 (+https://github.com/)",
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


def to_int(s: str) -> Optional[int]:
    try:
        return int(re.sub(r"[,\s]", "", s))
    except Exception:
        return None


def extract_metrics(text: str) -> Dict[str, Optional[int]]:
    """Heuristic extraction; intentionally simple and conservative."""
    lower = text.lower()
    metrics: Dict[str, Optional[int]] = {"cases": None, "deaths": None, "recovered": None}

    # Search within windows containing relevant keywords to reduce false positives.
    def best_number_for(keywords: List[str], labels: List[str]) -> Optional[int]:
        values: List[int] = []
        for kw in keywords:
            for m in re.finditer(re.escape(kw.lower()), lower):
                start = max(0, m.start() - 120)
                end = min(len(text), m.end() + 120)
                window = text[start:end]
                # Prefer numbers near the keyword
                nums = re.findall(r"(?<![\d.])\d{1,3}(?:,\d{3})+|\b\d{1,5}\b", window)
                for n in nums:
                    val = to_int(n)
                    if val is not None and val >= 0:
                        values.append(val)
        if not values:
            return None
        # For outbreak cumulative counts, largest nearby value is often the cumulative number.
        return max(values)

    metrics["cases"] = best_number_for(
        ["confirmed cases", "confirmed case", "cases confirmed", "case count", "cases"],
        ["cases"],
    )
    metrics["deaths"] = best_number_for(
        ["deaths", "death", "fatalities", "died"],
        ["deaths"],
    )
    metrics["recovered"] = best_number_for(
        ["recovered", "recovery", "discharged", "survivors"],
        ["recovered"],
    )

    # Guardrails: avoid absurd values caused by unrelated dates or page boilerplate.
    for k, v in list(metrics.items()):
        if v is not None and (v > 100000 or v < 0):
            metrics[k] = None

    return metrics


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

    rows = []
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
        rows.append(
            {
                "date": date,
                "title": title,
                "source": domain or "GDELT",
                "url": link,
                "summary": title,
                "status": "auto_media",
            }
        )
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
        # Only treat pages mentioning Bundibugyo/Ebola/Congo/Uganda as relevant.
        rel = text.lower()
        if not any(x in rel for x in ["bundibugyo", "ebola", "congo", "uganda", "drc"]):
            continue
        metrics = extract_metrics(text)
        if any(v is not None for v in metrics.values()):
            candidates.append(
                {
                    "date": today(),
                    "source": src["name"],
                    "source_type": src["type"],
                    "url": src["url"],
                    "cases": metrics.get("cases"),
                    "deaths": metrics.get("deaths"),
                    "recovered": metrics.get("recovered"),
                    "status": "auto_official_candidate",
                    "note": "自动从官方/准官方页面提取，需结合原文复核。",
                }
            )
        time.sleep(0.5)

    # Media candidates from titles only: not reliable enough for timeseries.
    number_pattern = re.compile(r"(\d{2,5})")
    for n in news_rows[:20]:
        title = n.get("title", "")
        if not title:
            continue
        if number_pattern.search(title):
            candidates.append(
                {
                    "date": n.get("date") or today(),
                    "source": n.get("source") or "media",
                    "source_type": "media",
                    "url": n.get("url"),
                    "cases": None,
                    "deaths": None,
                    "recovered": None,
                    "status": "media_candidate",
                    "note": title,
                }
            )

    return candidates


def append_official_timeseries_if_confident(candidates: List[Dict[str, Any]]) -> bool:
    rows: List[Dict[str, Any]] = load_json(TIMESERIES, [])
    if not rows:
        return False

    latest_official_cases = max(
        [r.get("cases") or 0 for r in rows if r.get("type") == "official"],
        default=0,
    )
    existing_keys = {(r.get("date"), r.get("source"), r.get("cases")) for r in rows}

    official_candidates = [
        c for c in candidates
        if c.get("source_type") in ("official", "quasi_official")
        and isinstance(c.get("cases"), int)
        and c["cases"] >= latest_official_cases
    ]
    if not official_candidates:
        return False

    # Choose the highest case count from official/quasi-official candidates.
    best = max(official_candidates, key=lambda c: c.get("cases") or 0)

    # Only append if new case count is higher than latest official count.
    if (best.get("cases") or 0) <= latest_official_cases:
        return False

    new_row = {
        "date": best.get("date") or today(),
        "cases": best.get("cases"),
        "deaths": best.get("deaths"),
        "recovered": best.get("recovered"),
        "type": "official",
        "source": "AUTO: " + (best.get("source") or "official source"),
        "url": best.get("url"),
        "note": "自动抓取新增官方/准官方口径；建议人工复核原文后保留或修正。",
    }

    key = (new_row["date"], new_row["source"], new_row["cases"])
    if key in existing_keys:
        return False

    rows.append(new_row)
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
    # Keep only current candidate batch plus top recent prior candidates.
    old_candidates = load_json(CANDIDATES, [])
    combined = candidates + old_candidates
    seen = set()
    deduped = []
    for c in combined:
        key = (c.get("date"), c.get("source"), c.get("url"), c.get("cases"), c.get("deaths"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)
    save_json(CANDIDATES, deduped[:80])

    changed_timeseries = False
    if AUTO_APPEND_OFFICIAL:
        changed_timeseries = append_official_timeseries_if_confident(deduped)

    print(json.dumps({
        "date": today(),
        "gdelt_news": len(gdelt_news),
        "news_total": len(merged_news),
        "candidates": len(deduped),
        "timeseries_appended": changed_timeseries,
        "auto_append_official": AUTO_APPEND_OFFICIAL,
        "auto_append_media": AUTO_APPEND_MEDIA,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
