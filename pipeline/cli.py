import argparse
import json
import logging
import os
import sys

# Add the parent directory to the system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.azure import assign_ip_to_vm, sync_ip_assignments


def main():
    parser = argparse.ArgumentParser(
        description="Swap Public IP CLI - Manage Azure public IP assignments",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Sync command - evaluate schedule and converge to desired state
    sync_parser = subparsers.add_parser(
        "sync",
        help="Evaluate schedule for current time and converge to desired state.",
    )
    sync_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )
    sync_parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON (for machine parsing)",
    )

    # Assign command - manual immediate assignment
    assign_parser = subparsers.add_parser(
        "assign",
        help="Assign a public IP label to a VM label immediately (manual override).",
    )
    assign_parser.add_argument("--vm", required=True, help="VM label from config/config.yml")
    assign_parser.add_argument("--ip", required=True, help="Public IP label from config/config.yml")

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if getattr(args, 'verbose', False) else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    if args.command == "sync":
        result = sync_ip_assignments()

        if args.json:
            # Output JSON for machine parsing
            output = {
                "desired_state": [{"vm": vm, "ip": ip} for vm, ip in result['desired_state']],
                "changes_made": [{"vm": vm, "ip": ip} for vm, ip in result['changes_made']],
                "already_correct": [{"vm": vm, "ip": ip} for vm, ip in result['already_correct']],
                "errors": result['errors'],
            }
            print(json.dumps(output))
        else:
            # Human-readable output
            print(f"\nSync Summary:")
            print(f"  Desired state: {len(result['desired_state'])} assignments")
            for vm, ip in result['desired_state']:
                print(f"    - {vm} → {ip}")

            if result['changes_made']:
                print(f"  Changes made: {len(result['changes_made'])}")
                for vm, ip in result['changes_made']:
                    print(f"    - {vm} → {ip}")
            else:
                print(f"  No changes needed - already in desired state")

            if result['errors']:
                print(f"  Errors: {len(result['errors'])}")
                for error in result['errors']:
                    print(f"    - {error}")

        if result['errors']:
            sys.exit(1)

    elif args.command == "assign":
        assign_ip_to_vm(args.vm, args.ip)
        print(f"Assigned IP label '{args.ip}' to VM label '{args.vm}'.")


if __name__ == "__main__":
    main()
