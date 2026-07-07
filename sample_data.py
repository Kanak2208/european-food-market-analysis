"""
sample_data.py
==================================================================
The extraction pulled ~2.6M rows — far more than you need, and enough to
make MySQL loading and Tableau sluggish. This creates a balanced working
sample (up to PER_COUNTRY products per market) that's fast to work with.

- Reads:  data/products_europe.csv   (the full extract)
- Backs up the full extract once to data/products_europe_full.csv
- Writes: data/products_europe.csv   (overwritten with the sample)

Why balanced (equal-ish per country)?
  The project compares 10 markets. Equal group sizes keep those comparisons
  fair instead of letting France's 1.1M products dominate.

==================================================================
"""

import shutil
from pathlib import Path
import pandas as pd

PER_COUNTRY = 7000    # max products kept per country (~70k rows total)
SEED = 42              # fixed so sample is reproducible

DATA = Path("data")
FULL = DATA / "products_europe.csv"
BACKUP = DATA / "products_europe_full.csv"

# 1. Back up the full extract once, then always sample FROM the backup
if not BACKUP.exists():
    shutil.copy(FULL, BACKUP)
    print(f"Backed up full extract -> {BACKUP}")

df = pd.read_csv(BACKUP, dtype={"code": "string"})
print(f"Full extract: {len(df):,} rows")

# 2. Balanced per-country sample (keeps small countries whole)
parts = []
for country, g in df.groupby("country"):
    parts.append(g.sample(n=min(len(g), PER_COUNTRY), random_state=SEED))
sample = pd.concat(parts).reset_index(drop=True)

# 3. Overwrite the working file with the sample
sample.to_csv(FULL, index=False)

print(f"\nSample: {len(sample):,} rows  (written to {FULL})")
print("Rows per country:")
print(sample["country"].value_counts().to_string())
print("\nThe full extract is safe in products_europe_full.csv ")
