"""Build data/ramen_shops.csv from Google Places (legacy Text Search).

Strategy for real variety in the categorical KB fields:
  - Per area, issue ONE query per broth type. The query term itself becomes
    the ground-truth label for the shop's broth (e.g. 'tonkotsu ramen in
    Shibuya' -> broth=tonkotsu for every shop returned by that call).
  - Per area, issue targeted queries for halal diet, spicy tantanmen, and
    jiro-style. Shops found via these queries get the corresponding tag.
  - Merge by place_id, first-seen wins for the labeled attribute, so the
    broth label is stable across re-runs.

Output schema matches the vocabulary expected by ramen_kb.pl:
  broth       = tonkotsu | shoyu | shio | miso | tsukemen | other
  richness    = light | medium | rich
  spice       = none | mild | spicy
  diet        = none | vegetarian | halal | veg_friendly
  ramen_type  = ramen | tsukemen | both
  jiro_style  = yes | no
  (etc. - see ramen_kb.pl lines 10-21)

Original location data (name, address, lat, lng) is preserved as extra
columns. app.py uses DictReader with explicit field names, so the extras
are ignored at KB-load time but remain useful for maps and human review.

Usage:
    export GOOGLE_MAPS_API_KEY=...
    python build_kb_csv.py [per_area]
"""

import csv
import json
import os
import random
import sys
import time
import urllib.parse
import urllib.request

API_KEY = os.environ["GOOGLE_MAPS_API_KEY"]
TEXT_SEARCH = "https://maps.googleapis.com/maps/api/place/textsearch/json"

AREAS = [
    "Shinjuku", "Shibuya", "Ginza", "Akihabara",
    "Ueno", "Shinagawa", "Roppongi", "Asakusa",
]

# Broth queries issued per area. Each query labels returned shops with
# (broth, ramen_type). 'other' isn't queried -- it's a fallback for shops
# found by non-broth queries that we can't confidently label.
BROTH_QUERIES = [
    ("tonkotsu ramen",  "tonkotsu",  "ramen"),
    ("shoyu ramen",     "shoyu",     "ramen"),
    ("miso ramen",      "miso",      "ramen"),
    ("shio ramen",      "shio",      "ramen"),
    ("tsukemen",        "tsukemen",  "tsukemen"),
]

# Per-area targeted queries for minority categorical values.
SPECIAL_QUERIES = [
    # (query suffix, tag dict)
    ("halal ramen",     {"diet": "halal"}),
    ("tantanmen ramen", {"spice": "spicy", "broth": "shoyu"}),
    ("ramen jiro",      {"jiro_style": "yes", "richness": "rich"}),
]

STATION = {a: f"{a.lower()} station" for a in AREAS}
NIGHTLIFE_AREAS = {"Shinjuku", "Shibuya", "Roppongi"}
LATE_NIGHT_CHAIN_HINTS = ("ichiran", "ippudo", "afuri")

CSV_FIELDS = [
    "shop_id", "name", "address", "latitude", "longitude",
    "area", "station", "price_level", "broth", "richness",
    "spice", "diet", "open_late", "seating", "group_ok",
    "wait_level", "travel_band", "ramen_type", "jiro_style", "payment",
]


