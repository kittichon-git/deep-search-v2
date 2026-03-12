import os
import requests
import json
import hashlib
from datetime import datetime
from dotenv import load_dotenv

from database import (
    get_search_settings,
    get_global_excludes,
    get_province_groups,
    insert_auction,
    insert_search_setting
)

load_dotenv()
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

def generate_hash_id(link, title, snippet):
    raw = f"{link}|{title}|{snippet}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

def ensure_templates_exist():
    settings = get_search_settings()
    if not settings:
        # Default templates for cold start
        DEFAULT_TEMPLATES = [
            '("พัสดุชำรุดเสื่อมสภาพ" OR "เสื่อมสภาพจนไม่สามารถใช้งานได้") "ขายทอดตลาด" ${YEAR_ANCHOR} filetype:pdf',
            '"ไม่จำเป็นต้องใช้ในราชการ" ("พัสดุ" OR "ครุภัณฑ์") ${YEAR_ANCHOR} filetype:pdf',
            '("องค์การบริหารส่วนจังหวัด" OR "อบจ") "ขายทอดตลาด" ("พัสดุ" OR "ครุภัณฑ์") ${YEAR_ANCHOR}',
            '("องค์การบริหารส่วนตำบล" OR "อบต") "ขายทอดตลาด" ("พัสดุ" OR "ครุภัณฑ์") ${YEAR_ANCHOR}'
        ]
        print("No templates found — seeding defaults...")
        for tpl in DEFAULT_TEMPLATES:
            insert_search_setting(tpl, ["any"])
        return get_search_settings()
    return settings

import urllib.request
import urllib.parse

def perform_search(query_str, tbs):
    """
    Call Serper.dev API to fetch up to 100 results.
    We use a pagination loop (up to 10 pages) because some server regions
    (like GitHub Actions) may restrict Google results to 10 per page
    even if num=100 is requested.
    """
    if not SERPER_API_KEY or SERPER_API_KEY == 'your_serper_api_key_here':
        print("  ! SERPER_API_KEY is missing or not set in .env")
        return []

    url = "https://google.serper.dev/search"
    all_results = []
    
    for page in range(1, 11):  # Pages 1 to 10
        payload = json.dumps({
            "q": query_str,
            "tbs": tbs if tbs != "any" else "",
            "gl": "th",
            "hl": "th",
            "num": 100,
            "page": page
        })
        headers = {
            'X-API-KEY': SERPER_API_KEY,
            'Content-Type': 'application/json'
        }
        
        try:
            req = urllib.request.Request(url, data=payload.encode('utf-8'), headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=30) as response:
                response_data = response.read().decode('utf-8')
                data = json.loads(response_data)
                
            organic = data.get("organic", [])
            if organic:
                all_results.extend(organic)
                
            # If we received fewer than 10 results in this chunk, we've likely hit the end
            if len(organic) < 10:
                break
                
        except Exception as e:
            print(f"  ! Error during API request (page {page}): {e}")
            break
            
    # Deduplicate results by link if any overlaps occurred
    seen = set()
    unique_results = []
    for r in all_results:
        if r.get("link") not in seen:
            seen.add(r.get("link"))
            unique_results.append(r)
            
    return unique_results[:100]



def main():
    print(f"=== Dynamic Search started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")

    # 1. Fetch Province Groups from DB
    prov_groups = get_province_groups()
    replacements = {
        "${YEAR_ANCHOR}": "(2568 OR 2569)",
        "${LOCAL_DOMINANCE_EXCLUDES}": "-อบต -เทศบาล",
    }
    for pg in prov_groups:
        # Format key as ${PROVINCES_...} based on display name or match existing templates
        # Using a simple mapping or just matching by group_name if it matches the pattern
        key = f"${{{pg['group_name']}}}" # e.g. ${ภาคเหนือ}
        # Backward compatibility for old tags
        legacy_map = {
            "ภาคเหนือ": "${PROVINCES_NORTH}",
            "ภาคอีสาน": "${PROVINCES_NE}",
            "ภาคกลาง": "${PROVINCES_CENTRAL}",
            "ภาคตะวันออก": "${PROVINCES_EAST}",
            "ภาคตะวันตก": "${PROVINCES_WEST}",
            "ภาคใต้": "${PROVINCES_SOUTH}"
        }
        replacements[key] = pg['provinces']
        if pg['group_name'] in legacy_map:
            replacements[legacy_map[pg['group_name']]] = pg['provinces']

    # 2. Fetch Global Excludes
    all_excludes = get_global_excludes()
    
    settings = ensure_templates_exist()
    total_found = total_new = 0

    for setting in settings:
        template = setting['template']
        time_filters = setting.get('time_filters') or ['any']
        selected_groups = setting.get('exclude_groups') or []

        # Replace placeholders
        query = template
        for k, v in replacements.items():
            if k in query:
                wrap = f"({v})" if "OR" in v else v
                query = query.replace(k, wrap)

        # Append selected exclude groups
        exclude_parts = []
        for exc in all_excludes:
            if exc.get('group_name') in selected_groups or (not selected_groups and exc.get('group_name') == 'ค่าเริ่มต้น'):
                exclude_parts.append(exc['exclude_text'])
        
        exclude_str = " ".join(exclude_parts)
        final_query = f"{query} {exclude_str}".strip()

        for tf in time_filters:
            tbs_val = "qdr:d" if tf == "1d" else ("qdr:w" if tf == "7d" else "any")
            print(f"\nSearching [{tf}]: {final_query[:85]}...")

            results = perform_search(final_query, tbs_val)
            print(f"  → Got {len(results)} results")

            for res in results:
                total_found += 1
                title, link, snippet = res.get('title',''), res.get('link',''), res.get('snippet','')
                
                data = {
                    "id": generate_hash_id(link, title, snippet),
                    "title": title, "link": link, "snippet": snippet,
                    "search_term": template, "time_filter": tf, "is_read": False
                }
                if insert_auction(data):
                    total_new += 1

    print(f"\n=== Done. Found {total_found} total, inserted {total_new} new items ===")

if __name__ == "__main__":
    main()
