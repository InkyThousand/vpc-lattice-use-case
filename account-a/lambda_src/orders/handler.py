import json
import os

import boto3
import requests
import requests.exceptions
from aws_requests_auth.aws_auth import AWSRequestsAuth

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "orders")
INVENTORY_SERVICE_DNS = os.environ.get("INVENTORY_SERVICE_DNS", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


def _get_order(order_id: str) -> dict | None:
    table = dynamodb.Table(TABLE_NAME)
    response = table.get_item(Key={"order_id": order_id})
    return response.get("Item")


def _call_inventory(item_id: str) -> dict:
    """
    Call the Inventory service via VPC Lattice DNS with SigV4 signing.

    Returns the parsed JSON body from the Inventory Lambda response.
    Raises RuntimeError with a structured error dict on failure.
    """
    url = f"http://{INVENTORY_SERVICE_DNS}/?item_id={item_id}"

    session = boto3.session.Session()
    credentials = session.get_credentials().get_frozen_credentials()

    auth = AWSRequestsAuth(
        aws_access_key=credentials.access_key,
        aws_secret_access_key=credentials.secret_key,
        aws_token=credentials.token,
        aws_host=INVENTORY_SERVICE_DNS,
        aws_region=AWS_REGION,
        aws_service="vpc-lattice-svcs",
    )

    try:
        resp = requests.get(url, auth=auth, timeout=5)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        raise RuntimeError(json.dumps({"statusCode": 503, "error": "inventory_unavailable"}))

    if resp.status_code == 403:
        raise RuntimeError(json.dumps({"statusCode": 403, "error": "auth_denied"}))

    if resp.status_code == 404:
        raise RuntimeError(json.dumps({"statusCode": 404, "error": "item_not_found"}))

    if resp.status_code != 200:
        raise RuntimeError(json.dumps({"statusCode": 503, "error": "inventory_unavailable"}))

    # Inventory Lambda returns body as a JSON string (Lambda proxy integration)
    raw_body = resp.json()
    if isinstance(raw_body, dict) and "body" in raw_body:
        body = raw_body["body"]
        if isinstance(body, str):
            return json.loads(body)
        return body

    return raw_body


def handler(event, context):
    try:
        # Support both direct dict payload and JSON-string body (Lambda URL / proxy)
        if isinstance(event.get("body"), str):
            payload = json.loads(event["body"])
        elif isinstance(event.get("body"), dict):
            payload = event["body"]
        else:
            payload = event

        order_id = payload.get("order_id")
        if not order_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "missing_parameter", "detail": "order_id is required"}),
            }

        # --- DynamoDB lookup ---
        order = _get_order(order_id)
        if not order:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "order_not_found", "order_id": order_id}),
            }

        item_id = order["item_id"]

        # --- Inventory service call ---
        inventory = _call_inventory(item_id)

        # --- Assemble response ---
        response_body = {
            "order_id": order_id,
            "book": {
                "item_id": item_id,
                "title": inventory.get("title"),
            },
            "inventory": {
                "item_id": inventory.get("item_id"),
                "quantity": inventory.get("quantity"),
                "available": inventory.get("available"),
                "version": inventory.get("version"),
            },
        }

        return {
            "statusCode": 200,
            "body": json.dumps(response_body),
        }

    except RuntimeError as exc:
        # Structured errors raised by _call_inventory
        try:
            error_payload = json.loads(str(exc))
            return {
                "statusCode": error_payload["statusCode"],
                "body": json.dumps({k: v for k, v in error_payload.items() if k != "statusCode"}),
            }
        except (json.JSONDecodeError, KeyError):
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "internal_error", "detail": str(exc)}),
            }

    except Exception as exc:  # noqa: BLE001
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "internal_error", "detail": str(exc)}),
        }
