"""
Unit tests for Orders Lambda handler.

Validates Requirements 3.3 and 3.4:
  - 3.3: When the Inventory service responds, the Orders Lambda SHALL return a combined
         JSON response including: order_id, book (from DynamoDB Orders table), and
         inventory (from Inventory service).
  - 3.4: When the Inventory service is unavailable or returns an error, the Orders Lambda
         SHALL return a structured error response with HTTP 503.
"""

import importlib
import importlib.util
import json
import os
import sys
from unittest.mock import MagicMock, patch

import boto3
import pytest
import responses as responses_lib
from moto import mock_aws

# ---------------------------------------------------------------------------
# Path setup — allow importing the handler without installing it
# ---------------------------------------------------------------------------
ACCOUNT_A_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORDERS_DIR = os.path.join(ACCOUNT_A_DIR, "lambda_src", "orders")

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------
TABLE_NAME = "orders"

SEED_ORDERS = [
    {"order_id": "ord-001", "item_id": "dune-001",        "customer": "user-42", "status": "pending"},
    {"order_id": "ord-002", "item_id": "neuromancer-001", "customer": "user-07", "status": "pending"},
    {"order_id": "ord-003", "item_id": "hyperion-001",    "customer": "user-13", "status": "pending"},
]

INVENTORY_DNS = "inventory.example.vpc-lattice.io"

