import datetime
import numpy as np
from tqdm import tqdm
from typing import Callable, List, Tuple

if __name__ == "__main__":
    import pandas as pd  # type: ignore

    storage_formats: List[Tuple[str, Callable[[pd.DataFrame], None], Callable[[], pd.DataFrame]]] = [
        ("hdf", lambda df: df.to_hdf("test.fixed.hdf", "test", mode="w"), lambda: pd.read_hdf("test_fixed.hdf", "test")), # type: ignore
        #("feather", lambda df: df.to_feather("test.feather"), lambda: pd.read_feather("test.feather")), # type: ignore
        #("parquet", lambda df: df.to_parquet("test.parquet"), lambda: pd.read_parquet("test.parquet")), # type: ignore
        ("pickle", lambda df: df.to_pickle("test.pkl"), lambda: pd.read_pickle("test.pkl")), # type: ignore
        ("excel", lambda df: df.to_excel("test.xlsx"), lambda: pd.read_excel("test.xlsx")), # type: ignore
    ]

    iterations = 10
    size = 100000

    np.random.seed(42)
    df = pd.DataFrame({"A": np.random.randn(size), "B": [1] * size})

    for format_name, dump, load in tqdm(storage_formats, total=len(storage_formats)):
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
