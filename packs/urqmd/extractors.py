#!/usr/bin/env python3
"""URQMD afterburner observables from the custom output particle file.

Format: per-event header `# event n particles m`, then particle lines
`id charge mass px py pz t x y z` (verified against the osc2u+urqmd ftn30 output;
columns 3-5 are the Cartesian momentum, NOT pT/phi/eta). pT, phi and pseudo-
rapidity eta are computed from (px, py, pz). Computes charged dN/deta and v2{2}
(two-particle Q-cumulant). Returns a dict; signals failure with {"error": ...}
rather than raising, so the launcher records a graceful blocker (not a crash).
"""
import math
import os


def _find(out_dir, name="particles_out.dat"):
    cand = os.path.join(out_dir, name)
    if os.path.isfile(cand) and os.path.getsize(cand) > 0:
        return cand
    for root, _dirs, files in os.walk(out_dir):
        if name in files:
            p = os.path.join(root, name)
            if os.path.getsize(p) > 0:
                return p
    return None


def _pseudorapidity(px, py, pz):
    """eta = 0.5 ln((|p|+pz)/(|p|-pz)); guard the collinear/degenerate cases."""
    p = math.sqrt(px * px + py * py + pz * pz)
    if p <= abs(pz) or p == 0.0:
        return math.copysign(20.0, pz)          # ~beam rapidity sentinel
    return 0.5 * math.log((p + pz) / (p - pz))


def _parse(path):
    """Yield per-event lists of (charge, phi, eta) derived from the Cartesian
    momentum columns `id charge mass px py pz ...`."""
    events = []
    cur = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                cur = []
                events.append(cur)
                continue
            parts = line.split()
            if len(parts) < 6 or cur is None:
                continue
            try:
                charge = int(float(parts[1]))
                px, py, pz = float(parts[3]), float(parts[4]), float(parts[5])
            except ValueError:
                continue
            phi = math.atan2(py, px)
            eta = _pseudorapidity(px, py, pz)
            cur.append((charge, phi, eta))
    return events


def extract(observable, out_dir, analysis_dir):
    path = _find(out_dir)
    if path is None:
        return {"error": "particles_out.dat not found or empty in %s" % out_dir}
    events = _parse(path)
    if not events:
        return {"error": "no events parsed from %s" % path}

    # charged dN/deta
    nbins, lo, hi = 40, -5.0, 5.0
    width = (hi - lo) / nbins
    counts = [0.0] * nbins
    n_charged = 0
    # v2{2} two-particle Q-cumulant, averaged over events weighted by M(M-1)
    num = den = 0.0
    for ev in events:
        charged = [(phi, eta) for (q, phi, eta) in ev if q != 0]
        n_charged += len(charged)
        for _phi, eta in charged:
            if lo <= eta < hi:
                counts[int((eta - lo) / width)] += 1
        M = len(charged)
        if M >= 2:
            qx = sum(math.cos(2 * phi) for phi, _ in charged)
            qy = sum(math.sin(2 * phi) for phi, _ in charged)
            two = (qx * qx + qy * qy - M) / (M * (M - 1))
            num += two * M * (M - 1)
            den += M * (M - 1)
    n_events = len(events)
    dNdeta = [c / n_events / width for c in counts]
    c2 = (num / den) if den > 0 else 0.0
    v2 = math.sqrt(c2) if c2 > 0 else 0.0

    os.makedirs(analysis_dir, exist_ok=True)
    plot = os.path.join(analysis_dir, "dNchdeta.png")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        centers = [lo + (i + 0.5) * width for i in range(nbins)]
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(centers, dNdeta, marker="o", ms=3)
        ax.set_xlabel("eta"); ax.set_ylabel("dN_ch/deta")
        ax.set_title("URQMD charged dN/deta (v2{2}=%.4f)" % v2)
        fig.savefig(plot, dpi=140, bbox_inches="tight")
        plt.close(fig)
    except Exception as exc:                     # plotting is best-effort
        plot = None
        with open(os.path.join(analysis_dir, "plot_error.txt"), "w") as f:
            f.write(str(exc))

    return {
        "observable": observable,
        "values": {"n_events": n_events, "n_charged": n_charged,
                   "dNdeta_peak": max(dNdeta) if dNdeta else 0.0, "v2": v2},
        "plot": plot,
        "source": path,
    }
