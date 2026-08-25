"""Download DejaVu Sans for Cyrillic PDF TZ export."""

from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "core" / "fonts" / "DejaVuSans.ttf"
ZIP_URL = "https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.zip"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.is_file() and OUT.stat().st_size > 100_000:
        print("exists", OUT, OUT.stat().st_size)
        return
    req = urllib.request.Request(ZIP_URL, headers={"User-Agent": "asf-tz-font"})
    with urllib.request.urlopen(req, timeout=90) as res:
        blob = res.read()
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        name = next(
            n
            for n in zf.namelist()
            if n.endswith("DejaVuSans.ttf") and "Bold" not in n and "Oblique" not in n
        )
        OUT.write_bytes(zf.read(name))
    print("wrote", OUT, OUT.stat().st_size)


if __name__ == "__main__":
    main()
