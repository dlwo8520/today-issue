"""Install a checksum-verified portable Node LTS inside .tools on Windows."""
import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".tools"
target.mkdir(exist_ok=True)
with urllib.request.urlopen("https://nodejs.org/dist/index.json", timeout=30) as response:
    releases = json.load(response)
release = next(r for r in releases if r["lts"] and "win-x64-zip" in r["files"])
version = release["version"]
name = f"node-{version}-win-x64.zip"
base = f"https://nodejs.org/dist/{version}/"
with urllib.request.urlopen(base + "SHASUMS256.txt", timeout=30) as response:
    checksums = response.read().decode()
expected = next(line.split()[0] for line in checksums.splitlines() if line.endswith("  " + name))
archive = target / name
urllib.request.urlretrieve(base + name, archive)
if hashlib.file_digest(archive.open("rb"), "sha256").hexdigest() != expected:
    raise RuntimeError("Node archive checksum mismatch")
with zipfile.ZipFile(archive) as bundle:
    bundle.extractall(target)
print(target / f"node-{version}-win-x64")
