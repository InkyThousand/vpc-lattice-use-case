"""
Unit tests for Inventory Lambda handlers (v1 and v2).

Validates Requirements 2.2 and 2.3:
  - 2.2: Requests to the Inventory Lattice service are routed to the Lambda function.
  - 2.3: Inventory Lambda queries DynamoDB and returns JSON with fields:
         item_id, title, author, quantity, available (plus version).
"""

import json
import os
import sys

import boto3
import pytest
from moto import mock_aws

# ---------------------------------------------------------------------------
# Path setup — allow importing handlers from lambda_src without installing them
# ---------------------------------------------------------------------------
ACCOUNT_B_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V1_DIR = os.path.join(ACCOUNT_B_DIR, "lambda_src", "inventory_v1")
V2_DIR = os.path.join(ACCOUNT_B_DIR, "lambda_src", "inventory_v2")

# ---------------------------------------------------------------------------
# Seed data matching the DynamoDB inventory table
# ---------------------------------------------------------------------------
SEED_ITEMS = [
    {"item_id": "dune-001",        "title": "Dune",                      "author": "Frank Herbert",     "quantity": 42, "available": True},
    {"item_id": "foundation-001",  "title": "Foundation",                "author": "Isaac Asimov",      "quantity": 17, "available": True},
    {"item_id": "neuromancer-001", "title": "Neuromancer",               "author": "William Gibson",    "quantity": 5,  "available": True},
    {"item_id": "lefthand-001",    "title": "The Left Hand of Darkness", "author": "Ursula K. Le Guin", "quantity": 0,  "available": False},
    {"item_id": "hyperion-001",    "title": "Hyperion",                  "author": "Dan Simmons",       "quantity": 23, "available": True},
]

