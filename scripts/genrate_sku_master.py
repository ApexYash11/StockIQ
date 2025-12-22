import pandas as pd

skus = [
    ("TS-BLK-S", "Black T-Shirt S", "TShirt", 240, 699, "VendorA", 10, 100, 40),
    ("TS-BLK-M", "Black T-Shirt M", "TShirt", 250, 699, "VendorA", 10, 100, 50),
    ("TS-BLK-L", "Black T-Shirt L", "TShirt", 260, 699, "VendorA", 10, 100, 50),
    ("TS-WHT-M", "White T-Shirt M", "TShirt", 245, 699, "VendorA", 10, 100, 45),
    ("HD-BLK-M", "Black Hoodie M", "Hoodie", 800, 1999, "VendorB", 20, 50, 30),
    ("HD-GRY-L", "Grey Hoodie L", "Hoodie", 820, 1999, "VendorB", 20, 50, 30),
    ("JK-DNM-M", "Denim Jacket M", "Jacket", 1200, 2999, "VendorC", 25, 40, 20),
    ("CP-BLK", "Black Cap", "Accessory", 150, 499, "VendorD", 7, 200, 60),
]

df = pd.DataFrame(skus, columns=[
    "sku_id", "product_name", "category",
    "cost_price", "selling_price", "vendor",
    "lead_time_days", "MOQ", "safety_stock"
])

df.to_csv("Data/sku_master.csv", index=False)
print("SKU master generated with 8 SKUs")
