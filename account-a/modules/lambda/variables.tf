variable "aws_region" {
  description = "AWS region where resources are deployed"
  type        = string
}

variable "table_name" {
  description = "Name of the DynamoDB orders table"
  type        = string
  default     = "orders"
}

variable "name_prefix" {
  description = "Prefix for naming Lambda functions and IAM resources"
  type        = string
  default     = "vpc-lattice-demo"
}

variable "inventory_service_dns" {
  description = "VPC Lattice DNS hostname for the Inventory service"
  type        = string
  default     = ""
}

variable "subnet_ids" {
  description = "Subnet IDs for Lambda VPC configuration"
  type        = list(string)
}

variable "security_group_ids" {
  description = "Security group IDs for Lambda VPC configuration"
  type        = list(string)
}
