output "dynamodb_table_name" {
  description = "Name of the DynamoDB orders table"
  value       = aws_dynamodb_table.orders.name
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB orders table"
  value       = aws_dynamodb_table.orders.arn
}

output "orders_lambda_arn" {
  description = "ARN of the Orders Lambda function"
  value       = aws_lambda_function.orders.arn
}

output "orders_lambda_name" {
  description = "Name of the Orders Lambda function"
  value       = aws_lambda_function.orders.function_name
}

output "orders_lambda_role_arn" {
  description = "IAM role ARN of the Orders Lambda — provide this to Account B for its auth policy"
  value       = aws_iam_role.lambda_exec.arn
}
