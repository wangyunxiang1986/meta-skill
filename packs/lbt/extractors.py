"""LBT observable extractors (pack code; model knowledge lives here, not in engine).

The T2 observable is the parton-level transverse-momentum spectrum dN/dpT computed
with LBT's correct positive/negative bookkeeping:

    dN/dpT(bin) = [ N_positive(bin) - N_negative(bin) ] / bin_width

``positive.dat`` (cols ``id px py pz E x y z t CAT``) are the jet+medium-response
partons; ``negative.dat`` (cols ``id px py pz E x y z t``) are the recoil "holes"
that must be SUBTRACTED bin-by-bin to remove the thermal background the jet
displaced. Lines starting with ``#`` are ``# event_id count`` separators. This is
still parton-level (FastJet-free, no cross-section weighting) -- a physically
sound diagnostic, not the publication charged-hadron spectrum (that needs
hadronization + jet finding downstream).
"""
import glob
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_LOCATORS = {
    "dNdpT_parton": {"file": "positive.dat"},
}


def _find(run_dir, name):
    hits = glob.glob(os.path.join(run_dir, "**", name), recursive=True)
    return sorted(hits)[0] if hits else None


def _load_pt(path):
    """Return (pT array, n_events) for a parton record file.

    pT = sqrt(px^2 + py^2). ``# event_id count`` lines separate events; the
    event count is needed for per-event normalization so that scan points with
    different event counts stay comparable. A file with no separators is one
    event."""
    px, py, n_events = [], [], 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                n_events += 1
                continue
            parts = s.split()
            if len(parts) < 5:
                continue
            try:
                px.append(float(parts[1]))
                py.append(float(parts[2]))
            except ValueError:
                continue
    px = np.asarray(px)
    py = np.asarray(py)
    return np.sqrt(px * px + py * py), max(n_events, 1)


def extract(observable, run_dir, out_dir):
    if observable not in _LOCATORS:
        return {"observable": observable, "error": "unknown observable"}
    pos_path = _find(run_dir, "positive.dat")
    if not pos_path:
        return {"observable": observable, "error": "positive.dat not found"}
    pt_pos, n_events = _load_pt(pos_path)
    if pt_pos.size == 0:
        return {"observable": observable, "error": "no positive parton rows parsed"}
    neg_path = _find(run_dir, "negative.dat")
    if neg_path:
        pt_neg, _ = _load_pt(neg_path)
    else:
        pt_neg = np.array([])

    os.makedirs(out_dir, exist_ok=True)
    pt_hi = max(20.0, float(np.percentile(pt_pos, 99)))
    edges = np.linspace(0.0, pt_hi, 41)
    centers = 0.5 * (edges[:-1] + edges[1:])
    widths = np.diff(edges)
    hp, _ = np.histogram(pt_pos, bins=edges)
    hn, _ = np.histogram(pt_neg, bins=edges) if pt_neg.size else (np.zeros_like(hp), edges)
    net = hp - hn                                   # positive minus negative (recoil holes)
    # per-event normalization: dN/dpT per event, comparable across scan points
    # with different event counts (e.g. an alphas scan changing ncall)
    dndpt_net = net / widths / n_events
    pos_mask = dndpt_net > 0                         # log axis: only physical (net>0) bins

    png = os.path.join(out_dir, "dNdpT_parton.png")
    plt.figure()
    plt.semilogy(centers[pos_mask], dndpt_net[pos_mask], "o-", label="net (pos - neg)")
    plt.semilogy(centers, np.maximum(hp / widths / n_events, 1e-12), "--", color="0.7",
                 label="positive only (ref)")
    plt.xlabel("pT [GeV]")
    plt.ylabel("(1/N_ev) dN/dpT (parton)")
    plt.title("LBT net parton pT spectrum (positive - negative)")
    plt.legend()
    plt.savefig(png)
    plt.close()
    values = {
        "n_events": int(n_events),
        "n_positive": int(pt_pos.size),
        "n_negative": int(pt_neg.size),
        "n_net": int(pt_pos.size - pt_neg.size),
        "net_per_event": float((pt_pos.size - pt_neg.size) / n_events),
        "pt_max": float(pt_pos.max()),
        "nonpositive_net_bins": int(np.sum(~pos_mask)),
    }
    if not neg_path:
        values["warning"] = ("negative.dat missing -- spectrum is positive-only, "
                             "NOT net-subtracted")
    return {
        "observable": observable,
        "values": values,
        "plot": png,
        "source": pos_path,
        "negative_source": neg_path,
    }


def fit(scan_results, param, observable, out_dir):
    xs = [r[param] for r in scan_results]
    ys = [r[observable] for r in scan_results]
    if len(xs) < 2:
        return {"param": param, "observable": observable, "poly_coeffs": [], "plot": None}
    coeffs = np.polyfit(xs, ys, min(2, len(xs) - 1))
    return {"param": param, "observable": observable,
            "poly_coeffs": [float(c) for c in coeffs], "plot": None}
