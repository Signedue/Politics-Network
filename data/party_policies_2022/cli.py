from __future__ import annotations

import argparse
import logging

from .config import PARTIES
from .pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect pre-election Danish party policy pages from the Wayback Machine.")
    parser.add_argument("--dry-run", action="store_true", help="Discover candidates without downloading archived HTML.")
    parser.add_argument(
        "--party",
        action="append",
        help="Party name or code; may be supplied multiple times.",
    )
    parser.add_argument("--max-pages", type=int, help="Maximum policy pages to attempt per selected party.")
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING"))
    args = parser.parse_args()
    if args.max_pages is not None and args.max_pages < 1:
        parser.error("--max-pages must be positive")
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s: %(message)s")
    selected = list(PARTIES)
    if args.party:
        selected = []
        for requested in args.party:
            matches = [
                party for party in PARTIES
                if party.code.casefold() == requested.casefold()
                or party.name.casefold() == requested.casefold()
            ]
            if not matches:
                parser.error(f"Unknown party: {requested}")
            selected.extend(matches)
        selected = list(dict.fromkeys(selected))
    rows, errors, summaries = run(selected, args.max_pages, args.dry_run)
    for summary in summaries:
        print(
            f"{summary['party']}: discovered={summary['discovered_urls']} "
            f"extracted={summary['extracted_pages']} rejected={summary['rejected_pages']}"
        )
    print(f"Total extracted: {len(rows)}; rejected/errors: {len(errors)}")


if __name__ == "__main__":
    main()
