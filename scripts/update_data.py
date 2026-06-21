#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WHO-only formal data update mode.

Formal dashboard time series:
- data/timeseries.json is the single source of truth for charts and metric cards.
- It should contain WHO / WHO AFRO confirmed data only.
- This script DOES NOT automatically append to timeseries.json.

Automatic updates:
- data/news.json: updated from GDELT/news signals.
- data/candidates.json: WHO / WHO AFRO candidates + media signals for manual review.
"""
from __future__ import annotations
import datetime as dt, html, json, re, sys, time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
NEWS = DATA_DIR / "news.json"
CANDIDATES = DATA_DIR / "candidates.json"
QUERY = '(Bundibugyo OR "Ebola Bundibugyo" OR "Bundibugyo virus") (DRC OR Congo OR Uganda OR Ebola)'
WHO_SOURCES = [
    {"name":"WHO Disease Outbreak News index","url":"https://www.who.int/emergencies/disease-outbreak-news","source_type":"who_index","note":"WHO DON 索引页，仅作为发现新 DON 的候选线索，不自动提取正式数字。"},
    {"name":"WHO AFRO Ebola topic","url":"https://www.afro.who.int/health-topics/ebola-disease","source_type":"who_afro_index","note":"WHO AFRO 专题页，仅作为发现 SitRep 的候选线索。"}
]
MEDIA_DOMAINS_TO_KEEP = ["reuters.com","apnews.com","who.int","afro.who.int","ecdc.europa.eu","cdc.gov","africacdc.org"]

def today(): return dt.datetime.utcnow().date().isoformat()
def load_json(path: Path, default: Any):
    try: return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception: return default
def save_json(path: Path, obj: Any):
    path.parent.mkdir(exist_ok=True); path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
def fetch(url: str, timeout: int = 25) -> Optional[str]:
    try:
        r=requests.get(url, timeout=timeout, headers={"User-Agent":"BDBV-dashboard-who-only-monitor/1.0","Accept":"text/html,application/json;q=0.9,*/*;q=0.8"})
        r.raise_for_status(); return r.text
    except Exception as e:
        print(f"[WARN] fetch failed: {url} ({e})", file=sys.stderr); return None
def clean_text(raw: str) -> str:
    try:
        soup=BeautifulSoup(raw,"html.parser")
        for tag in soup(["script","style","noscript"]): tag.decompose()
        txt=soup.get_text(" ")
    except Exception: txt=raw
    return re.sub(r"\s+"," ",html.unescape(txt)).strip()
def fetch_gdelt_news() -> List[Dict[str, Any]]:
    url="https://api.gdeltproject.org/api/v2/doc/doc?"+f"query={quote(QUERY)}&mode=artlist&format=json&maxrecords=40&sort=hybridrel"
    raw=fetch(url, timeout=30)
    if not raw: return []
    try: payload=json.loads(raw)
    except Exception: return []
    rows=[]
    for a in payload.get("articles",[])[:40]:
        title=a.get("title") or ""; link=a.get("url") or ""; domain=a.get("domain") or ""
        if not title or not link: continue
        if MEDIA_DOMAINS_TO_KEEP and not any(d in domain for d in MEDIA_DOMAINS_TO_KEEP): continue
        seen=a.get("seendate") or ""; date=seen[:8] if seen else today().replace("-","")
        date=f"{date[:4]}-{date[4:6]}-{date[6:8]}" if len(date)==8 and date.isdigit() else today()
        status="who_signal" if ("who.int" in domain or "afro.who.int" in domain) else "media_pending"
        rows.append({"date":date,"title":title,"source":domain or "GDELT","url":link,"summary":"自动抓取新闻/官方线索；媒体来源不进入正式 WHO-only 曲线。","status":status})
    return rows
def merge_by_url(existing, new_rows, keep=60):
    by_url={}
    for row in existing+new_rows:
        if row.get("url"): by_url[row["url"]]=row
    rows=list(by_url.values()); rows.sort(key=lambda r:r.get("date",""), reverse=True); return rows[:keep]
def build_candidates(news_rows):
    candidates=[]
    for src in WHO_SOURCES:
        raw=fetch(src["url"])
        relevant=False
        if raw:
            text=clean_text(raw).lower()
            relevant=any(k in text for k in ["bundibugyo","ebola","congo","uganda","drc"])
        candidates.append({"date":today(),"source":src["name"],"source_type":src["source_type"],"url":src["url"],"cases":None,"deaths":None,"recovered":None,"confidence":"source_watch","score":None,"warnings":["index_page","manual_review_required","no_numeric_auto_extraction"],"status":"who_candidate_source","note":src["note"]+(" 页面包含相关关键词。" if relevant else " 暂未识别到明确相关关键词。")})
        time.sleep(0.5)
    for n in news_rows[:30]:
        source=n.get("source","")
        status="who_candidate" if ("who.int" in source or "afro.who.int" in source) else "media_candidate"
        warnings=["manual_review_required"] + ([] if status=="who_candidate" else ["media_source","not_who_official","do_not_use_in_formal_timeseries"])
        candidates.append({"date":n.get("date") or today(),"source":source,"source_type":"who_or_media_signal","url":n.get("url"),"cases":None,"deaths":None,"recovered":None,"confidence":"signal_only","score":None,"warnings":warnings,"status":status,"note":n.get("title") or "自动抓取线索，需人工复核。"})
    return candidates
def main():
    DATA_DIR.mkdir(exist_ok=True)
    existing_news=load_json(NEWS, [])
    gdelt_news=fetch_gdelt_news()
    merged_news=merge_by_url(existing_news, gdelt_news)
    save_json(NEWS, merged_news)
    old_candidates=load_json(CANDIDATES, [])
    new_candidates=build_candidates(gdelt_news)
    merged_candidates=merge_by_url(old_candidates, new_candidates, keep=100)
    save_json(CANDIDATES, merged_candidates)
    print(json.dumps({"date":today(),"mode":"WHO-only formal data","news_added_or_kept":len(merged_news),"candidates_added_or_kept":len(merged_candidates),"timeseries_auto_append":False,"formal_timeseries_source":"data/timeseries.json; WHO/WHO AFRO only; manual update required"}, ensure_ascii=False, indent=2))
if __name__=="__main__": main()
