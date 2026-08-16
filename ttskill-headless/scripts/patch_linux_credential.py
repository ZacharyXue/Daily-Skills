#!/usr/bin/env python3
"""Idempotent headless patch for ttskill credential-store.js.

Converts the Linux credential backend from Secret Service (secret-tool / D-Bus)
to plain-file storage in auth/token.json + auth/device-key.json, so ttskill
works on headless servers (ECS) without a desktop session.

Usage:
  patch_linux_credential.py <ttskill-base-dir>   # apply patch (idempotent)
  patch_linux_credential.py --check <dir>        # report whether patched
"""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = "src/credential-store.js"

MARKER = "Headless server fallback"

# (unique marker, old block, new block) — order matters, apply in sequence
PATCHES = [
    (
        "fn secretServiceRead",
        """function secretServiceRead(record) {
  const result = spawnSync("secret-tool", [
    "lookup",
    "service",
    KEYCHAIN_SERVICE,
    "account",
    accountName(record),
  ], { encoding: "utf8" });
  if (result.error?.code === "ENOENT") return null;
  if (result.status !== 0) return null;
  const text = result.stdout.trim();
  return text ? JSON.parse(text) : null;
}""",
        """function secretServiceRead(record) {
  // Headless server fallback: store credentials as plain files in auth/
  // (no D-Bus / Secret Service available on ECS).
  const legacyPath = record.legacyPath();
  if (!exists(legacyPath)) return null;
  try {
    return readJson(legacyPath);
  } catch {
    return null;
  }
}""",
    ),
    (
        "fn secretServiceWrite",
        """function secretServiceWrite(record, payload) {
  const result = spawnSync("secret-tool", [
    "store",
    `--label=ttskill ${record.label}`,
    "service",
    KEYCHAIN_SERVICE,
    "account",
    accountName(record),
  ], { encoding: "utf8", input: JSON.stringify(payload) });
  if (result.error || result.status !== 0) {
    throw linuxSecretServiceError("写入", result);
  }
}""",
        """function secretServiceWrite(record, payload) {
  // Headless server fallback: write credentials as plain files in auth/.
  const legacyPath = record.legacyPath();
  fs.mkdirSync(path.dirname(legacyPath), { recursive: true });
  fs.writeFileSync(legacyPath + ".tmp", JSON.stringify(payload, null, 2) + "\\n", { mode: 0o600 });
  fs.renameSync(legacyPath + ".tmp", legacyPath);
}""",
    ),
    (
        "fn secretServiceDelete",
        """function secretServiceDelete(record) {
  spawnSync("secret-tool", [
    "clear",
    "service",
    KEYCHAIN_SERVICE,
    "account",
    accountName(record),
  ], { stdio: "ignore" });
}""",
        """function secretServiceDelete(record) {
  // Headless server fallback: delete the plain file.
  fs.rmSync(record.legacyPath(), { force: true });
}""",
    ),
    (
        "fn removeLegacyFile",
        """function removeLegacyFile(record) {
  fs.rmSync(record.legacyPath(), { force: true });
}""",
        """function removeLegacyFile(record) {
  // On Linux headless the "native" store IS the legacy file (see
  // secretServiceRead/Write), so never delete it.
  if (process.platform === "linux") return;
  fs.rmSync(record.legacyPath(), { force: true });
}""",
    ),
]


def find_base_dir(arg: str) -> Path:
    p = Path(arg).expanduser().resolve()
    # Accept the base dir itself or a path containing it (e.g. ~/.local/share/ttfund)
    if (p / TARGET).is_file():
        return p
    # Walk up to find the directory that contains src/credential-store.js
    for parent in [p, *p.parents]:
        if (parent / TARGET).is_file():
            return parent
    # Maybe user passed the package root like .../ttskill-base-linux-x64-0.1.2
    for parent in p.rglob("src"):
        if (parent / "credential-store.js").is_file():
            return parent.parent
    raise SystemExit(f"credential-store.js not found under {p}")


def is_patched(src: str) -> bool:
    return MARKER in src


def apply_patch(base: Path) -> str:
    target = base / TARGET
    src = target.read_text(encoding="utf-8")

    if is_patched(src):
        return "already-patched"

    applied = []
    for marker, old, new in PATCHES:
        if old not in src:
            return f"FAIL: block [{marker}] not found — file may be a different version"
        src = src.replace(old, new, 1)
        applied.append(marker)

    target.write_text(src, encoding="utf-8")
    return "patched: " + ", ".join(applied)


def main():
    args = sys.argv[1:]
    check = False
    if args and args[0] == "--check":
        check = True
        args = args[1:]
    if not args:
        raise SystemExit(__doc__)

    base = find_base_dir(args[0])
    target = base / TARGET

    if check:
        src = target.read_text(encoding="utf-8")
        print("PATCHED" if is_patched(src) else "NOT_PATCHED")
        return

    result = apply_patch(base)
    print(result)
    if result.startswith("FAIL"):
        sys.exit(1)
    # Sanity: JS syntax check
    import shutil
    import subprocess
    if shutil.which("node"):
        r = subprocess.run(["node", "--check", str(target)], capture_output=True, text=True)
        if r.returncode != 0:
            print("node --check FAILED:\n" + r.stderr)
            sys.exit(1)
        print("syntax OK")


if __name__ == "__main__":
    main()