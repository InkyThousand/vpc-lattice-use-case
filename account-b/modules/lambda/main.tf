# -----------------------------------------------------------------------
# DynamoDB table for Inventory
# -----------------------------------------------------------------------
resource "aws_dynamodb_table" "inventory" {
  name         = var.table_name
  billing_mode = "PAY_PER_REQUEST"

  hash_key = "item_id"

  attribute {
    name = "item_id"
    type = "S"
  }

  tags = {
    Name = var.table_name
  }
}

# -----------------------------------------------------------------------
# Seed the table with sci-fi book records
# Re-runs whenever the seed file content changes (hash-based trigger).
# -----------------------------------------------------------------------
resource "null_resource" "seed_inventory" {
  triggers = {
    seed_hash = filemd5("${path.module}/seed_data/inventory.json")
  }

  provisioner "local-exec" {
    command = <<-EOT
      aws dynamodb batch-write-item \
        --table-name ${aws_dynamodb_table.inventory.name} \
        --request-items file://${path.module}/seed_data/inventory.json \
        --region ${var.aws_region}
    EOT
  }

  depends_on = [aws_dynamodb_table.inventory]
}

# -----------------------------------------------------------------------
# Package Lambda source files into zip archives
# -----------------------------------------------------------------------
data "archive_file" "inventory_v1" {
  type        = "zip"
  source_file = "${path.root}/lambda_src/inventory_v1/handler.py"
  output_path = "${path.module}/builds/inventory_v1.zip"
}

data "archive_file" "inventory_v2" {
  type        = "zip"
  source_file = "${path.root}/lambda_src/inventory_v2/handler.py"
  output_path = "${path.module}/builds/inventory_v2.zip"
}

# -----------------------------------------------------------------------
# IAM execution role for Inventory Lambda functions
# -----------------------------------------------------------------------
resource "aws_iam_role" "lambda_exec" {
  name = "${var.name_prefix}-lambda-exec-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "lambda.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name = "${var.name_prefix}-lambda-exec-role"
  }
}

resource "aws_iam_role_policy" "lambda_dynamodb" {
  name = "${var.name_prefix}-lambda-dynamodb-policy"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = aws_dynamodb_table.inventory.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# -----------------------------------------------------------------------
# Inventory Lambda v1
# -----------------------------------------------------------------------
resource "aws_lambda_function" "inventory_v1" {
  function_name    = "${var.name_prefix}-inventory-v1"
  role             = aws_iam_role.lambda_exec.arn
  runtime          = "python3.11"
  handler          = "handler.handler"
  filename         = data.archive_file.inventory_v1.output_path
  source_code_hash = data.archive_file.inventory_v1.output_base64sha256

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.inventory.name
    }
  }

  tags = {
    Name = "${var.name_prefix}-inventory-v1"
  }

  depends_on = [aws_iam_role_policy_attachment.lambda_basic_execution]
}

# -----------------------------------------------------------------------
# Inventory Lambda v2
# -----------------------------------------------------------------------
resource "aws_lambda_function" "inventory_v2" {
  function_name    = "${var.name_prefix}-inventory-v2"
  role             = aws_iam_role.lambda_exec.arn
  runtime          = "python3.11"
  handler          = "handler.handler"
  filename         = data.archive_file.inventory_v2.output_path
  source_code_hash = data.archive_file.inventory_v2.output_base64sha256

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.inventory.name
    }
  }

  tags = {
    Name = "${var.name_prefix}-inventory-v2"
  }

  depends_on = [aws_iam_role_policy_attachment.lambda_basic_execution]
}
