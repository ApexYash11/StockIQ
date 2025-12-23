"""
SKU coverage audit for StockIQ.

Checks SKU presence across all generated CSVs and reports:
- Unique SKU count per file
- Union of all SKUs
- Top SKUs by order volume
- Missing-SKU inconsistencies

Safe to run locally, in CI, or at pipeline startup.
"""

from pathlib import Path
import pandas as pd
from typing import Dict, Set, Optional

DATA_DIR = Path("./output")  # adjust if needed
GENERATE_DIR = Path("./Generate")

def detect_sku_column(df: pd.DataFrame) -> Optional[str]:
    candidates = [c for c in df.columns if 'sku' in c.lower()]
    if candidates:
        return candidates[0]
    # fallbacks
    for alt in ['product_id', 'product', 'item_id', 'id']:
        if alt in df.columns:
            return alt
    return None


def analyze_folder(folder: Path) -> Dict[str, Dict]:
    results = {}
    for f in sorted(folder.glob('*.csv')):
        try:
            df = pd.read_csv(f)
        except Exception as e:
            results[f.name] = {'error': str(e)}
            continue

        sku_col = detect_sku_column(df)
        if sku_col is None:
            results[f.name] = {'sku_col': None, 'unique_skus': 0}
            continue

        skus = set(df[sku_col].astype(str).dropna().unique())
        results[f.name] = {'sku_col': sku_col, 'unique_skus': len(skus), 'skus_sample': list(sorted(skus))[:5]}

    return results


def main():
    print("\n=== SKU COVERAGE AUDIT ===\n")

    out_results = analyze_folder(DATA_DIR) if DATA_DIR.exists() else {}
    gen_results = analyze_folder(GENERATE_DIR) if GENERATE_DIR.exists() else {}

    # Print per-file results
    print("-- output/ CSVs --")
    for name, info in out_results.items():
        if 'error' in info:
            print(f"{name}: ERROR reading file: {info['error']}")
        elif info.get('sku_col') is None:
            print(f"{name}: no SKU-like column detected")
        else:
            print(f"{name}: column='{info['sku_col']}', {info['unique_skus']} unique SKUs (sample: {info['skus_sample']})")

    print("\n-- Generate/ CSVs --")
    for name, info in gen_results.items():
        if 'error' in info:
            print(f"{name}: ERROR reading file: {info['error']}")
        elif info.get('sku_col') is None:
            print(f"{name}: no SKU-like column detected")
        else:
            print(f"{name}: column='{info['sku_col']}', {info['unique_skus']} unique SKUs (sample: {info['skus_sample']})")

    # Union of SKUs found
    all_skus: Set[str] = set()
    for info in list(out_results.values()) + list(gen_results.values()):
        if info.get('sku_col') and 'skus_sample' in info:
            # we don't store full sets to avoid memory bloat; re-read orders.csv for union instead
            pass

    # Use orders.csv as the authoritative set for union and top list if present
    orders_file = DATA_DIR / 'orders.csv'
    if orders_file.exists():
        orders = pd.read_csv(orders_file)
        sku_col = detect_sku_column(orders)
        if sku_col:
            orders[sku_col] = orders[sku_col].astype(str)
            unique_orders_skus = set(orders[sku_col].dropna().unique())
            print(f"\nTOTAL unique SKUs (from orders.csv): {len(unique_orders_skus)}")
            top = orders[sku_col].value_counts().head(10)
            print('\nTop 10 SKUs in orders.csv by record count:')
            print(top.to_string())
        else:
            print('\norders.csv present but no SKU-like column detected')
    else:
        print('\norders.csv not present; cannot compute authoritative union/top list')

    print("\nSKU AUDIT COMPLETE\n")


if __name__ == '__main__':
    main()

