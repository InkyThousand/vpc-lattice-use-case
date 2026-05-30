output "dynamodb_table_name" {
  description = "Name of the DynamoDB inventory table"
  value       = aws_dynamodb_table.inventory.name
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB inventory table"
  value       = aws_dynamodb_table.inventory.arn
}

output "lambda_v1_arn" {
  description = "ARN of Inventory Lambda v1"
  value       = aws_lambda_function.inventory_v1.arn
}

output "lambda_v2_arn" {
  description = "ARN of Inventory Lambda v2"
  value       = aws_lambda_function.inventory_v2.arn
}

output "lambda_execution_role_arn" {
  description = "ARN of the Lambda IAM execution role"
  value       = aws_iam_role.lambda_exec.arn
}
