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
