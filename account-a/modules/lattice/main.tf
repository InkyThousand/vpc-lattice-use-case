resource "aws_vpclattice_service_network" "this" {
  name      = var.service_network_name
  auth_type = "AWS_IAM"

  tags = {
    Name = var.service_network_name
  }
}

resource "aws_vpclattice_service_network_vpc_association" "this" {
  vpc_identifier             = var.vpc_id
  service_network_identifier = aws_vpclattice_service_network.this.id
}

resource "aws_ram_resource_share_accepter" "inventory_share" {
  count     = var.ram_share_arn != "" ? 1 : 0
  share_arn = var.ram_share_arn
}

resource "aws_vpclattice_service_network_service_association" "inventory" {
  count                      = var.inventory_service_arn != "" ? 1 : 0
  service_identifier         = var.inventory_service_arn
  service_network_identifier = aws_vpclattice_service_network.this.id

  depends_on = [aws_ram_resource_share_accepter.inventory_share]
}
