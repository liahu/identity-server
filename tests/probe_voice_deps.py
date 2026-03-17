import importlib.util
import json
import site
import subprocess
import sys
from pathlib import Path


def runtime_missing() -> list[str]:
    p = subprocess.run(
        [sys.executable, "-c", "import wespeaker.cli.speaker"],
        capture_output=True,
        text=True,
    )
    if p.returncode == 0:
        return []
    msg = (p.stderr or p.stdout or "")
    marker = "No module named "
    if marker not in msg:
        return []
    tail = msg.split(marker, 1)[1].strip()
    name = tail.strip('"').strip("'").split(".")[0]
    return [name]


def static_missing() -> list[str]:
    root = None
    for sp in site.getsitepackages():
        p = Path(sp) / "wespeaker"
        if p.exists() and p.is_dir():
            root = p
            break
    if root is None:
        return ["wespeaker"]
    root = root.resolve()
    mods = set()
    for py in root.rglob("*.py"):
        text = py.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("import "):
                part = s[7:].split("#", 1)[0]
                for item in part.split(","):
                    m = item.strip().split(" as ")[0].strip()
                    if m:
                        mods.add(m.split(".")[0])
            elif s.startswith("from "):
                m = s[5:].split(" import ", 1)[0].strip()
                if m and not m.startswith("."):
                    mods.add(m.split(".")[0])

    stdlib_or_internal = {
        "os",
        "sys",
        "json",
        "time",
        "math",
        "copy",
        "itertools",
        "functools",
        "pathlib",
        "typing",
        "dataclasses",
        "argparse",
        "logging",
        "collections",
        "subprocess",
        "shutil",
        "threading",
        "queue",
        "glob",
        "random",
        "statistics",
        "re",
        "tempfile",
        "traceback",
        "pickle",
        "warnings",
        "datetime",
        "inspect",
        "importlib",
        "hashlib",
        "base64",
        "socket",
        "http",
        "urllib",
        "decimal",
        "fractions",
        "numbers",
        "textwrap",
        "gzip",
        "zipfile",
        "tarfile",
        "io",
        "csv",
        "configparser",
        "enum",
        "abc",
        "types",
        "pprint",
        "contextlib",
        "signal",
        "wespeaker",
    }

    missing = []
    for m in sorted(mods):
        if m in stdlib_or_internal:
            continue
        if importlib.util.find_spec(m) is None:
            missing.append(m)
    return missing


if __name__ == "__main__":
    print(
        json.dumps(
            {
                "runtime_missing": runtime_missing(),
                "missing_static": static_missing(),
            },
            ensure_ascii=False,
        )
    )
