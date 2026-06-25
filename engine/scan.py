"""Model-agnostic scanning of a scientific code checkout.

This module must contain NO model/domain knowledge (enforced by
tests/test_boundary.py). It only extracts structural facts.
"""
from __future__ import annotations

import ast
import configparser
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional

SKIP_DIR_NAMES = {
    ".git", "__pycache__", "build", "dist", ".pytest_cache",
    ".mypy_cache", ".venv", "venv", "node_modules",
}

_EXT = {
    "source": {".py", ".cpp", ".c", ".h", ".hpp", ".f90", ".cc", ".cu", ".cl"},
    "config": {".ini", ".info", ".yaml", ".yml", ".json", ".toml", ".cfg"},
    "docs": {".md", ".rst", ".txt"},
    "data": {".dat", ".h5", ".root", ".csv", ".oscar"},
    "notebook": {".ipynb"},
}
_BUILD_NAMES = {"CMakeLists.txt", "Makefile", "GNUmakefile", "setup.py",
                "pyproject.toml", "meson.build"}


def read_text(path: Path, limit: Optional[int] = None) -> str:
    path = Path(path)
    if not path.exists() or not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[:limit] if limit else text


def literal(node):
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def expr_name(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = expr_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Constant):
        return repr(node.value)
    return ""


