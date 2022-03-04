import datetime
import pandas as pd
import numpy as np
from tqdm import tqdm

storage_formats = [
    ("hdf", lambda df: df.to_hdf("test_fixed.hdf", "test", mode="w"), lambda: pd.read_hdf("test_fixed.hdf", "test")),
    #("feather", lambda df: df.to_feather("test.feather"), lambda: pd.read_feather("test.feather")),
    #("parquet", lambda df: df.to_parquet("test.parquet"), lambda: pd.read_parquet("test.parquet")),
    ("pickle", lambda df: df.to_pickle("test.pkl"), lambda: pd.read_pickle("test.pkl")),
    ("excel", lambda df: df.to_excel("test.xlsx"), lambda: pd.read_excel("test.xlsx")),
]

iterations = 10
size = 100000

np.random.seed(42)
df = pd.DataFrame({"A": np.random.randn(size), "B": [1] * size})

for format_name, dump, load in tqdm(storage_formats):
    dump_times = np.zeros(iterations)
    for i in tqdm(range(iterations), total=iterations):
        start = datetime.datetime.now()
        dump(df)
        stop = datetime.datetime.now()
        dump_times[i] = (stop - start).total_seconds() * 1000

    load_times = np.zeros(iterations)
    for i in tqdm(range(iterations), total=iterations):
        start = datetime.datetime.now()
        load()
        stop = datetime.datetime.now()
        load_times[i] = (stop - start).total_seconds() * 1000

    print(f"{format_name:<10s}: {np.mean(dump_times):.0f}ms +/- {np.std(dump_times):.0f}ms")
