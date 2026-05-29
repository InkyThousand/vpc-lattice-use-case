output "vpc_id" {
  description = "VPC ID for Account B"
  value       = module.networking.vpc_id
}

output "private_subnet_ids" {
  description = "Private subnet IDs for Lambda functions"
  value       = module.networking.private_subnet_ids
}

output "lambda_security_group_id" {
  description = "Security group ID for Lambda functions"
  value       = module.networking.lambda_security_group_id
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB inventory table"
  value       = module.lambda.dynamodb_table_name
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB inventory table"
  value       = module.lambda.dynamodb_table_arn
}
