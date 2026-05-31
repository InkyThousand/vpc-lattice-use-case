# -----------------------------------------------------------------------
# DynamoDB table for Orders
# -----------------------------------------------------------------------
resource "aws_dynamodb_table" "orders" {
  name         = var.table_name
  billing_mode = "PAY_PER_REQUEST"

  hash_key = "order_id"

  attribute {
    name = "order_id"
    type = "S"
  }

  tags = {
    Name = var.table_name
  }
}

# -----------------------------------------------------------------------
# Seed the table with mock order records referencing sci-fi book IDs.
# Re-runs whenever the seed file content changes (hash-based trigger).
# -----------------------------------------------------------------------
resource "null_resource" "seed_orders" {
  triggers = {
    seed_hash = filemd5("${path.module}/seed_data/orders.json")
  }

  provisioner "local-exec" {
    command = <<-EOT
      aws dynamodb batch-write-item \
        --table-name ${aws_dynamodb_table.orders.name} \
        --request-items file://${path.module}/seed_data/orders.json \
        --region ${var.aws_region}
    EOT
  }

  depends_on = [aws_dynamodb_table.orders]
}

# -----------------------------------------------------------------------
# Lambda layer: install Python dependencies (requests, aws-requests-auth)
# -----------------------------------------------------------------------
resource "null_resource" "build_layer" {
  triggers = {
    requirements_hash = filemd5("${path.module}/requirements.txt")
  }

  provisioner "local-exec" {
    command = <<-EOT
      pip install -r ${path.module}/requirements.txt \
        --target ${path.module}/builds/python/lib/python3.11/site-packages \
        --upgrade --quiet && \
      cd ${path.module}/builds && zip -r orders_layer.zip python/
    EOT
  }
}

resource "aws_lambda_layer_version" "orders_deps" {
  layer_name          = "${var.name_prefix}-orders-deps"
  filename            = "${path.module}/builds/orders_layer.zip"
  compatible_runtimes = ["python3.11"]

  depends_on = [null_resource.build_layer]
}

# -----------------------------------------------------------------------
# Package Orders Lambda source into a zip archive
# -----------------------------------------------------------------------
data "archive_file" "orders" {
  type        = "zip"
  source_file = "${path.root}/lambda_src/orders/handler.py"
  output_path = "${path.module}/builds/orders.zip"
}

# -----------------------------------------------------------------------
# IAM execution role for Orders Lambda
# -----------------------------------------------------------------------
resource "aws_iam_role" "lambda_exec" {
  name = "${var.name_prefix}-orders-lambda-exec-role"

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
    Name = "${var.name_prefix}-orders-lambda-exec-role"
  }
}

resource "aws_iam_role_policy" "lambda_permissions" {
  name = "${var.name_prefix}-orders-lambda-policy"
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
        Resource = aws_dynamodb_table.orders.arn
      },
      {
        Effect   = "Allow"
        Action   = "vpc-lattice-svcs:Invoke"
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_vpc_execution" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# -----------------------------------------------------------------------
# Orders Lambda function
# -----------------------------------------------------------------------
resource "aws_lambda_function" "orders" {
  function_name    = "${var.name_prefix}-orders"
  role             = aws_iam_role.lambda_exec.arn
  runtime          = "python3.11"
  handler          = "handler.handler"
  filename         = data.archive_file.orders.output_path
  source_code_hash = data.archive_file.orders.output_base64sha256

  layers = [aws_lambda_layer_version.orders_deps.arn]

  vpc_config {
    subnet_ids         = var.subnet_ids
    security_group_ids = var.security_group_ids
  }

  environment {
    variables = {
      DYNAMODB_TABLE        = aws_dynamodb_table.orders.name
      INVENTORY_SERVICE_DNS = var.inventory_service_dns
    }
  }

  tags = {
    Name = "${var.name_prefix}-orders"
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_iam_role_policy_attachment.lambda_vpc_execution,
  ]
}
