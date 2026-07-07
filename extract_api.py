"""
extract_api.py
==================================================================
SECONDARY / OPTIONAL extraction via the live Open Food Facts API.

Use this to SHOW you can consume a REST API (pagination, rate-limiting,
a proper User-Agent, error handling). Do NOT use it to pull the full 20k+
rows: Open Food Facts limits search to ~10 requests/minute and asks you to
use the data export (extract_parquet.py) for anything beyond a few hundred
products. Hammering the API risks an IP ban.

This script pulls a capped sample per country and writes a CSV with the
SAME columns as extract_parquet.py, so the two are interchangeable.
==================================================================
"""

import time
import requests
import pandas as pd

# >>> CHANGE THIS to a real contact email. OFF asks every app to identify
#     itself; requests without a custom User-Agent can be blocked. <<<
USER_AGENT = "IronhackCapstone/1.0 (your-email@example.com)"

SEARCH_URL = "https://world.openfoodfacts.org/api/v2/search"

COUNTRIES = {  # display name : value OFF expects in countries_tags_en
    "Germany": "Germany",
    "United Kingdom": "United Kingdom",
    "France": "France",
    "Italy": "Italy",
    "Spain": "Spain",
    "Netherlands": "Netherlands",
    "Switzerland": "Switzerland",
    "Poland": "Poland",
    "Belgium": "Belgium",
    "Sweden": "Sweden",
}

FIELDS = ",".join([
    "code", "product_name", "brands", "countries_tags",
    "nutriscore_grade", "nutriscore_score", "nova_group",
    "environmental_score_grade", "additives_n", "completeness",
    "last_modified_t", "nutriments",
])

PAGE_SIZE = 100      # max OFF reliably returns per search page
MAX_PAGES = 5        # 5 pages x 100 = up to 500 products PER country (a sample!)
SLEEP_SECONDS = 6.5  # stay under the 10 requests/minute search limit


def fetch_country(country_value: str) -> list[dict]:
    rows = []
    for page in range(1, MAX_PAGES + 1):
        params = {
            "countries_tags_en": country_value,
            "fields": FIELDS,
            "page_size": PAGE_SIZE,
            "page": page,
        }
        try:
            r = requests.get(
                SEARCH_URL, params=params,
                headers={"User-Agent": USER_AGENT}, timeout=30,
            )
            if r.status_code == 429 or r.status_code == 503:
                print(f"    rate-limited (HTTP {r.status_code}); waiting 30s...")
                time.sleep(30)
                continue
            r.raise_for_status()
            products = r.json().get("products", [])
        except requests.RequestException as e:
            print(f"    request failed on page {page}: {e}")
            break

        if not products:
            break
        rows.extend(products)
        print(f"    page {page}: {len(products)} products (running total {len(rows)})")
        time.sleep(SLEEP_SECONDS)  # be polite
    return rows


def flatten(prod: dict, country_name: str) -> dict:
    n = prod.get("nutriments", {}) or {}
    name = prod.get("product_name")
    if isinstance(name, list):           # some responses give a list of langs
        name = name[0].get("text") if name else None
    return {
        "code": prod.get("code"),
        "product_name": name,
        "brands": prod.get("brands"),
        "country": country_name,
        "nutriscore_grade": prod.get("nutriscore_grade"),
        "nutriscore_score": prod.get("nutriscore_score"),
        "nova_group": prod.get("nova_group"),
        "eco_grade": prod.get("environmental_score_grade"),
        "additives_n": prod.get("additives_n"),
        "energy_kcal_100g": n.get("energy-kcal_100g"),
        "sugars_100g": n.get("sugars_100g"),
        "fat_100g": n.get("fat_100g"),
        "saturated_fat_100g": n.get("saturated-fat_100g"),
        "salt_100g": n.get("salt_100g"),
        "sodium_100g": n.get("sodium_100g"),
        "proteins_100g": n.get("proteins_100g"),
        "fiber_100g": n.get("fiber_100g"),
        "completeness": prod.get("completeness"),
        "last_modified_t": prod.get("last_modified_t"),
    }


def main():
    all_rows = []
    for display, value in COUNTRIES.items():
        print(f"Fetching {display}...")
        for prod in fetch_country(value):
            all_rows.append(flatten(prod, display))

    df = pd.DataFrame(all_rows)
    df = df[df["product_name"].notna() & (df["product_name"].str.strip() != "")]
    df = df.drop_duplicates(subset=["code", "country"]).reset_index(drop=True)

    import os
    os.makedirs("data", exist_ok=True)
    out = "data/products_europe_api_sample.csv"
    df.to_csv(out, index=False)
    print(f"\n{len(df):,} rows written -> {out}")
    print("Rows per country:\n" + df["country"].value_counts().to_string())
    print("\nThis is a SAMPLE. For the full 20k+ dataset, run extract_parquet.py.")


if __name__ == "__main__":
    main()
