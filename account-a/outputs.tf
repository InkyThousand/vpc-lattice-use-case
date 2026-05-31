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
