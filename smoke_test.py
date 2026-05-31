#!/usr/bin/env python3
"""
Smoke test for the VPC Lattice demo.

Invokes the Orders Lambda multiple times via boto3 and prints the
v1/v2 distribution of Inventory responses to verify weighted routing
(expect ~80% v1 / 20% v2).

Usage:
    python smoke_test.py [--function-name NAME] [--region REGION] [--count N]

Environment variables (used as defaults):
    ORDERS_LAMBDA_NAME  - Orders Lambda function name
    AWS_REGION          - AWS region (default: us-east-1)
"""

import argparse
import json
import os
import sys
from collections import Counter

import boto3
from botocore.exceptions import BotoCoreError, ClientError

DEFAULT_FUNCTION_NAME = os.environ.get("ORDERS_LAMBDA_NAME", "orders")
DEFAULT_REGION = os.environ.get("AWS_REGION", "us-east-1")
DEFAULT_COUNT = 10
TEST_PAYLOAD = {"order_id": "ord-001"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke test: invoke Orders Lambda N times and report inventory version distribution."
    )
    parser.add_argument(
        "--function-name",
        default=DEFAULT_FUNCTION_NAME,
        help=f"Orders Lambda function name (default: '{DEFAULT_FUNCTION_NAME}' / env ORDERS_LAMBDA_NAME)",
    )
    parser.add_argument(
        "--region",
        default=DEFAULT_REGION,
        help=f"AWS region (default: '{DEFAULT_REGION}' / env AWS_REGION)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_COUNT,
        help=f"Number of Lambda invocations (default: {DEFAULT_COUNT})",
    )
    return parser.parse_args()


def invoke_orders_lambda(client, function_name: str, invocation_number: int) -> dict:
    """
    Invoke the Orders Lambda and return a result dict with keys:
      - invocation: int
      - status_code: int (HTTP status from Lambda response body)
      - version: str | None  (inventory.version if present)
      - error: str | None    (description if something went wrong)
    """
    result = {"invocation": invocation_number, "status_code": None, "version": None, "error": None}

    try:
        response = client.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(TEST_PAYLOAD).encode(),
        )
    except ClientError as exc:
        result["error"] = f"ClientError: {exc.response['Error']['Code']} — {exc.response['Error']['Message']}"
        return result
    except BotoCoreError as exc:
        result["error"] = f"BotoCoreError: {exc}"
        return result

    # Read the raw Lambda response payload
    try:
        raw_payload = response["Payload"].read()
        lambda_response = json.loads(raw_payload)
    except (json.JSONDecodeError, KeyError) as exc:
        result["error"] = f"Failed to parse Lambda response payload: {exc}"
        return result

    # Check for Lambda-level function errors (unhandled exceptions)
    if response.get("FunctionError"):
        result["error"] = f"Lambda function error ({response['FunctionError']}): {lambda_response}"
        return result

    # The handler returns { "statusCode": int, "body": "<json string>" }
    status_code = lambda_response.get("statusCode")
    result["status_code"] = status_code

    if status_code != 200:
        # Attempt to surface the error detail from the body
        body_raw = lambda_response.get("body", "{}")
        try:
            body = json.loads(body_raw) if isinstance(body_raw, str) else body_raw
            result["error"] = f"HTTP {status_code}: {body}"
        except json.JSONDecodeError:
            result["error"] = f"HTTP {status_code}: {body_raw}"
        return result

    # Parse the body and extract inventory.version
    body_raw = lambda_response.get("body", "{}")
    try:
        body = json.loads(body_raw) if isinstance(body_raw, str) else body_raw
    except json.JSONDecodeError as exc:
        result["error"] = f"Failed to parse response body JSON: {exc}"
        return result

    inventory = body.get("inventory")
    if not isinstance(inventory, dict):
        result["error"] = "Response body missing 'inventory' object"
        return result

    version = inventory.get("version")
    if version is None:
        result["error"] = "inventory object missing 'version' field"
        return result

    result["version"] = version
    return result


def main() -> int:
    args = parse_args()

    print(f"Smoke test — Orders Lambda weighted routing")
    print(f"  Function : {args.function_name}")
    print(f"  Region   : {args.region}")
    print(f"  Count    : {args.count}")
    print(f"  Payload  : {json.dumps(TEST_PAYLOAD)}")
    print()

    try:
        client = boto3.client("lambda", region_name=args.region)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Failed to create boto3 Lambda client: {exc}", file=sys.stderr)
        return 1

    results = []
    for i in range(1, args.count + 1):
        print(f"  [{i:>3}/{args.count}] invoking...", end=" ", flush=True)
        result = invoke_orders_lambda(client, args.function_name, i)
        results.append(result)

        if result["error"]:
            print(f"ERROR — {result['error']}")
        else:
            print(f"OK — inventory.version = {result['version']}")

    # ── Summary ──────────────────────────────────────────────────────────────
    print()
    print("=" * 50)
    print("RESULTS SUMMARY")
    print("=" * 50)

    errors = [r for r in results if r["error"]]
    successes = [r for r in results if r["version"] is not None]

    if errors:
        print(f"\nErrors ({len(errors)}/{args.count}):")
        for r in errors:
            print(f"  invocation {r['invocation']}: {r['error']}")

    if successes:
        version_counts: Counter = Counter(r["version"] for r in successes)
        total_success = len(successes)

        print(f"\nVersion distribution ({total_success} successful invocations):")
        for version in sorted(version_counts):
            count = version_counts[version]
            pct = count / total_success * 100
            bar = "█" * int(pct / 2)
            print(f"  {version:>4} : {count:>3} / {total_success}  ({pct:5.1f}%)  {bar}")

        print()
        print(f"Expected: ~80% v1 / ~20% v2  (configured weights)")

        # Warn if distribution looks very off (more than 3x the expected error for N samples)
        v1_pct = version_counts.get("v1", 0) / total_success * 100
        if total_success >= 5:
            if v1_pct < 50:
                print(
                    f"\n⚠  WARNING: v1 share ({v1_pct:.1f}%) is well below the expected 80%."
                    " Check your Lattice listener rule weights."
                )
            elif v1_pct > 99:
                print(
                    f"\n⚠  WARNING: v1 share is 100% — v2 may not be receiving any traffic."
                    " This can happen with small sample sizes, but worth verifying."
                )
    else:
        print("\nNo successful invocations — cannot compute version distribution.")

    print()
    exit_code = 0 if len(errors) == 0 else 1
    if exit_code == 0:
        print("✓ Smoke test passed — all invocations succeeded.")
    else:
        print(f"✗ Smoke test finished with {len(errors)} error(s).")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
