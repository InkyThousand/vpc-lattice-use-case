output "service_network_id" {
  description = "ID of the VPC Lattice Service Network"
  value       = aws_vpclattice_service_network.this.id
}

output "service_network_arn" {
  description = "ARN of the VPC Lattice Service Network"
  value       = aws_vpclattice_service_network.this.arn
}
