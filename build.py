"""Package the Anki add-on.

The print page lives once, in web/index.html. This bundles it into the add-on
as flashcards_template.html and writes dist/print_cut_flashcards.ankiaddon.

    python build.py            # build the .ankiaddon
    python build.py --dev      # also copy the template into addon/, for running
                               # the add-on straight from this folder
"""

import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ADDON = ROOT / "addon"
WEB_PAGE = ROOT / "web" / "index.html"
DIST = ROOT / "dist"
OUT = DIST / "print_cut_flashcards.ankiaddon"

# user_files/ and caches must never ship: they hold one person's local state.
PACKAGED = ["__init__.py", "manifest.json", "README.md"]


def main():
    missing = [p for p in [WEB_PAGE] + [ADDON / f for f in PACKAGED] if not p.exists()]
    if missing:
        sys.exit("Missing: " + ", ".join(str(m.relative_to(ROOT)) for m in missing))

    DIST.mkdir(exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for name in PACKAGED:
            z.write(ADDON / name, name)
        z.write(WEB_PAGE, "flashcards_template.html")
    print("Wrote", OUT.relative_to(ROOT))

    if "--dev" in sys.argv:
        shutil.copyfile(WEB_PAGE, ADDON / "flashcards_template.html")
        print("Copied template into addon/ for development")


if __name__ == "__main__":
    main()