# Simulated Inventory service response (Lambda proxy integration format)
INVENTORY_RESPONSE_BODY = {
    "item_id": "dune-001",
    "title": "Dune",
    "author": "Frank Herbert",
    "quantity": 42,
    "available": True,
    "version": "v1",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_table_and_seed(dynamodb_resource):
    """Create the orders DynamoDB table and populate it with seed data."""
    table = dynamodb_resource.create_table(
        TableName=TABLE_NAME,
        KeySchema=[{"AttributeName": "order_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "order_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    for item in SEED_ORDERS:
        table.put_item(Item=item)
    return table


def _load_handler():
    """Import the orders handler module fresh (bypasses module cache issues)."""
    module_name = "orders_handler"
    spec = importlib.util.spec_from_file_location(
        module_name, os.path.join(ORDERS_DIR, "handler.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_event(order_id=None):
    """Build a minimal Lambda invocation event."""
    if order_id is not None:
        return {"order_id": order_id}
    return {}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def aws_credentials(monkeypatch):
    """Ensure boto3 uses fake credentials so moto intercepts all calls."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("DYNAMODB_TABLE", TABLE_NAME)
    monkeypatch.setenv("INVENTORY_SERVICE_DNS", INVENTORY_DNS)
    monkeypatch.setenv("AWS_REGION", "us-east-1")


# ---------------------------------------------------------------------------
# Tests — successful combined response
# ---------------------------------------------------------------------------

class TestOrdersHandlerSuccess:
    """Tests for the happy-path combined order + inventory response."""

    @mock_aws
    @responses_lib.activate
    def test_successful_order_and_inventory_response(self):
        """
        Validates: Requirements 3.3
        A valid order_id returns HTTP 200 with a combined response containing
        order_id, book (item_id + title), and inventory (item_id, quantity,
        available, version).
        """
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_table_and_seed(dynamodb)

        # Stub the Inventory HTTP call — returns Lambda proxy integration format
        responses_lib.add(
            responses_lib.GET,
            f"http://{INVENTORY_DNS}/",
            json={"body": json.dumps(INVENTORY_RESPONSE_BODY)},
            status=200,
        )

        mod = _load_handler()
        mod.dynamodb = dynamodb

        result = mod.handler(_make_event("ord-001"), {})

        assert result["statusCode"] == 200
        body = json.loads(result["body"])

        assert body["order_id"] == "ord-001"

        assert "book" in body
        assert body["book"]["item_id"] == "dune-001"
        assert body["book"]["title"] == "Dune"

        assert "inventory" in body
        assert body["inventory"]["item_id"] == "dune-001"
        assert body["inventory"]["quantity"] == 42
        assert body["inventory"]["available"] is True
        assert body["inventory"]["version"] == "v1"

    @mock_aws
    @responses_lib.activate
    def test_all_required_response_fields_present(self):
        """
        Validates: Requirements 3.3
        The combined response contains all required top-level fields:
        order_id, book, inventory.
        """
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_table_and_seed(dynamodb)

        responses_lib.add(
            responses_lib.GET,
            f"http://{INVENTORY_DNS}/",
            json={"body": json.dumps(INVENTORY_RESPONSE_BODY)},
            status=200,
        )

        mod = _load_handler()
        mod.dynamodb = dynamodb

        result = mod.handler(_make_event("ord-001"), {})
        body = json.loads(result["body"])

        assert {"order_id", "book", "inventory"}.issubset(body.keys())

    @mock_aws
    @responses_lib.activate
    def test_inventory_response_as_plain_dict(self):
        """
        Validates: Requirements 3.3
        Handler correctly handles an Inventory response that returns a plain dict
        (not wrapped in a Lambda proxy 'body' key).
        """
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_table_and_seed(dynamodb)

        # Inventory returns a plain JSON dict (no 'body' wrapper)
        responses_lib.add(
            responses_lib.GET,
            f"http://{INVENTORY_DNS}/",
            json=INVENTORY_RESPONSE_BODY,
            status=200,
        )

        mod = _load_handler()
        mod.dynamodb = dynamodb

        result = mod.handler(_make_event("ord-001"), {})

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["inventory"]["quantity"] == 42

    @mock_aws
    @responses_lib.activate
    def test_event_with_body_string_payload(self):
        """
        Validates: Requirements 3.3
        Handler correctly parses order_id from a JSON-string 'body' field
        (Lambda URL / API Gateway proxy integration format).
        """
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_table_and_seed(dynamodb)

        responses_lib.add(
            responses_lib.GET,
            f"http://{INVENTORY_DNS}/",
            json={"body": json.dumps(INVENTORY_RESPONSE_BODY)},
            status=200,
        )

        mod = _load_handler()
        mod.dynamodb = dynamodb

        event = {"body": json.dumps({"order_id": "ord-002"})}
        result = mod.handler(event, {})

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["order_id"] == "ord-002"
        assert body["book"]["item_id"] == "neuromancer-001"


# ---------------------------------------------------------------------------
# Tests — error handling (Requirement 3.4)
# ---------------------------------------------------------------------------

class TestOrdersHandlerErrors:
    """Tests for error scenarios: 503, 403, 404."""

    @mock_aws
    @responses_lib.activate
    def test_503_when_inventory_unreachable_connection_error(self):
        """
        Validates: Requirements 3.4
        When the Inventory service is unreachable (ConnectionError), the handler
        returns HTTP 503 with error='inventory_unavailable'.
        """
        import requests.exceptions as req_exc

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_table_and_seed(dynamodb)

        # Must use requests.exceptions.ConnectionError so the responses library
        # raises the correct exception type that the handler catches.
        responses_lib.add(
            responses_lib.GET,
            f"http://{INVENTORY_DNS}/",
            body=req_exc.ConnectionError("Connection refused"),
        )

        mod = _load_handler()
        mod.dynamodb = dynamodb

        result = mod.handler(_make_event("ord-001"), {})

        assert result["statusCode"] == 503
        body = json.loads(result["body"])
        assert body["error"] == "inventory_unavailable"

    @mock_aws
    @responses_lib.activate
    def test_503_when_inventory_returns_500(self):
        """
        Validates: Requirements 3.4
        When the Inventory service returns an unexpected 5xx error, the handler
        returns HTTP 503 with error='inventory_unavailable'.
        """
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_table_and_seed(dynamodb)

        responses_lib.add(
            responses_lib.GET,
            f"http://{INVENTORY_DNS}/",
            json={"error": "internal_error"},
            status=500,
        )

        mod = _load_handler()
        mod.dynamodb = dynamodb

        result = mod.handler(_make_event("ord-001"), {})

        assert result["statusCode"] == 503
        body = json.loads(result["body"])
        assert body["error"] == "inventory_unavailable"

    @mock_aws
    @responses_lib.activate
    def test_403_when_auth_denied(self):
        """
        Validates: Requirements 3.4
        When the Inventory Lattice service returns HTTP 403 (IAM auth denied),
        the handler returns HTTP 403 with error='auth_denied'.
        """
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_table_and_seed(dynamodb)

        responses_lib.add(
            responses_lib.GET,
            f"http://{INVENTORY_DNS}/",
            json={"Message": "Forbidden"},
            status=403,
        )

        mod = _load_handler()
        mod.dynamodb = dynamodb

        result = mod.handler(_make_event("ord-001"), {})

        assert result["statusCode"] == 403
        body = json.loads(result["body"])
        assert body["error"] == "auth_denied"

    @mock_aws
    @responses_lib.activate
    def test_404_when_inventory_item_not_found(self):
        """
        Validates: Requirements 3.4
        When the Inventory service returns HTTP 404 (item not found),
        the handler returns HTTP 404 with error='item_not_found'.
        """
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_table_and_seed(dynamodb)

        responses_lib.add(
            responses_lib.GET,
            f"http://{INVENTORY_DNS}/",
            json={"error": "item_not_found"},
            status=404,
        )

        mod = _load_handler()
        mod.dynamodb = dynamodb

        result = mod.handler(_make_event("ord-001"), {})

        assert result["statusCode"] == 404
        body = json.loads(result["body"])
        assert body["error"] == "item_not_found"

    @mock_aws
    def test_404_when_order_not_found_in_dynamodb(self):
        """
        Validates: Requirements 3.4
        When the order_id does not exist in the Orders DynamoDB table,
        the handler returns HTTP 404 with error='order_not_found'.
        """
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_table_and_seed(dynamodb)

        mod = _load_handler()
        mod.dynamodb = dynamodb

        result = mod.handler(_make_event("ord-nonexistent"), {})

        assert result["statusCode"] == 404
        body = json.loads(result["body"])
        assert body["error"] == "order_not_found"
        assert body["order_id"] == "ord-nonexistent"

    @mock_aws
    def test_400_when_order_id_missing(self):
        """
        Validates: Requirements 3.3
        When order_id is not provided in the event, the handler returns HTTP 400.
        """
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_table_and_seed(dynamodb)

        mod = _load_handler()
        mod.dynamodb = dynamodb

        result = mod.handler(_make_event(), {})

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["error"] == "missing_parameter"

    @mock_aws
    @responses_lib.activate
    def test_503_when_inventory_times_out(self):
        """
        Validates: Requirements 3.4
        When the Inventory service times out, the handler returns HTTP 503
        with error='inventory_unavailable'.
        """
        import requests.exceptions

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_table_and_seed(dynamodb)

        responses_lib.add(
            responses_lib.GET,
            f"http://{INVENTORY_DNS}/",
            body=requests.exceptions.Timeout("Request timed out"),
        )

        mod = _load_handler()
        mod.dynamodb = dynamodb

        result = mod.handler(_make_event("ord-001"), {})

        assert result["statusCode"] == 503
        body = json.loads(result["body"])
        assert body["error"] == "inventory_unavailable"