def iter_files(root: Path) -> Iterable[Path]:
    for path in Path(root).rglob("*"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.is_file():
            yield path


# ---------------------------------------------------------------- parameters
def extract_argparse_parameters(path: Path) -> List[Dict[str, object]]:
    path = Path(path)
    if not path.exists():
        return []
    try:
        tree = ast.parse(read_text(path))
    except SyntaxError:
        return []
    # Pre-pass: variable name -> mutually-exclusive-group id (generic argparse idiom)
    group_of_var: Dict[str, int] = {}
    next_gid = 0
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Attribute)
                and node.value.func.attr == "add_mutually_exclusive_group"):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    group_of_var[tgt.id] = next_gid
            next_gid += 1
    params: List[Dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "add_argument":
            continue
        flags = [literal(arg) for arg in node.args]
        flags = [flag for flag in flags if isinstance(flag, str)]
        option_flags = [flag for flag in flags if flag.startswith("--")]
        if not option_flags:
            continue
        keywords = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        default = literal(keywords["default"]) if "default" in keywords else None
        choices = literal(keywords["choices"]) if "choices" in keywords else None
        required = literal(keywords["required"]) if "required" in keywords else None
        help_text = literal(keywords["help"]) if "help" in keywords else ""
        type_text = expr_name(keywords["type"]) if "type" in keywords else ""
        recv = node.func.value
        exclusive_group = group_of_var.get(recv.id) if isinstance(recv, ast.Name) else None
        params.append({
            "name": option_flags[0].lstrip("-"),
            "flags": option_flags,
            "default": default,
            "type": type_text,
            "choices": choices,
            "required": required,
            "exclusive_group": exclusive_group,
            "help": help_text or "",
            "source": str(path),
        })
    return params


def extract_ini_parameters(path: Path) -> List[Dict[str, object]]:
    path = Path(path)
    if not path.exists():
        return []
    parser = configparser.ConfigParser(inline_comment_prefixes=(";", "#"), strict=False)
    parser.optionxform = str
    try:
        parser.read(path)
    except Exception:
        return []
    params: List[Dict[str, object]] = []
    for section in parser.sections():
        for key, value in parser.items(section):
            params.append({
                "name": key,
                "flags": [f"--{key}"],
                "default": value,
                "type": "",
                "choices": None,
                "help": f"`{path.name}` section `{section}`",
                "source": str(path),
            })
    return params


def extract_yaml_keys(path: Path) -> List[Dict[str, object]]:
    path = Path(path)
    if not path.exists():
        return []
    params: List[Dict[str, object]] = []
    seen = set()
    for line in read_text(path).splitlines():
        match = re.match(r"^([A-Za-z0-9_./-]+)\s*:\s*(.*)$", line)
        if not match:
            continue
        key = match.group(1)
        if key in seen:
            continue
        seen.add(key)
        params.append({
            "name": key,
            "flags": [key],
            "default": match.group(2).strip() or None,
            "type": "yaml-key",
            "choices": None,
            "help": f"Top-level YAML key in `{path.name}`",
            "source": str(path),
        })
    return params


def dedupe_parameters(parameters: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    by_name: Dict[str, Dict[str, object]] = {}
    for param in parameters:
        name = str(param["name"])
        if name not in by_name:
            by_name[name] = dict(param)
            continue
        existing = by_name[name]
        if not existing.get("help") and param.get("help"):
            existing["help"] = param["help"]
        if existing.get("default") in (None, "") and param.get("default") not in (None, ""):
            existing["default"] = param["default"]
        existing["source"] = f"{existing['source']}; {param['source']}"
    return [by_name[key] for key in sorted(by_name)]


def collect_parameters(root: Path, py_files: List[str], config_files: List[str]) -> List[Dict[str, object]]:
    root = Path(root)
    params: List[Dict[str, object]] = []
    for rel in py_files:
        params.extend(extract_argparse_parameters(root / rel))
    for rel in config_files:
        suf = Path(rel).suffix.lower()
        if suf in (".ini", ".info", ".cfg"):
            params.extend(extract_ini_parameters(root / rel))
        elif suf in (".yaml", ".yml"):
            params.extend(extract_yaml_keys(root / rel))
    return dedupe_parameters(params)


# ----------------------------------------------------------- git / counts / dirs
def git_info(root: Path) -> Dict[str, str]:
    root = Path(root)
    if not (root / ".git").exists():
        return {}
    info: Dict[str, str] = {}
    for key, cmd in {
        "commit": ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
        "branch": ["git", "-C", str(root), "branch", "--show-current"],
        "remote": ["git", "-C", str(root), "remote", "get-url", "origin"],
        "describe": ["git", "-C", str(root), "describe", "--always", "--dirty", "--tags"],
    }.items():
        try:
            info[key] = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
        except Exception:
            pass
    try:
        dirty = subprocess.check_output(
            ["git", "-C", str(root), "status", "--porcelain"],
            text=True, stderr=subprocess.DEVNULL).strip()
        info["dirty"] = "true" if dirty else "false"
    except Exception:
        pass
    return info


def file_counts(root: Path) -> Dict[str, int]:
    counter: Counter = Counter()
    for path in iter_files(root):
        suffix = path.suffix.lower() or "[no extension]"
        counter[suffix] += 1
    return dict(counter.most_common(30))


def directory_summary(root: Path, max_depth: int = 2) -> List[str]:
    entries: List[str] = []
    for path in sorted(Path(root).rglob("*")):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.is_dir():
            rel = path.relative_to(root)
            if len(rel.parts) <= max_depth:
                entries.append(str(rel))
    return entries


_DEP_KEYWORDS = ["OpenCL", "CUDA", "PyOpenCL", "pyopencl", "Anaconda", "cmake",
                 "gsl", "Boost", "h5py", "pandas", "sympy", "Mako", "HDF5", "YAML", "ROOT"]


def dependency_lines(readme: str) -> List[str]:
    lines = []
    for line in readme.splitlines():
        if any(kw.lower() in line.lower() for kw in _DEP_KEYWORDS):
            stripped = line.strip()
            if stripped:
                lines.append(stripped)
    return lines[:60]


# ------------------------------------------------------------------- classify
def classify_files(root: Path) -> Dict[str, object]:
    out: Dict[str, object] = {k: [] for k in (
        "source", "build_files", "config_files", "docs",
        "output_data", "notebooks", "binaries")}
    readme_path = None
    for path in iter_files(root):
        rel = str(path.relative_to(root))
        name, suf = path.name, path.suffix.lower()
        if name in _BUILD_NAMES:
            out["build_files"].append(rel)
        if suf in _EXT["source"]:
            out["source"].append(rel)
        elif suf in _EXT["config"]:
            out["config_files"].append(rel)
        elif suf in _EXT["docs"]:
            out["docs"].append(rel)
        elif suf in _EXT["data"]:
            out["output_data"].append(rel)
        elif suf in _EXT["notebook"]:
            out["notebooks"].append(rel)
        if readme_path is None and name.lower().startswith("readme"):
            readme_path = rel
    out["readme_path"] = readme_path
    return out


def scan_files(root: Path) -> Dict[str, object]:
    root = Path(root).resolve()
    result = classify_files(root)
    result["git"] = git_info(root)
    result["directories"] = directory_summary(root)
    result["file_counts"] = file_counts(root)
    return result


# --------------------------------------------------------------------- entries
def _argv_positional_names(text: str) -> List[str]:
    found: Dict[int, str] = {}
    for match in re.finditer(r"(\w+)\s*=\s*(?:int\(|float\(|str\()?\s*sys\.argv\[(\d+)\]", text):
        found.setdefault(int(match.group(2)), match.group(1))
    return [found[i] for i in sorted(found) if i >= 1]


_ARGV_INDEX_RE = re.compile(r"sys\.argv\[(\d+)\]")
_ARGV_LEN_GUARD_RE = re.compile(r"len\(\s*sys\.argv\s*\)\s*(==|>=|>)\s*(\d+)")


def _argv_required_count(text: str) -> int:
    """How many positional args the code actually requires, inferred from the
    code itself: the highest ``sys.argv[i]`` index used, cross-checked with any
    ``len(sys.argv) <op> N`` guard. These are generic Python idioms -- no model
    knowledge. ``len==N`` / ``len>=N`` imply ``N-1`` positionals; ``len>N`` implies
    ``N``; the largest signal wins."""
    max_index = max((int(m.group(1)) for m in _ARGV_INDEX_RE.finditer(text)), default=0)
    guard = 0
    for m in _ARGV_LEN_GUARD_RE.finditer(text):
        op, n = m.group(1), int(m.group(2))
        guard = max(guard, n if op == ">" else n - 1)
    return max(max_index, guard)


def _entry_signature(text: str) -> Optional[Dict[str, object]]:
    uses_argparse = "parse_args(" in text or "parse_known_args(" in text
    uses_argv = "sys.argv[" in text
    if not (uses_argparse or uses_argv):
        return None
    return {
        "cli_style": "argparse" if uses_argparse else "argv",
        "argv_names": _argv_positional_names(text) if uses_argv else [],
        "argv_required": _argv_required_count(text) if uses_argv else 0,
        "reads_config": "read_config(" in text,
    }


def detect_entrypoints(root: Path, py_dirs: Optional[List[str]] = None) -> List[Dict[str, object]]:
    root = Path(root)
    if py_dirs is None:
        py_dirs = [p.name for p in root.iterdir() if p.is_dir() and p.name not in SKIP_DIR_NAMES]
        py_dirs.append(".")
    candidates: List[Path] = []
    for d in py_dirs:
        base = root / d
        if base.is_dir():
            candidates.extend(sorted(base.rglob("*.py")))
    entries: List[Dict[str, object]] = []
    seen = set()
    for path in candidates:
        if any(part in SKIP_DIR_NAMES for part in path.relative_to(root).parts[:-1]):
            continue
        rel = str(path.relative_to(root))
        if rel in seen:
            continue
        seen.add(rel)
        sig = _entry_signature(read_text(path))
        if sig is None:
            continue
        entries.append({"path": rel, "purpose": f"CLI entry ({sig['cli_style']})", **sig})
    return entries


_CPP_ARGV_IDX_RE = re.compile(r"argv\s*\[\s*(\d+)\s*\]")
_CPP_ARGV_NAME_RE = re.compile(r"([A-Za-z_]\w*)\s*=\s*(?:ato[ifl]+\s*\(\s*)?argv\s*\[\s*(\d+)\s*\]")
_CPP_MAIN_RE = re.compile(r"\bint\s+main\s*\([^)]*\bargv\b")
_MAKE_EXE_RE = re.compile(r"^\s*EXE\s*[:?]?=\s*(\S+)", re.MULTILINE)


def _cpp_argv_positionals(text: str):
    """Ordered positional names for a C/C++ ``argv`` entry (``argv[0]`` is the
    program). Names come from ``name = atoi(argv[i])`` / ``name = argv[i]``
    assignments; unnamed slots fall back to ``argN``. Count = highest index used.
    All generic C idioms -- no model knowledge."""
    named: Dict[int, str] = {}
    for m in _CPP_ARGV_NAME_RE.finditer(text):
        idx = int(m.group(2))
        if idx >= 1:
            named.setdefault(idx, m.group(1))
    max_idx = max((int(m.group(1)) for m in _CPP_ARGV_IDX_RE.finditer(text)), default=0)
    return [named.get(i, "arg%d" % i) for i in range(1, max_idx + 1)], max_idx


def _makefile_exe(dirpath: Path) -> Optional[str]:
    for name in ("Makefile", "GNUmakefile", "makefile"):
        mk = Path(dirpath) / name
        if mk.is_file():
            m = _MAKE_EXE_RE.search(read_text(mk))
            if m:
                return m.group(1)
    return None


def detect_cpp_entrypoints(root: Path) -> List[Dict[str, object]]:
    """Compiled-C/C++ run entries the Python scanner misses: a source file with
    ``int main(...argv...)``. The run command is derived as ``./<exe>`` with the
    exe name from a sibling Makefile ``EXE=``, else the source stem."""
    root = Path(root)
    entries: List[Dict[str, object]] = []
    seen = set()
    for ext in ("*.cpp", "*.cc", "*.cxx", "*.c"):
        for path in sorted(root.rglob(ext)):
            if any(part in SKIP_DIR_NAMES for part in path.relative_to(root).parts[:-1]):
                continue
            text = read_text(path)
            if not _CPP_MAIN_RE.search(text):
                continue
            rel = str(path.relative_to(root))
            if rel in seen:
                continue
            seen.add(rel)
            names, required = _cpp_argv_positionals(text)
            exe = _makefile_exe(path.parent) or path.stem
            entries.append({
                "path": rel, "purpose": "CLI entry (argv, compiled)",
                "cli_style": "argv", "lang": "cpp", "run_prefix": ["./%s" % exe],
                "argv_names": names, "argv_required": required, "reads_config": False,
            })
    return entries


# ------------------------------------------------------------- outputs / builds
_OUTPUT_LIT_RE = re.compile(r"""['"]([^'"]*\.(?:dat|h5|txt|csv|oscar))['"]""")
_OUTPUT_NAME_OK = re.compile(r"^[A-Za-z][\w-]+\.(?:dat|h5|txt|csv|oscar)$")
_WRITE_TOKENS = (
    "savetxt", ".save(", ".tofile(", "create_dataset", "to_hdf", ".to_csv(",
    "np.save", "savez", "'w'", '"w"', "'a'", '"a"', "'wb'", '"wb"',
)


def discover_output_files_from_source(root: Path, src_dirs: List[str]) -> Dict[str, str]:
    root = Path(root)
    found: Dict[str, str] = {}
    for d in src_dirs:
        base = root / d
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            for line in read_text(path).splitlines():
                if not any(tok in line for tok in _WRITE_TOKENS):
                    continue
                for lit in _OUTPUT_LIT_RE.findall(line):
                    name = lit.rsplit("/", 1)[-1]
                    if "%" in name or "{" in name:
                        continue
                    if _OUTPUT_NAME_OK.match(name):
                        found.setdefault(name, str(path.relative_to(root)))
    return found


def build_targets(root: Path) -> List[str]:
    root = Path(root)
    out = []
    for path in root.rglob("CMakeLists.txt"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        out.append(str(path.parent.relative_to(root)))
    return sorted(dict.fromkeys(out))


_README_CMD_RE = re.compile(r"^\s*#?\s*((?:(?:python\d?|mpirun|srun|bash|sh)\s+\S[^\n]*)|(?:\./\S[^\n]*))$")
_README_CMD_SKIP = ("pip ", "conda ", "setup.py", "-m pip", "install", "apt ", "brew ")


def readme_run_commands(readme_text: str) -> List[str]:
    """Extract documented run commands from the README (the authoritative,
    model-agnostic source of "how to run"). Skips install-style lines."""
    out: List[str] = []
    seen = set()
    for line in readme_text.splitlines():
        m = _README_CMD_RE.match(line)
        if not m:
            continue
        cmd = m.group(1).strip()
        if any(tok in cmd for tok in _README_CMD_SKIP):
            continue
        if cmd not in seen:
            seen.add(cmd)
            out.append(cmd)
    return out[:20]


def primary_entrypoint(entries: List[Dict[str, object]],
                       readme_commands: Optional[List[str]] = None) -> Optional[Dict[str, object]]:
    """Pick the most likely run driver, by characteristic only (no model names).
    The README is authoritative about which script is a run driver, so prefer
    entries whose basename appears in a README run command; otherwise fall back
    to a positional+config entry, then any argv, then any argparse entry."""
    if not entries:
        return None
    readme_scripts = set()
    for cmd in readme_commands or []:
        for tok in cmd.split():
            base = tok.split("/")[-1]
            if base.endswith((".py", ".sh")):
                readme_scripts.add(base)
    documented = [e for e in entries if e["path"].split("/")[-1] in readme_scripts]
    pool_source = documented or entries
    argv_cfg = [e for e in pool_source if e.get("cli_style") == "argv" and e.get("reads_config")]
    argv_any = [e for e in pool_source if e.get("cli_style") == "argv"]
    argparse_any = [e for e in pool_source if e.get("cli_style") == "argparse"]
    for pool in (argv_cfg, argv_any, argparse_any):
        if pool:
            return sorted(pool, key=lambda e: -len(e.get("argv_names", [])))[0]
    return pool_source[0]


# ------------------------------------------------------------------------- top
def _looks_like_project(d: Path) -> bool:
    """Generic, model-agnostic test for 'this dir is an independent project root':
    a VCS checkout (``.git``), or a README accompanied by at least one runnable
    entry somewhere inside. Loose scripts or tooling dirs (no README, no VCS) do
    not qualify, so they never masquerade as a project root."""
    d = Path(d)
    if (d / ".git").is_dir():
        return True
    if not (any(d.glob("README*")) or any(d.glob("readme*"))):
        return False
    for p in d.rglob("*.py"):
        if any(part in SKIP_DIR_NAMES for part in p.relative_to(d).parts[:-1]):
            continue
        if _entry_signature(read_text(p)) is not None:
            return True
    return False


class AmbiguousProjectRoot(Exception):
    """Raised when the given root is a multi-project workspace: several
    independent project-like children and no single real root to choose. The
    caller must point ``--project-root`` at one specific project."""

    def __init__(self, root: Path, candidates: List[Path]):
        self.root = Path(root)
        self.candidates = [Path(c) for c in candidates]
        names = ", ".join(sorted(c.name for c in self.candidates))
        super().__init__(
            f"{root} looks like a multi-project workspace, not a single project "
            f"(independent project roots found: {names}). "
            f"Point --project-root at one of them.")


def _effective_root(root: Path, max_depth: int = 3) -> Path:
    """Descend to the real project root, applying two rules (up to ``max_depth``):

    1. *Pure wrapper* -- the only non-skipped content is exactly one subdirectory
       and no files of its own (e.g. an unzipped archive ``wrapper/Project/...``):
       descend into it.
    2. *Workspace with one project* -- the current dir is not itself a project
       root, but exactly one child *is* (``_looks_like_project``): descend into it.
       This handles a messy parent dir that holds one real checkout plus loose
       files / tooling dirs.

    If the current dir is itself a project root, stop. If it is not a project and
    has *multiple* project-like children, it is an ambiguous multi-project
    workspace -> raise ``AmbiguousProjectRoot``. Otherwise stop here."""
    root = Path(root)
    for _ in range(max_depth):
        if _looks_like_project(root):
            return root
        children = [c for c in root.iterdir() if c.name not in SKIP_DIR_NAMES]
        dirs = [c for c in children if c.is_dir()]
        files = [c for c in children if c.is_file()]
        if len(dirs) == 1 and not files:
            root = dirs[0]
            continue
        proj_children = [d for d in dirs if _looks_like_project(d)]
        if len(proj_children) == 1:
            root = proj_children[0]
            continue
        if len(proj_children) >= 2:
            raise AmbiguousProjectRoot(root, proj_children)
        return root
    return root


_SKILL_JUNK_DIRS = {".git", "__pycache__", "node_modules", "__MACOSX",
                    ".ipynb_checkpoints", ".mypy_cache", ".pytest_cache"}


def _skill_meta(skill_md: Path):
    """(name, description) from a SKILL.md YAML frontmatter; best-effort, falls
    back to the parent directory name."""
    name = skill_md.parent.name
    desc = ""
    try:
        text = skill_md.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return name, desc
    if text.startswith("---"):
        end = text.find("\n---", 3)
        fm = text[3:end] if end != -1 else ""
        for line in fm.splitlines():
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip() or name
            elif line.startswith("description:"):
                desc = line.split(":", 1)[1].strip().strip('"').strip("'")
                if desc in (">", "|", ">-", "|-", ">+", "|+"):
                    desc = ""        # YAML block scalar; body on following lines (best-effort: skip)
    return name, desc


def detect_existing_skills(root: Path) -> list:
    """Hand-authored skills the code already ships (a SKILL.md living under a
    skills-ish directory). The meta-skill defers to these instead of generating
    a competing, thinner skill. Detection is by location -- some ancestor dir
    name contains 'skill' -- which matches both the `.claude/skills/<name>/`
    convention and project conventions like `LBTskills/<name>/`. Our own
    generated skills (which carry references/project-profile.json) are excluded."""
    root = Path(root)
    out, seen = [], set()
    for skill_md in root.rglob("SKILL.md"):
        parts = skill_md.relative_to(root).parts
        if any(p in _SKILL_JUNK_DIRS for p in parts):
            continue
        if not any("skill" in p.lower() for p in parts[:-1]):
            continue                                  # not under a skills-ish dir
        if (skill_md.parent / "references" / "project-profile.json").exists():
            continue                                  # our own generated skill, not code-shipped
        rel = "/".join(parts)
        if rel in seen:
            continue
        seen.add(rel)
        name, desc = _skill_meta(skill_md)
        out.append({"name": name, "path": rel, "description": desc})
    return sorted(out, key=lambda s: s["path"])


def scan_project(root: Path) -> Dict[str, object]:
    root = _effective_root(Path(root).resolve())
    files = scan_files(root)
    src_dirs = sorted({p.split("/")[0] for p in files["source"] if "/" in p} | {"."})
    py_dirs = [d for d in src_dirs if d != "."] + ["."]
    entries = detect_entrypoints(root, py_dirs=py_dirs)
    if not entries:                              # no Python driver -> compiled C/C++ fallback
        entries = detect_cpp_entrypoints(root)
    entry_py = [e["path"] for e in entries]
    params = collect_parameters(root, entry_py, files["config_files"])
    outputs = discover_output_files_from_source(root, src_dirs)
    readme_rel = files.get("readme_path")
    readme_text = read_text(root / readme_rel) if readme_rel else ""
    readme_cmds = readme_run_commands(readme_text)
    scan = dict(files)
    scan.update({
        "project_root": str(root),
        "entrypoints": entries,
        "parameters": params,
        "output_files": [{"name": n, "source": s} for n, s in sorted(outputs.items())],
        "build_targets": build_targets(root),
        "dependencies": dependency_lines(readme_text),
        "readme_commands": readme_cmds,
        "primary_entry": primary_entrypoint(entries, readme_cmds),
        "existing_skills": detect_existing_skills(root),
    })
    return scan
