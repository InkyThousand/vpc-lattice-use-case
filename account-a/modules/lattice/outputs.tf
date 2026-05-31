output "service_network_id" {
  description = "ID of the VPC Lattice Service Network"
  value       = aws_vpclattice_service_network.this.id
}

output "service_network_arn" {
  description = "ARN of the VPC Lattice Service Network"
  value       = aws_vpclattice_service_network.this.arn
}

output "inventory_service_association_id" {
  description = "ID of the Inventory service association with the Service Network"
  value       = length(aws_vpclattice_service_network_service_association.inventory) > 0 ? aws_vpclattice_service_network_service_association.inventory[0].id : null
}
