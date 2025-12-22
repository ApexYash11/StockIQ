import pandas as pd

data = [
    # Delhi NCR
    ("Delhi NCR", "Delhivery",    2.0, 0.92, 0.08, 65),
    ("Delhi NCR", "EcomExpress",  2.5, 0.88, 0.12, 60),
    ("Delhi NCR", "Xpressbees",   3.0, 0.85, 0.15, 55),

    # Mumbai
    ("Mumbai", "Delhivery",       2.5, 0.90, 0.10, 70),
    ("Mumbai", "EcomExpress",     3.0, 0.86, 0.14, 65),
    ("Mumbai", "Xpressbees",      3.5, 0.82, 0.18, 58),

    # Bangalore
    ("Bangalore", "Delhivery",    3.5, 0.85, 0.15, 75),
    ("Bangalore", "EcomExpress",  4.0, 0.80, 0.20, 68),
    ("Bangalore", "Xpressbees",   4.5, 0.76, 0.24, 60),
]

df = pd.DataFrame(data, columns=[
    "region",
    "courier",
    "avg_delivery_days",
    "COD_success_rate",
    "RTO_rate",
    "cost_per_shipment"
])

df.to_csv("Data/logistics_performance.csv", index=False)
print("Logistics performance data generated")
