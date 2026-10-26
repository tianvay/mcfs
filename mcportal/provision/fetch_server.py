"""Download and unpack the newest official Bedrock Dedicated Server for provision/setup.sh.

    python3 fetch_server.py <target dir>      -> prints the version on success

Uses the portal's release module unchanged (same checks as the update button: only minecraft.net over HTTPS,
version in the file name, intact zip, no unsafe paths or links, the expected server files). The module is loaded
by its file path, without the rest of the portal (it needs only the Python standard library).
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

RELEASE = Path(__file__).resolve().parent.parent / "app" / "adapters" / "bedrock" / "release.py"


def load_release():
    spec = importlib.util.spec_from_file_location("mcfs_release", RELEASE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mcfs_release"] = mod  # dataclasses look the module up by name
    spec.loader.exec_module(mod)
    return mod


def main(target: Path) -> int:
    release = load_release()
    try:
        rel = release.latest()
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / Path(rel.url).name
            release.download(rel, zip_path)
            release.stage(zip_path, target)
    except release.ReleaseError as e:
        print(f"FEHLER: {e}", file=sys.stderr)
        return 1
    print(rel.version)
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
