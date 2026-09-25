"""Opt-in local collector: python -m app.monitor --cities mumbai,bangalore --once."""
import argparse
import time
from app.catalog import CITIES
from app.services import city_snapshot
from app.operations import record_check
from app.data.openaq import DataUnavailable


def run_once(cities):
    for city in cities:
        try:
            snapshot = city_snapshot(city, "live")
            record_check(city, snapshot)
            print(f"{city}: collected; {snapshot['quality']}", flush=True)
        except Exception as exc:
            # Never log raw exceptions: provider URLs can contain credentials.
            detail = str(exc) if isinstance(exc, DataUnavailable) else f"Collection failed ({type(exc).__name__}); inspect application tests."
            record_check(city, error=detail)
            print(f"{city}: {detail}", flush=True)
            continue
        # Delivery failures must never overwrite a successful collection check.
        try:
            from app.notifications import enqueue, dispatch
            enqueue(snapshot)
            dispatch()
        except Exception as exc:
            print(f"{city}: notification processing failed ({type(exc).__name__}); collection is saved.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cities", default="all", help="all, or comma-separated configured city IDs")
    parser.add_argument("--interval", type=int, default=3600)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    cities = list(CITIES) if args.cities == "all" else list(dict.fromkeys(args.cities.split(",")))
    if any(c not in CITIES for c in cities) or args.interval < 600:
        parser.error("Use configured city IDs and an interval of at least 600 seconds.")
    try:
        while True:
            run_once(cities)
            if args.once:
                return
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Monitor stopped cleanly.")


if __name__ == "__main__":
    main()
