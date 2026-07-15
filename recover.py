"""Command-line entrypoint for Wayback Recovery."""

import argparse


def main() -> None:
    """Parse command-line options and run the requested recovery tool."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("domain", nargs="?", help="Target domain to recover.")
    parser.add_argument("--timeline", action="store_true", help="Print archive timeline.")
    parser.add_argument("--versions", action="store_true", help="Detect website versions.")
    parser.add_argument(
        "--recover-homepage",
        action="store_true",
        help="Recover the homepage for a detected version.",
    )
    parser.add_argument("--version", type=int, help="Detected version number to recover.")
    args = parser.parse_args()

    if args.domain is None:
        print("Usage:")
        print("python recover.py <domain> --timeline")
        print("python recover.py <domain> --versions")
        print("python recover.py <domain> --recover-homepage --version <number>")
        return

    if args.timeline:
        from archive.cdx import CDXClient
        from archive.timeline import build_timeline

        records = CDXClient().get_records(args.domain, collapse=True)
        timeline = build_timeline(records)

        print("Wayback Recovery")
        print()
        print("Timeline")
        print()
        for year in timeline:
            print(year["year"])
            print()
            print(f"Archived URLs: {year['archived_urls']}")
            print()
            print("First snapshot:")
            print(year["first_snapshot"])
            print()
            print("Last snapshot:")
            print(year["last_snapshot"])
            print()
            print("------------------")

        return

    if args.versions:
        from archive.cdx import CDXClient
        from archive.version_detector import detect_versions

        records = CDXClient().get_records(args.domain, collapse=True)
        versions = detect_versions(records)

        print("Wayback Recovery")
        print()
        print("Website Versions")
        print()
        for index, version in enumerate(versions, start=1):
            print(f"Version {index}")
            print()
            print(f"{version['start_year']}–{version['end_year']}")
            print()
            print(f"Confidence: {version['confidence']}")
            print()
            print("Reason:")
            for reason in version["reasons"]:
                print(reason)
            print()
            print("----------------------")

        return

    if args.recover_homepage:
        if args.version is None:
            raise ValueError("--recover-homepage requires --version <number>.")

        from archive.recovery import recover_homepage

        print("Recovering homepage...")
        output_path = recover_homepage(args.domain, args.version)
        print("✓ Homepage located")
        print("✓ Snapshot selected")
        print("✓ HTML downloaded")
        print("✓ Saved:")
        print(output_path)

        return

    print("Usage:")
    print("python recover.py <domain> --timeline")
    print("python recover.py <domain> --versions")
    print("python recover.py <domain> --recover-homepage --version <number>")


if __name__ == "__main__":
    main()
