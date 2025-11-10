import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# Ensure src directory is on sys.path so we can import sibling modules
CURRENT_FILE = Path(__file__).resolve()
SRC_DIR = CURRENT_FILE.parent
PROJECT_ROOT = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from extractors.instagram_parser import InstagramParser, InstagramScraperError  # type: ignore
from outputs.exporter import export_posts  # type: ignore

def load_settings(settings_path: Path) -> Dict[str, Any]:
    if not settings_path.exists():
        raise FileNotFoundError(f"Settings file not found at {settings_path}")

    with settings_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return data

def configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

def read_usernames_from_file(path: Path) -> List[str]:
    usernames: List[str] = []
    if not path.exists():
        logging.warning("Input file %s does not exist; no usernames loaded.", path)
        return usernames

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # Support "username,max_posts" but we only care about username here
            username = stripped.split(",")[0].strip()
            if username:
                usernames.append(username)

    return usernames

def parse_args() -> argparse.Namespace:
    default_input_file = PROJECT_ROOT / "data" / "inputs.sample.txt"
    default_settings = SRC_DIR / "config" / "settings.example.json"

    parser = argparse.ArgumentParser(
        description="Instagram User's Post Scraper - scrape public posts of Instagram profiles."
    )
    parser.add_argument(
        "-u",
        "--username",
        dest="usernames",
        action="append",
        help="Instagram username to scrape (can be used multiple times).",
    )
    parser.add_argument(
        "-i",
        "--input-file",
        type=str,
        default=str(default_input_file),
        help=f"Path to a text file containing usernames (one per line). Default: {default_input_file}",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=str(default_settings),
        help=f"Path to settings JSON file. Default: {default_settings}",
    )
    parser.add_argument(
        "-m",
        "--max-posts",
        type=int,
        default=None,
        help="Maximum number of posts to fetch per profile. Overrides config if provided.",
    )
    parser.add_argument(
        "-f",
        "--formats",
        nargs="+",
        choices=["json", "csv", "excel", "html"],
        help="Output formats. Overrides config if provided.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=str,
        help="Directory to store exported files. Overrides config if provided.",
    )

    return parser.parse_args()

def main() -> None:
    args = parse_args()

    # Load settings
    settings_path = Path(args.config).resolve()
    settings = load_settings(settings_path)

    # Configure logging
    log_level = settings.get("log_level", "INFO")
    configure_logging(log_level)
    logger = logging.getLogger("main")

    # Determine usernames
    usernames: List[str] = []
    if args.usernames:
        usernames.extend(args.usernames)

    input_file = Path(args.input_file).resolve()
    usernames_from_file = read_usernames_from_file(input_file)
    for u in usernames_from_file:
        if u not in usernames:
            usernames.append(u)

    if not usernames:
        logger.error(
            "No usernames provided. Use --username or provide a valid input file."
        )
        sys.exit(1)

    # Determine scraping options
    max_posts: Optional[int] = args.max_posts or settings.get(
        "max_posts_per_profile", None
    )

    output_dir_str: str = (
        args.output_dir or settings.get("output_dir", str(PROJECT_ROOT / "data"))
    )
    output_dir = Path(output_dir_str).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    formats: List[str] = args.formats or settings.get(
        "output_formats", ["json", "csv"]
    )

    # Setup scraper
    user_agent = settings.get(
        "user_agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36",
    )
    timeout = float(settings.get("request_timeout", 10))
    parser = InstagramParser(user_agent=user_agent, timeout=timeout)

    logger.info(
        "Starting scraping for %d profile(s). Output formats: %s. Max posts per profile: %s",
        len(usernames),
        ", ".join(formats),
        str(max_posts) if max_posts is not None else "unlimited",
    )

    for username in usernames:
        try:
            logger.info("Scraping profile '%s'...", username)
            posts = parser.fetch_posts(username=username, max_posts=max_posts)
            logger.info("Fetched %d posts for '%s'.", len(posts), username)

            if not posts:
                logger.warning("No posts found for '%s'. Skipping export.", username)
                continue

            base_filename = f"{username}_posts"
            export_paths = export_posts(
                posts=posts,
                output_dir=output_dir,
                base_filename=base_filename,
                formats=formats,
            )

            for fmt, path in export_paths.items():
                logger.info("Exported %s to %s", fmt.upper(), path)

        except InstagramScraperError as exc:
            logger.error(
                "Failed to scrape profile '%s': %s", username, exc, exc_info=True
            )
        except Exception as exc:  # pragma: no cover - safety net
            logger.exception("Unexpected error while processing '%s': %s", username, exc)

    logger.info("Scraping complete.")

if __name__ == "__main__":
    main()