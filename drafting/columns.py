#!/usr/bin/env python3
"""Extract the column layout of an output file from an INDEPENDENT source of truth --
so a generated extractor can be checked against it, not against the LLM's own reading.

This is what makes "golden strong-verification" real rather than circular: if the
expected values were reasoned by the same model that wrote the parser, a column
mis-read (the URQMD py-as-phi / pz-as-eta bug) corrupts parser AND golden together and
the test still passes. Here the column->field map comes from the code the COMPILER
reads (the writer's `<<` chain) or from the file's OWN header -- neither depends on the
LLM's interpretation.

Three writer paradigms, in increasing difficulty:
  header_named   the output header lists column names (OSCAR2013)            -> read header
  header_kv      each observable is a `# key = value` line (TRENTo)           -> read header
  cpp_stream     column meaning lives only in the C++ `out << a << b << ...`   -> parse source
                 record write (LBT/URQMD -- headerless data, the risky case)

Returns an ordered list of field tokens (as the code names them, e.g. 'P[1]', 'KATT1'),
which a human/LLM then maps to physics -- but the ORDER, the thing a mis-parse gets
wrong, is fixed by this function, not guessed.
"""
import re

# a streamed field: anything between << ... << that is not a literal separator/string
_SEP_RE = re.compile(r'^(?:"[^"]*"|\s*|endl|std::endl|"\\n"|"\\t")$')
_COMMENT_PREFIX = ("//", "*", "#")


def _clean_field(tok):
    tok = tok.strip()
    # strip a trailing per-particle index like [i] so P[1][i] -> P[1]; keep inner [1]
    tok = re.sub(r"\[[A-Za-z_]\w*\]\s*$", "", tok)
    return tok


def parse_cpp_stream_write(line):
    """Given a C++ record-write line ``obj << a << " " << b << endl;`` return the ordered
    list of DATA fields (separators/newlines/strings dropped). Column N of the output is
    element N of this list -- the independent truth for column order."""
    s = line.strip()
    if s.startswith(_COMMENT_PREFIX):
        return []
    # drop everything up to and including the first << (the stream object + optional '# ')
    if "<<" not in s:
        return []
    parts = s.split("<<")[1:]                    # tokens after each <<
    fields = []
    for p in parts:
        p = p.rstrip(";").strip()
        if p.endswith("endl") or p.endswith("endl)"):
            p = p[:p.rfind("endl")].strip().rstrip("<").strip()
        if not p or _SEP_RE.match(p):
            continue
        if p.startswith('"') and p.endswith('"'):
            continue                             # a quoted literal separator/label
        # a leading numeric sign carried on the field (e.g. -LBT->P0[1]) -> keep the field
        fields.append(_clean_field(p))
    return [f for f in fields if f and not _SEP_RE.match(f)]


def parse_header_named(header_line):
    """OSCAR2013-style: '#!OSCAR2013 particle_lists t x y z mass p0 px py pz pdg ...'.
    Return the column names after the format keyword."""
    toks = header_line.lstrip("#!").split()
    # drop leading format keywords (OSCAR2013, particle_lists, ...) -- keep from the first
    # single-letter or physics-like token; heuristic: names appear after 'particle_lists'
    if "particle_lists" in toks:
        return toks[toks.index("particle_lists") + 1:]
    return toks


def parse_header_kv(header_lines):
    """TRENTo-style '# key = value' block: return the ordered key names."""
    keys = []
    for line in header_lines:
        m = re.match(r"^#\s*([A-Za-z][\w]*)\s*=", line)
        if m:
            keys.append(m.group(1))
    return keys


def column_truth(writer_line=None, header_line=None, header_kv_lines=None):
    """Dispatch to whichever independent source is available. Returns
    {'paradigm': ..., 'fields': [...ordered field tokens...]}."""
    if header_line and ("OSCAR" in header_line or "particle_lists" in header_line):
        return {"paradigm": "header_named", "fields": parse_header_named(header_line)}
    if header_kv_lines:
        keys = parse_header_kv(header_kv_lines)
        if keys:
            return {"paradigm": "header_kv", "fields": keys}
    if writer_line:
        fields = parse_cpp_stream_write(writer_line)
        if fields:
            return {"paradigm": "cpp_stream", "fields": fields}
    return {"paradigm": "unknown", "fields": []}
