"""CLVisc observable extractors (pack code; model knowledge lives here, not in engine)."""
import glob
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_LOCATORS = {
    "dNchdeta": {"file": "dNdEta_mc_charged.dat"},
    "v2": {"file": "vn_mc_charged.dat", "column": 2},
}


def _find(run_dir, name):
    hits = glob.glob(os.path.join(run_dir, "**", name), recursive=True)
    return hits[0] if hits else None


def extract(observable, run_dir, out_dir):
    loc = _LOCATORS.get(observable)
    if not loc:
        return {"observable": observable, "error": "unknown observable"}
    path = _find(run_dir, loc["file"])
    if not path:
        return {"observable": observable, "error": f"{loc['file']} not found"}
    data = np.loadtxt(path)
    os.makedirs(out_dir, exist_ok=True)
    if observable == "dNchdeta":
        eta, val = data[:, 0], data[:, 1]
        i = int(np.argmin(np.abs(eta)))
        png = os.path.join(out_dir, "dNchdeta.png")
        plt.figure()
        plt.plot(eta, val, "o-")
        plt.xlabel("eta")
        plt.ylabel("dNch/deta")
        plt.savefig(png)
        plt.close()
        return {"observable": observable, "values": {"eta0": float(val[i])}, "plot": png}
    # v2(pT)
    pt, v2 = data[:, 0], data[:, loc["column"]]
    png = os.path.join(out_dir, "v2_pt.png")
    plt.figure()
    plt.plot(pt, v2, "o-")
    plt.xlabel("pT")
    plt.ylabel("v2")
    plt.savefig(png)
    plt.close()
    return {"observable": observable, "values": {"v2_pt": [float(x) for x in v2]}, "plot": png}


def fit(scan_results, param, observable, out_dir):
    xs = [r[param] for r in scan_results]
    ys = [r[observable] for r in scan_results]
    if len(xs) < 2:
        return {"param": param, "observable": observable, "poly_coeffs": [], "plot": None}
    coeffs = np.polyfit(xs, ys, min(2, len(xs) - 1))
    return {"param": param, "observable": observable,
            "poly_coeffs": [float(c) for c in coeffs], "plot": None}
