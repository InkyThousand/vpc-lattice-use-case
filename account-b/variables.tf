variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "account_a_id" {
  description = "AWS Account ID for Account A (Orders) — used for RAM share"
  type        = string
}

variable "orders_lambda_role_arn" {
  description = "IAM role ARN of the Orders Lambda in Account A — used in Lattice auth policy"
  type        = string
  default     = ""
}

variable "inventory_v1_weight" {
  description = "Traffic weight for Inventory Lambda v1"
  type        = number
  default     = 80
}

variable "inventory_v2_weight" {
  description = "Traffic weight for Inventory Lambda v2"
  type        = number
  default     = 20
}

variable "vpc_cidr" {
  description = "CIDR block for VPC-B"
  type        = string
  default     = "10.1.0.0/16"
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.1.1.0/24", "10.1.2.0/24"]
}

variable "availability_zones" {
  description = "Availability zones for subnets"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}
