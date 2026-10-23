#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, os, re, shutil, sys, zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
TEXT_EXT = {".xml", ".py", ".po", ".txt", ".md", ".json"}
FIXED_TIME = (2024, 1, 1, 0, 0, 0)

def default_base_url() -> str:
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        return "https://USER.github.io/REPO"
    owner, name = repo.split("/", 1)
    if name.lower() == f"{owner.lower()}.github.io":
        return f"https://{owner.lower()}.github.io"
    return f"https://{owner.lower()}.github.io/{name}"

def render_addon(src: Path, dest: Path, base_url: str) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        target = dest / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix in TEXT_EXT:
            target.write_text(path.read_text(encoding="utf-8").replace("{{BASE_URL}}", base_url), encoding="utf-8")
        else:
            shutil.copyfile(path, target)

def make_zip(addon_dir: Path, addon_id: str, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(addon_dir.rglob("*")):
            if path.is_dir():
                continue
            info = zipfile.ZipInfo(f"{addon_id}/{path.relative_to(addon_dir).as_posix()}", FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("BASE_URL") or default_base_url())
    ap.add_argument("--src", default=str(ROOT / "kodi"))
    ap.add_argument("--out", default=str(ROOT))
    args = ap.parse_args()

    base_url = args.base_url.rstrip("/")
    src_root, out = Path(args.src), Path(args.out)
    work = out / ".kodi_build"
    addon_xmls: list[str] = []

    if not src_root.exists():
        print("No kodi directory found", file=sys.stderr)
        return 1

    for src in sorted(p for p in src_root.iterdir() if (p / "addon.xml").exists()):
        addon_id = src.name
        rendered = work / addon_id
        render_addon(src, rendered, base_url)

        xml_text = (rendered / "addon.xml").read_text(encoding="utf-8")
        root = ET.fromstring(xml_text)
        version = root.get("version")

        zip_path = out / "zips" / addon_id / f"{addon_id}-{version}.zip"
        make_zip(rendered, addon_id, zip_path)
        print(f"[zip] {zip_path.relative_to(out)}")

        if addon_id.startswith("repository."):
            shutil.copyfile(zip_path, out / f"{addon_id}.zip")

        addon_xmls.append(re.sub(r"^<\?xml[^>]*\?>\s*", "", xml_text).strip())

    shutil.rmtree(work, ignore_errors=True)
    if not addon_xmls:
        print("No add-ons found under", src_root, file=sys.stderr)
        return 1

    addons_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n' + \
        "\n".join(addon_xmls) + "\n</addons>\n"
    (out / "addons.xml").write_text(addons_xml, encoding="utf-8")
    (out / "addons.xml.md5").write_text(hashlib.md5(addons_xml.encode("utf-8")).hexdigest(), encoding="utf-8")
    print(f"[repo] addons.xml + md5 written (base url: {base_url})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