TABLE_NAME = "inventory"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_table_and_seed(dynamodb_resource):
    """Create the inventory DynamoDB table and populate it with seed data."""
    table = dynamodb_resource.create_table(
        TableName=TABLE_NAME,
        KeySchema=[{"AttributeName": "item_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "item_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    for item in SEED_ITEMS:
        table.put_item(Item=item)
    return table


def _make_event(item_id=None):
    """Build a minimal VPC Lattice-style Lambda event."""
    params = {"item_id": item_id} if item_id is not None else {}
    return {"queryStringParameters": params}


def _load_handler(version_dir):
    """Import a handler module from the given directory path."""
    if version_dir not in sys.path:
        sys.path.insert(0, version_dir)
    import importlib
    # Each handler lives in handler.py; use a unique module name per version
    module_name = f"handler_{os.path.basename(version_dir)}"
    spec = importlib.util.spec_from_file_location(module_name, os.path.join(version_dir, "handler.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


# ---------------------------------------------------------------------------
# Tests — Inventory v1
# ---------------------------------------------------------------------------

class TestInventoryV1:
    """Tests for the inventory_v1 handler."""

    @mock_aws
    def test_successful_item_retrieval_returns_v1(self, monkeypatch):
        """
        Validates: Requirements 2.3
        A valid item_id returns HTTP 200 with all required fields and version='v1'.
        """
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_table_and_seed(dynamodb)

        # Re-import so the module picks up the mocked boto3 resource
        mod = _load_handler(V1_DIR)
        # Patch the module-level dynamodb resource to use the mocked one
        mod.dynamodb = dynamodb

        event = _make_event("dune-001")
        result = mod.handler(event, {})

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["item_id"] == "dune-001"
        assert body["title"] == "Dune"
        assert body["author"] == "Frank Herbert"
        assert body["quantity"] == 42
        assert body["available"] is True
        assert body["version"] == "v1"

    @mock_aws
    def test_all_required_fields_present_v1(self, monkeypatch):
        """
        Validates: Requirements 2.3
        Response body contains exactly the required fields: item_id, title, author,
        quantity, available, version.
        """
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_table_and_seed(dynamodb)

        mod = _load_handler(V1_DIR)
        mod.dynamodb = dynamodb

        result = mod.handler(_make_event("foundation-001"), {})
        body = json.loads(result["body"])

        required_fields = {"item_id", "title", "author", "quantity", "available", "version"}
        assert required_fields.issubset(body.keys())

    @mock_aws
    def test_item_not_found_returns_404_v1(self):
        """
        Validates: Requirements 2.3
        An unknown item_id returns HTTP 404 with an appropriate error payload.
        """
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_table_and_seed(dynamodb)

        mod = _load_handler(V1_DIR)
        mod.dynamodb = dynamodb

        result = mod.handler(_make_event("nonexistent-999"), {})

        assert result["statusCode"] == 404
        body = json.loads(result["body"])
        assert body["error"] == "item_not_found"
        assert body["item_id"] == "nonexistent-999"

    @mock_aws
    def test_missing_item_id_returns_400_v1(self):
        """
        Validates: Requirements 2.3
        A request without item_id returns HTTP 400.
        """
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_table_and_seed(dynamodb)

        mod = _load_handler(V1_DIR)
        mod.dynamodb = dynamodb

        result = mod.handler(_make_event(), {})

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["error"] == "missing_parameter"

    @mock_aws
    def test_exception_handling_returns_500_v1(self):
        """
        Validates: Requirements 2.3
        When DynamoDB raises an unexpected exception the handler returns HTTP 500.
        """
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        # Intentionally do NOT create the table — get_item will raise an exception
        mod = _load_handler(V1_DIR)
        mod.dynamodb = dynamodb

        result = mod.handler(_make_event("dune-001"), {})

        assert result["statusCode"] == 500
        body = json.loads(result["body"])
        assert body["error"] == "internal_error"
        assert "detail" in body

    @mock_aws
    def test_available_false_item_v1(self):
        """
        Validates: Requirements 2.3
        Items with available=False are returned correctly (not filtered out).
        """
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_table_and_seed(dynamodb)

        mod = _load_handler(V1_DIR)
        mod.dynamodb = dynamodb

        result = mod.handler(_make_event("lefthand-001"), {})

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["available"] is False
        assert body["quantity"] == 0
        assert body["version"] == "v1"


# ---------------------------------------------------------------------------
# Tests — Inventory v2
# ---------------------------------------------------------------------------

class TestInventoryV2:
    """Tests for the inventory_v2 handler."""

    @mock_aws
    def test_successful_item_retrieval_returns_v2(self):
        """
        Validates: Requirements 2.3, 5.2
        A valid item_id returns HTTP 200 with all required fields and version='v2'.
        """
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_table_and_seed(dynamodb)

        mod = _load_handler(V2_DIR)
        mod.dynamodb = dynamodb

        event = _make_event("hyperion-001")
        result = mod.handler(event, {})

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["item_id"] == "hyperion-001"
        assert body["title"] == "Hyperion"
        assert body["author"] == "Dan Simmons"
        assert body["quantity"] == 23
        assert body["available"] is True
        assert body["version"] == "v2"

    @mock_aws
    def test_version_field_differs_between_v1_and_v2(self):
        """
        Validates: Requirements 5.2
        v1 and v2 handlers return different version strings for the same item.
        """
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_table_and_seed(dynamodb)

        mod_v1 = _load_handler(V1_DIR)
        mod_v1.dynamodb = dynamodb

        mod_v2 = _load_handler(V2_DIR)
        mod_v2.dynamodb = dynamodb

        event = _make_event("dune-001")
        result_v1 = mod_v1.handler(event, {})
        result_v2 = mod_v2.handler(event, {})

        body_v1 = json.loads(result_v1["body"])
        body_v2 = json.loads(result_v2["body"])

        assert body_v1["version"] == "v1"
        assert body_v2["version"] == "v2"

    @mock_aws
    def test_item_not_found_returns_404_v2(self):
        """
        Validates: Requirements 2.3
        An unknown item_id returns HTTP 404 with an appropriate error payload.
        """
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_table_and_seed(dynamodb)

        mod = _load_handler(V2_DIR)
        mod.dynamodb = dynamodb

        result = mod.handler(_make_event("nonexistent-999"), {})

        assert result["statusCode"] == 404
        body = json.loads(result["body"])
        assert body["error"] == "item_not_found"
        assert body["item_id"] == "nonexistent-999"

    @mock_aws
    def test_missing_item_id_returns_400_v2(self):
        """
        Validates: Requirements 2.3
        A request without item_id returns HTTP 400.
        """
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_table_and_seed(dynamodb)

        mod = _load_handler(V2_DIR)
        mod.dynamodb = dynamodb

        result = mod.handler(_make_event(), {})

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["error"] == "missing_parameter"

    @mock_aws
    def test_exception_handling_returns_500_v2(self):
        """
        Validates: Requirements 2.3
        When DynamoDB raises an unexpected exception the handler returns HTTP 500.
        """
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        # Intentionally do NOT create the table
        mod = _load_handler(V2_DIR)
        mod.dynamodb = dynamodb

        result = mod.handler(_make_event("dune-001"), {})

        assert result["statusCode"] == 500
        body = json.loads(result["body"])
        assert body["error"] == "internal_error"
        assert "detail" in body
