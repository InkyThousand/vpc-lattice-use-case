output "target_group_v1_arn" {
  description = "ARN of the VPC Lattice target group for Inventory v1"
  value       = aws_vpclattice_target_group.inventory_v1.arn
}

output "target_group_v2_arn" {
  description = "ARN of the VPC Lattice target group for Inventory v2"
  value       = aws_vpclattice_target_group.inventory_v2.arn
}

output "lattice_service_arn" {
  description = "ARN of the VPC Lattice Inventory service"
  value       = aws_vpclattice_service.inventory.arn
}

output "lattice_service_id" {
  description = "ID of the VPC Lattice Inventory service"
  value       = aws_vpclattice_service.inventory.id
}

output "lattice_service_dns_name" {
  description = "DNS name of the VPC Lattice Inventory service"
  value       = aws_vpclattice_service.inventory.dns_entry[0].domain_name
}

output "lattice_listener_arn" {
  description = "ARN of the VPC Lattice HTTP listener"
  value       = aws_vpclattice_listener.inventory_http.arn
}

output "ram_share_arn" {
  description = "ARN of the AWS RAM resource share for the Inventory service"
  value       = aws_ram_resource_share.inventory_service_share.arn
}
