import pandas as pd
df = pd.read_csv("artifacts/weekly_forecast_future.csv")
print(df["week"].min(), df["week"].max())
print(df.head(5).to_string(index=False))