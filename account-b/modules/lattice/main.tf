# -----------------------------------------------------------------------
# VPC Lattice Target Group — Inventory v1 (Lambda)
# -----------------------------------------------------------------------
resource "aws_vpclattice_target_group" "inventory_v1" {
  name = "inventory-tg-v1"
  type = "LAMBDA"

  tags = {
    Name = "inventory-tg-v1"
  }
}

# -----------------------------------------------------------------------
# VPC Lattice Target Group — Inventory v2 (Lambda)
# -----------------------------------------------------------------------
resource "aws_vpclattice_target_group" "inventory_v2" {
  name = "inventory-tg-v2"
  type = "LAMBDA"

  tags = {
    Name = "inventory-tg-v2"
  }
}

# -----------------------------------------------------------------------
# Register Inventory Lambda v1 as a target
# -----------------------------------------------------------------------
resource "aws_vpclattice_target_group_attachment" "inventory_v1" {
  target_group_identifier = aws_vpclattice_target_group.inventory_v1.id

  target {
    id = var.lambda_v1_arn
  }
}

# -----------------------------------------------------------------------
# Register Inventory Lambda v2 as a target
# -----------------------------------------------------------------------
resource "aws_vpclattice_target_group_attachment" "inventory_v2" {
  target_group_identifier = aws_vpclattice_target_group.inventory_v2.id

  target {
    id = var.lambda_v2_arn
  }
}

# -----------------------------------------------------------------------
# VPC Lattice Service — Inventory (IAM auth)
# -----------------------------------------------------------------------
resource "aws_vpclattice_service" "inventory" {
  name      = "inventory-service"
  auth_type = "AWS_IAM"

  tags = {
    Name = "inventory-service"
  }
}

# -----------------------------------------------------------------------
# VPC Lattice Listener — HTTP on port 80
# -----------------------------------------------------------------------
resource "aws_vpclattice_listener" "inventory_http" {
  name               = "inventory-http"
  service_identifier = aws_vpclattice_service.inventory.id
  protocol           = "HTTP"
  port               = 80

  default_action {
    forward {
      target_groups {
        target_group_identifier = aws_vpclattice_target_group.inventory_v1.id
        weight                  = 100
      }
    }
  }
}

# -----------------------------------------------------------------------
# VPC Lattice Auth Policy — allow only Orders Lambda role from Account A
# -----------------------------------------------------------------------
resource "aws_vpclattice_auth_policy" "inventory" {
  count = var.orders_lambda_role_arn != "" ? 1 : 0

  resource_identifier = aws_vpclattice_service.inventory.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = "*"
        Action    = "vpc-lattice-svcs:Invoke"
        Resource  = "*"
        Condition = {
          StringEquals = {
            "aws:PrincipalArn" = var.orders_lambda_role_arn
          }
        }
      }
    ]
  })
}

# -----------------------------------------------------------------------
# AWS RAM Resource Share — share Inventory Service with Account A
# -----------------------------------------------------------------------
resource "aws_ram_resource_share" "inventory_service_share" {
  name                      = "inventory-service-share"
  allow_external_principals = true

  tags = {
    Name = "inventory-service-share"
  }
}

resource "aws_ram_resource_association" "inventory_service" {
  resource_share_arn = aws_ram_resource_share.inventory_service_share.arn
  resource_arn       = aws_vpclattice_service.inventory.arn
}

resource "aws_ram_principal_association" "account_a" {
  resource_share_arn = aws_ram_resource_share.inventory_service_share.arn
  principal          = var.account_a_id
}

# -----------------------------------------------------------------------
# VPC Lattice Listener Rule — weighted routing 80/20 (v1/v2)
# -----------------------------------------------------------------------
resource "aws_vpclattice_listener_rule" "weighted_routing" {
  name                = "weighted-routing"
  listener_identifier = aws_vpclattice_listener.inventory_http.listener_id
  service_identifier  = aws_vpclattice_service.inventory.id
  priority            = 10

  match {
    http_match {
      path_match {
        match {
          prefix = "/"
        }
        case_sensitive = false
      }
    }
  }

  action {
    forward {
      target_groups {
        target_group_identifier = aws_vpclattice_target_group.inventory_v1.id
        weight                  = var.weight_v1
      }
      target_groups {
        target_group_identifier = aws_vpclattice_target_group.inventory_v2.id
        weight                  = var.weight_v2
      }
    }
  }
}
