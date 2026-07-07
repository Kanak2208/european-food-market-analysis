"""
extract_parquet.py
==================================================================
PRIMARY data extraction for the capstone (recommended for 20k+ rows).

Why Parquet and not the live API?
  Open Food Facts explicitly asks you NOT to pull more than a few hundred
  products through the API. For bulk data they publish a daily export.
  We read that export (Parquet on Hugging Face) with DuckDB, which lets us
  filter ~4.5M food products down to the European market with plain SQL and
  pull only the columns we need over the network.

Output:
  data/products_europe.csv        <- load this into Tableau / Power BI
  data/openfoodfacts.db (SQLite)  <- query this with SQL
==================================================================
"""

import os
import duckdb
import pandas as pd
from huggingface_hub import HfApi

# ------------------------------------------------------------------
# 1. CONFIG  — the 10 largest European economies (nominal GDP, 2025)
# ------------------------------------------------------------------
COUNTRY_TAGS = {
    "en:germany":        "Germany",
    "en:united-kingdom": "United Kingdom",
    "en:france":         "France",
    "en:italy":          "Italy",
    "en:spain":          "Spain",
    "en:netherlands":    "Netherlands",
    "en:switzerland":    "Switzerland",
    "en:poland":         "Poland",
    "en:belgium":        "Belgium",
    "en:sweden":         "Sweden",
}

OUT_DIR = "data"
CSV_PATH = os.path.join(OUT_DIR, "products_europe.csv")
#DB_PATH = os.path.join(OUT_DIR, "openfoodfacts.db")

os.makedirs(OUT_DIR, exist_ok=True)


# ------------------------------------------------------------------
# 2. Locate the FOOD Parquet files on Hugging Face at runtime.
#    (Discovering the paths beats hard-coding them — the repo layout
#     changes occasionally.)
# ------------------------------------------------------------------
def find_food_parquet_files() -> list[str]:
    repo = "openfoodfacts/product-database"
    files = HfApi().list_repo_files(repo, repo_type="dataset")
    food = [
        f for f in files
        if f.endswith(".parquet") and "food" in f.lower() and "beauty" not in f.lower()
    ]
    if not food:  # fallback: take every parquet (you can filter beauty out later)
        food = [f for f in files if f.endswith(".parquet")]
    urls = [f"hf://datasets/{repo}/{f}" for f in food]
    print(f"Found {len(urls)} food Parquet file(s) on Hugging Face.")
    return urls


# ------------------------------------------------------------------
# 3. Build the SQL. Nutrients live in a nested list-of-structs called
#    `nutriments`; this helper pulls one nutrient's per-100g value out.
# ------------------------------------------------------------------
def n100(name: str) -> str:
    return (
        "TRY_CAST(struct_extract("
        f"list_filter(nutriments, x -> x.name = '{name}')[1], '100g') AS DOUBLE)"
    )


def build_query(parquet_urls: list[str]) -> str:
    tag_list = ", ".join(f"'{t}'" for t in COUNTRY_TAGS)
    # DuckDB reads a Python list of paths if we inline it as a SQL list literal:
    files_sql = "[" + ", ".join(f"'{u}'" for u in parquet_urls) + "]"

    # map en:germany -> Germany inside SQL via a CASE expression
    case_when = "\n".join(
        f"      WHEN country_tag = '{tag}' THEN '{name}'"
        for tag, name in COUNTRY_TAGS.items()
    )

    return f"""
    WITH base AS (
        SELECT
            code,
            COALESCE(
                list_filter(product_name, x -> x.lang = 'main')[1].text,
                product_name[1].text
            )                                   AS product_name,
            brands,
            categories_tags,
            countries_tags,
            nutriscore_grade,
            nutriscore_score,
            nova_group,
            environmental_score_grade           AS eco_grade,
            additives_n,
            completeness,
            last_modified_t,
            {n100('energy-kcal')}               AS energy_kcal_100g,
            {n100('sugars')}                    AS sugars_100g,
            {n100('fat')}                       AS fat_100g,
            {n100('saturated-fat')}             AS saturated_fat_100g,
            {n100('salt')}                      AS salt_100g,
            {n100('proteins')}                  AS proteins_100g,
            {n100('fiber')}                     AS fiber_100g,
            {n100('sodium')}                    AS sodium_100g,
            -- keep only the European tags that matched
            list_filter(countries_tags, c -> c IN ({tag_list})) AS eu_tags
        FROM read_parquet({files_sql})
        -- keep a product only if it is sold in at least one of our 10 markets
        WHERE list_bool_or(list_transform(countries_tags, c -> c IN ({tag_list})))
    ),
    exploded AS (
        -- one row per (product, country): a product sold in 3 markets -> 3 rows
        SELECT *, unnest(eu_tags) AS country_tag
        FROM base
    )
    SELECT
        code,
        product_name,
        brands,
        CASE
{case_when}
        END                                     AS country,
        country_tag,
        nutriscore_grade,
        nutriscore_score,
        nova_group,
        eco_grade,
        additives_n,
        energy_kcal_100g,
        sugars_100g,
        fat_100g,
        saturated_fat_100g,
        salt_100g,
        sodium_100g,
        proteins_100g,
        fiber_100g,
        completeness,
        to_timestamp(last_modified_t)           AS last_modified
    FROM exploded
    """


# ------------------------------------------------------------------
# 4. Run it.
# ------------------------------------------------------------------
def main():
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")  # needed to read hf:// over HTTP

    urls = find_food_parquet_files()
    query = build_query(urls)

    print("Querying Open Food Facts (this pulls only the columns we need)...")
    df = con.execute(query).df()

    # Light hygiene: drop products with no usable name, de-dup exact repeats
    df = df[df["product_name"].notna() & (df["product_name"].str.strip() != "")]
    df = df.drop_duplicates(subset=["code", "country"]).reset_index(drop=True)

    print(f"\nTotal rows (product x country grain): {len(df):,}")
    print(f"Distinct products:                     {df['code'].nunique():,}")
    print("\nRows per country:")
    print(df["country"].value_counts().to_string())

    if len(df) < 20_000:
        print(
            "\n[!] Under 20k rows. Add more countries to COUNTRY_TAGS, or relax the "
            "name filter. France + Germany + UK + Spain + Italy alone usually clear it."
        )

    # ---- write outputs ----
    df.to_csv(CSV_PATH, index=False)
    print(f"\nCSV written  -> {CSV_PATH}")

#    import sqlite3
 #   with sqlite3.connect(DB_PATH) as sq:
  #      df.to_sql("products", sq, if_exists="replace", index=False)
   # print(f"SQLite written -> {DB_PATH}  (table: products)")
    print("\nDone. Load the CSV into Tableau/Power BI, query the .db with SQL.")


if __name__ == "__main__":
    main()
