variable "vpc_id" {
  description = "ID of VPC-A to associate with the Service Network"
  type        = string
}

variable "service_network_name" {
  description = "Name tag for the VPC Lattice Service Network"
  type        = string
  default     = "orders-service-network"
}

variable "inventory_service_arn" {
  description = "ARN of the VPC Lattice Inventory service shared from Account B — used for service association"
  type        = string
  default     = ""
}

variable "ram_share_arn" {
  description = "ARN of the AWS RAM resource share from Account B — used to accept the Inventory service share"
  type        = string
  default     = ""
}
