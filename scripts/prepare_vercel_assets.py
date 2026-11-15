"""Copy the Flask static files to the same URLs on Vercel's CDN."""

from pathlib import Path
import shutil


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = root / "c08" / "web"
    target = root / "public" / "static"
    shutil.copytree(source, target, dirs_exist_ok=True)


if __name__ == "__main__":
    main()