def http_get_json(url: str, params: dict) -> dict:
    q = urllib.parse.urlencode(params)
    with urllib.request.urlopen(f"{url}?{q}", timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def text_search(query: str) -> list[dict]:
    data = http_get_json(TEXT_SEARCH, {
        "query": query,
        "type": "restaurant",
        "language": "en",
        "region": "jp",
        "key": API_KEY,
    })
    if data.get("status") not in ("OK", "ZERO_RESULTS"):
        sys.stderr.write(f"[{query}] {data.get('status')} {data.get('error_message','')}\n")
        return []
    return data.get("results", [])


def atomize(s: str) -> str:
    s = s.strip().lower().replace("&", "and")
    s = "".join(ch if ch.isalnum() else "_" for ch in s)
    s = "_".join(p for p in s.split("_") if p)
    return s or "unknown"


def map_price(g_price) -> str:
    if g_price in (0, 1):
        return "low"
    if g_price in (3, 4):
        return "high"
    return "medium"


def infer_richness(broth: str, jiro: str) -> str:
    if jiro == "yes" or broth == "tonkotsu" or broth == "miso":
        return "rich"
    if broth == "shio":
        return "light"
    return "medium"


def infer_spice_default(name_lc: str) -> str:
    if any(k in name_lc for k in ("spicy", "mala", "tantanmen", "tantan", "karashi", "dandan")):
        return "spicy"
    if "chili" in name_lc:
        return "mild"
    return "none"


def infer_diet_default(name_lc: str) -> str:
    if "halal" in name_lc:
        return "halal"
    if "vegan" in name_lc or "vegetarian" in name_lc:
        return "vegetarian"
    return "none"


def infer_open_late(area: str, name_lc: str) -> str:
    if any(c in name_lc for c in LATE_NIGHT_CHAIN_HINTS):
        return "yes"
    return "yes" if area in NIGHTLIFE_AREAS else "no"


def infer_wait(ratings_total: int, rating: float) -> str:
    if ratings_total >= 4000 and rating >= 4.2:
        return "long"
    if ratings_total >= 1200:
        return "medium"
    return "short"


def infer_payment(rating_count: int, price_level: str) -> str:
    if price_level in ("medium", "high") or rating_count >= 1500:
        return "card_ok"
    return "cash_only"


def infer_jiro_name(name_lc: str) -> str:
    return "yes" if "jiro" in name_lc else "no"


def collect_places() -> dict:
    """Run all targeted queries; return {place_id: (google_place, tags)}.

    `tags` is a dict of ground-truth category labels derived from whichever
    query first surfaced this place. First-seen wins, so results are stable
    across runs.
    """
    store: dict[str, tuple[dict, str, dict]] = {}

    def absorb(place: dict, area: str, tags: dict):
        pid = place.get("place_id")
        if not pid:
            return
        types = set(place.get("types") or [])
        if not (types & {"restaurant", "food", "meal_takeaway", "meal_delivery"}):
            return
        if pid in store:
            return  # first-seen wins
        store[pid] = (place, area, tags)

    # Broth queries per area.
    for area in AREAS:
        for q_suffix, broth, rtype in BROTH_QUERIES:
            results = text_search(f"{q_suffix} in {area}, Tokyo")
            tags = {"broth": broth, "ramen_type": rtype}
            for p in results:
                absorb(p, area, tags)
            time.sleep(0.15)

    # Targeted per-area queries for minority categorical values.
    for area in AREAS:
        for q_suffix, extra in SPECIAL_QUERIES:
            results = text_search(f"{q_suffix} in {area}, Tokyo")
            for p in results:
                absorb(p, area, dict(extra))
            time.sleep(0.15)

    print(f"  collected {len(store)} unique places across {len(AREAS)} areas", flush=True)
    return store


def weighted(rng: random.Random, choices: list[tuple[str, float]]) -> str:
    """Return one option sampled by weight. `choices` is [(value, weight), ...]."""
    total = sum(w for _, w in choices)
    roll = rng.random() * total
    acc = 0.0
    for val, w in choices:
        acc += w
        if roll <= acc:
            return val
    return choices[-1][0]


def build_row(place: dict, area: str, tags: dict) -> dict:
    """Fabricate a KB row for this shop.

    Ground truth is used where available:
      - name/address/lat/lng: Google Places response
      - broth / ramen_type: from the query that first surfaced the shop
      - diet / spice / jiro_style: respected when a targeted query tagged them
      - wait_level: derived from Google's user_ratings_total

    Remaining categorical fields (seating, group_ok, payment, sometimes
    price_level and spice) are filled by a seeded weighted sampler so the
    KB has realistic diversity and a recommender can actually discriminate.
    The seed is the shop_id, so the output is deterministic across runs.
    """
    name = place.get("name", "")
    name_lc = name.lower()
    geom = (place.get("geometry") or {}).get("location") or {}
    shop_id = atomize(name)
    rng = random.Random(shop_id)

    # Price_level: if Google knows, trust it; otherwise sample.
    g_price = place.get("price_level")
    if g_price is not None:
        price_level = map_price(g_price)
    else:
        price_level = weighted(rng, [("low", 0.30), ("medium", 0.55), ("high", 0.15)])

    rating = float(place.get("rating") or 0)
    ratings_total = int(place.get("user_ratings_total") or 0)

    broth = tags.get("broth", "other")
    ramen_type_base = tags.get("ramen_type", "ramen")
    # Some ramen shops also serve tsukemen -- sample a few 'both'.
    ramen_type = weighted(rng, [(ramen_type_base, 0.78), ("both", 0.22)])
    diet = tags.get("diet") or infer_diet_default(name_lc)
    # Spice: honour explicit tag; name-based hits; otherwise sample.
    spice = tags.get("spice") or infer_spice_default(name_lc)
    if spice == "none":
        spice = weighted(rng, [("none", 0.70), ("mild", 0.20), ("spicy", 0.10)])
    jiro = tags.get("jiro_style") or infer_jiro_name(name_lc)
    if jiro == "no":
        jiro = weighted(rng, [("no", 0.92), ("yes", 0.08)])
    richness = tags.get("richness") or infer_richness(broth, jiro)

    # Seating, group_ok, payment: no reliable signal from Google -- sample.
    seating = weighted(rng, [("bar", 0.55), ("both", 0.30), ("table", 0.15)])
    group_ok = weighted(rng, [("solo", 0.25), ("small", 0.55), ("group", 0.20)])
    payment = weighted(rng, [("card_ok", 0.72), ("cash_only", 0.28)])

    return {
        "shop_id": shop_id,
        "name": name,
        "address": place.get("formatted_address", ""),
        "latitude": geom.get("lat", ""),
        "longitude": geom.get("lng", ""),
        "area": atomize(area),
        "station": atomize(STATION[area]),
        "price_level": price_level,
        "broth": broth,
        "richness": richness,
        "spice": spice,
        "diet": diet,
        "open_late": infer_open_late(area, name_lc),
        "seating": seating,
        "group_ok": group_ok,
        "wait_level": infer_wait(ratings_total, rating),
        "travel_band": "near",
        "ramen_type": ramen_type,
        "jiro_style": jiro,
        "payment": payment,
    }


def pick_per_area(rows: list[dict], per_area: int) -> list[dict]:
    """Select up to `per_area` rows per area, prioritising broth diversity.

    We cycle through broths per area so the output has a balanced mix rather
    than e.g. all-tonkotsu in one neighbourhood just because tonkotsu queries
    returned the most results first.
    """
    by_area: dict[str, list[dict]] = {}
    for r in rows:
        by_area.setdefault(r["area"], []).append(r)

    picked: list[dict] = []
    for area, area_rows in by_area.items():
        buckets: dict[str, list[dict]] = {}
        for r in area_rows:
            buckets.setdefault(r["broth"], []).append(r)
        broth_order = ["tonkotsu", "shoyu", "miso", "shio", "tsukemen", "other"]
        chosen: list[dict] = []
        seen_ids: set[str] = set()
        # Round-robin through broths
        idx = 0
        while len(chosen) < per_area:
            progress = False
            for broth in broth_order:
                if len(chosen) >= per_area:
                    break
                bucket = buckets.get(broth, [])
                if idx < len(bucket):
                    r = bucket[idx]
                    if r["shop_id"] not in seen_ids:
                        chosen.append(r)
                        seen_ids.add(r["shop_id"])
                    progress = True
            if not progress:
                break
            idx += 1
        picked.extend(chosen)
    return picked


def main(per_area: int = 8, out_path: str = os.path.join("data", "ramen_shops.csv")) -> None:
    store = collect_places()
    all_rows = [build_row(p, area, tags) for (p, area, tags) in store.values()]

    # Dedup by shop_id within an area (two different place_ids could atomize
    # to the same shop_id for branches with identical names).
    seen: set[tuple[str, str]] = set()
    unique_rows = []
    for r in all_rows:
        key = (r["area"], r["shop_id"])
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(r)

    picked = pick_per_area(unique_rows, per_area)
    picked.sort(key=lambda r: (r["area"], r["broth"], r["shop_id"]))

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(picked)

    print(f"\nWrote {len(picked)} rows -> {out_path}")


if __name__ == "__main__":
    per = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    main(per_area=per)
