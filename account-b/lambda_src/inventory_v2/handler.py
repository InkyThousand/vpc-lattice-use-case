import json
import os
import boto3

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "inventory")


def handler(event, context):
    try:
        query_params = event.get("queryStringParameters") or {}
        item_id = query_params.get("item_id")

        if not item_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "missing_parameter", "detail": "item_id is required"})
            }

        table = dynamodb.Table(TABLE_NAME)
        response = table.get_item(Key={"item_id": item_id})
        item = response.get("Item")

        if not item:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "item_not_found", "item_id": item_id})
            }

        return {
            "statusCode": 200,
            "body": json.dumps({
                "item_id": item["item_id"],
                "title": item["title"],
                "author": item["author"],
                "quantity": int(item["quantity"]),
                "available": bool(item["available"]),
                "version": "v2"
            })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "internal_error", "detail": str(e)})
        }
