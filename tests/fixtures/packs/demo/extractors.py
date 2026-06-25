def extract(observable, run_dir, out_dir):
    return {"observable": observable, "values": [1.0], "plot": None}


def fit(scan_results, param, observable, out_dir):
    return {"trend": "flat", "plot": None}
