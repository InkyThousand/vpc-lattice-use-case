variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "account_b_id" {
  description = "AWS Account ID for Account B (Inventory) — used for RAM share acceptance"
  type        = string
}

variable "inventory_service_arn" {
  description = "ARN of the VPC Lattice Inventory service shared from Account B — used for service association"
  type        = string
  default     = ""
}

variable "vpc_cidr" {
  description = "CIDR block for VPC-A"
  type        = string
  default     = "10.0.0.0/16"
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "availability_zones" {
  description = "Availability zones for subnets"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}
