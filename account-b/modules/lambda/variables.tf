variable "aws_region" {
  description = "AWS region where resources are deployed"
  type        = string
}

variable "table_name" {
  description = "Name of the DynamoDB inventory table"
  type        = string
  default     = "inventory"
}

variable "name_prefix" {
  description = "Prefix for naming Lambda functions and IAM resources"
  type        = string
  default     = "vpc-lattice-demo"
}
