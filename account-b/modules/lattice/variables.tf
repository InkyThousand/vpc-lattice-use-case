variable "lambda_v1_arn" {
  description = "ARN of the Inventory Lambda v1 function"
  type        = string
}

variable "lambda_v2_arn" {
  description = "ARN of the Inventory Lambda v2 function"
  type        = string
}

variable "weight_v1" {
  description = "Traffic weight for Inventory Lambda v1 (out of weight_v1 + weight_v2)"
  type        = number
  default     = 80
}

variable "weight_v2" {
  description = "Traffic weight for Inventory Lambda v2 (out of weight_v1 + weight_v2)"
  type        = number
  default     = 20
}

variable "orders_lambda_role_arn" {
  description = "IAM role ARN of the Orders Lambda in Account A — used in Lattice auth policy"
  type        = string
  default     = ""
}

variable "account_a_id" {
  description = "AWS Account ID for Account A (Orders) — used for RAM share"
  type        = string
  default     = ""
}
