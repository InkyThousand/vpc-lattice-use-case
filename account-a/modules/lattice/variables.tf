variable "vpc_id" {
  description = "ID of VPC-A to associate with the Service Network"
  type        = string
}

variable "service_network_name" {
  description = "Name tag for the VPC Lattice Service Network"
  type        = string
  default     = "orders-service-network"
}
