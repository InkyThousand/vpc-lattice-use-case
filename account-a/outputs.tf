output "vpc_id" {
  description = "VPC ID for Account A"
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

output "orders_lambda_role_arn" {
  description = "IAM role ARN of the Orders Lambda — provide this to Account B for its auth policy"
  value       = module.lambda.orders_lambda_role_arn
}

output "service_network_arn" {
  description = "ARN of the VPC Lattice Service Network"
  value       = module.lattice.service_network_arn
}

output "orders_lambda_name" {
  description = "Name of the Orders Lambda function"
  value       = module.lambda.orders_lambda_name
}

output "orders_lambda_invoke_command" {
  description = "Sample AWS CLI command to invoke the Orders Lambda with a test order"
  value       = "aws lambda invoke --function-name ${module.lambda.orders_lambda_name} --payload '{\"order_id\":\"ord-001\"}' --cli-binary-format raw-in-base64-out /tmp/orders_response.json && cat /tmp/orders_response.json"
}
