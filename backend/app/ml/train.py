"""Collect and evaluate a city's live or explicitly synthetic data."""

from __future__ import annotations

from app.catalog import CITIES
import argparse
from app.services import city_snapshot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", choices=list(CITIES), default="delhi")
    parser.add_argument("--mode", choices=["live", "demo"], default="live")
    args = parser.parse_args()
    result = city_snapshot(args.city, args.mode)
    print(result["model"]["method"])
    print(result["model"]["metrics"])


if __name__ == "__main__":
    main()
