"""
setup.py
~~~~~~~~
Entry point for the Spira project setup script.

Usage
-----
    python setup.py

Environment variables (loaded from .env):
    SPIRA_BASE_URL   Base URL of your Spira instance.
    SPIRA_USERNAME   Spira username.
    SPIRA_API_KEY    Spira API key / RSS token (include curly braces).

The structure to create is read from ``spira-structure.json`` in the same
directory as this script.
"""

import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from spira_setup.client import SpiraClient
from spira_setup.runner import run

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------
ROOT = Path(__file__).parent
ENV_FILE = ROOT / ".env"
STRUCTURE_FILE = ROOT / "spira-structure.json"


def _load_env() -> tuple[str, str, str]:
    """Load and validate required environment variables."""
    load_dotenv(ENV_FILE)

    base_url = os.getenv("SPIRA_BASE_URL", "").strip()
    username = os.getenv("SPIRA_USERNAME", "").strip()
    api_key = os.getenv("SPIRA_API_KEY", "").strip()

    missing = [
        name
        for name, val in [
            ("SPIRA_BASE_URL", base_url),
            ("SPIRA_USERNAME", username),
            ("SPIRA_API_KEY", api_key),
        ]
        if not val
    ]
    if missing:
        logger.error(
            "Missing required environment variable(s): %s.  "
            "Check your .env file.",
            ", ".join(missing),
        )
        sys.exit(1)

    return base_url, username, api_key


def _load_structure() -> dict:
    """Load and parse the structure JSON file."""
    if not STRUCTURE_FILE.exists():
        logger.error("Structure file not found: %s", STRUCTURE_FILE)
        sys.exit(1)

    with STRUCTURE_FILE.open(encoding="utf-8") as fh:
        return json.load(fh)


def _print_summary(summary: dict) -> None:
    """Print a human-readable summary of created resources."""
    print("\n" + "=" * 60)
    print("  SETUP COMPLETE — SUMMARY")
    print("=" * 60)

    sections = [
        ("Program",           "program"),
        ("Products",          "products"),
        ("Releases",          "releases"),
        ("Custom Lists",      "custom_lists"),
        ("Custom Properties", "custom_properties"),
        ("Test Folders",      "test_folders"),
        ("Test Cases",        "test_cases"),
    ]

    for label, key in sections:
        items = summary.get(key, [])
        if not items:
            continue
        print(f"\n{label} ({len(items)}):")
        for item in items:
            context = ""
            if "product" in item:
                context += f"  [product: {item['product']}]"
            if "folder" in item:
                context += f"  [folder: {item['folder']}]"
            if "artifact" in item:
                context += f"  [artifact: {item['artifact']}]"
            print(f"  • {item['name']} (id={item.get('id')}){context}")

    print("\n" + "=" * 60 + "\n")


def main() -> None:
    base_url, username, api_key = _load_env()
    structure = _load_structure()

    logger.info("Connecting to Spira at %s as '%s'.", base_url, username)
    client = SpiraClient(base_url, username, api_key)

    # Quick connectivity check
    try:
        client.get("projects")
    except Exception as exc:
        logger.error("Could not connect to Spira: %s", exc)
        sys.exit(1)

    logger.info("Connection OK.  Starting setup...")

    try:
        summary = run(client, structure)
    except Exception as exc:
        logger.error("Setup failed: %s", exc, exc_info=True)
        sys.exit(1)

    _print_summary(summary)


if __name__ == "__main__":
    main()
