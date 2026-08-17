#!/usr/bin/env python3
"""TRENTo observables from the per-event .dat grid files.

Grounded in a real run: each grid file starts with a header block written by TRENTo::

    # event 0
    # b     = 10.07057064
    # npart = 79
    # mult  = 29.43167861
    # e2    = 0.3376270323
    # e3    = ...

The per-event properties (multiplicity, eccentricities) are read from those header
lines -- the same table TRENTo prints to stdout. We average over all N.dat files.
Returns a dict; signals failure with {"error": ...} rather than raising.
"""
import os
import re

_HDR = re.compile(r"^#\s*([A-Za-z][\w]*)\s*=\s*([-+0-9.eE]+)")


def _event_files(out_dir):
    files = []
    for root, _dirs, names in os.walk(out_dir):
        for n in names:
            if re.fullmatch(r"\d+\.dat", n):
                files.append(os.path.join(root, n))
    return sorted(files)


def _read_header(path):
    """Return {b, npart, mult, e2, ...} parsed from the file's leading '# key = val'."""
    props = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.startswith("#"):
                break                       # header ends at the first grid row
            m = _HDR.match(line)
            if m:
                try:
                    props[m.group(1)] = float(m.group(2))
                except ValueError:
                    pass
    return props


def extract(observable, out_dir, analysis_dir):
    files = _event_files(out_dir)
    if not files:
        return {"error": "no <n>.dat event files found in %s" % out_dir}
    key = observable if observable in ("mult", "npart", "b", "e2", "e3", "e4", "e5") else "mult"
    vals = []
    for f in files:
        props = _read_header(f)
        if key in props:
            vals.append(props[key])
    if not vals:
        return {"error": "no '%s' in event headers under %s" % (key, out_dir)}
    n = len(vals)
    mean = sum(vals) / n
    result = {
        "observable": observable,
        "values": {"n_events": n, "mean_%s" % key: mean,
                   "min_%s" % key: min(vals), "max_%s" % key: max(vals)},
        "source": out_dir,
    }

    os.makedirs(analysis_dir, exist_ok=True)
    plot = os.path.join(analysis_dir, "%s_hist.png" % key)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.hist(vals, bins=min(20, max(3, n)))
        ax.set_xlabel(key); ax.set_ylabel("events")
        ax.set_title("TRENTo %s (mean=%.4g, N=%d)" % (key, mean, n))
        fig.savefig(plot, dpi=140, bbox_inches="tight")
        plt.close(fig)
        result["plot"] = plot
    except Exception as exc:                 # plotting is best-effort
        result["plot"] = None
        with open(os.path.join(analysis_dir, "plot_error.txt"), "w") as f:
            f.write(str(exc))
    return result
