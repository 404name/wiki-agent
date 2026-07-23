"""Portable PyInstaller build for the Wiki Agent sidecar.

Produces src-tauri/binaries/wiki-agent-core-<triple>[.exe] so Tauri's
externalBin can pick it up on any platform/CI runner. The web UI in dist/
is embedded, so run `npm run build` first.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parent
REPO_ROOT = CORE_DIR.parent
DIST_DIR = REPO_ROOT / "dist"
BINARIES_DIR = REPO_ROOT / "src-tauri" / "binaries"

COLLECT_ALL = ["graphiti_core", "fastembed", "langgraph", "langchain_openai", "keyring"]
HIDDEN_IMPORTS = ["wiki_agent.api"]


def host_triple() -> str:
    out = subprocess.run(["rustc", "-vV"], capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        if line.startswith("host:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError("could not read host triple from `rustc -vV`")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--triple", help="target triple; defaults to `rustc -vV` host")
    args = parser.parse_args()

    triple = args.triple or host_triple()
    is_windows = "windows" in triple
    name = f"wiki-agent-core-{triple}"

    if not DIST_DIR.exists():
        raise SystemExit(f"missing {DIST_DIR} — run `npm run build` first")

    sep = ";" if is_windows else ":"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile", "--console", "--noconfirm", "--clean",
        "--name", name,
        "--distpath", str(CORE_DIR / "dist"),
        "--workpath", str(CORE_DIR / "build"),
        "--specpath", str(CORE_DIR),
        "--add-data", f"{DIST_DIR}{sep}web",
    ]
    for pkg in COLLECT_ALL:
        cmd += ["--collect-all", pkg]
    for mod in HIDDEN_IMPORTS:
        cmd += ["--hidden-import", mod]
    cmd.append(str(CORE_DIR / "run_sidecar.py"))

    subprocess.run(cmd, check=True, cwd=CORE_DIR)

    exe_name = f"{name}.exe" if is_windows else name
    built = CORE_DIR / "dist" / exe_name
    if not built.exists():
        raise SystemExit(f"expected build output missing: {built}")

    BINARIES_DIR.mkdir(parents=True, exist_ok=True)
    target = BINARIES_DIR / exe_name
    shutil.copy2(built, target)
    print(f"sidecar ready: {target}")


if __name__ == "__main__":
    main()
