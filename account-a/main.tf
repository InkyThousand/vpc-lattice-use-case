terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

module "networking" {
  source = "./modules/networking"

  vpc_cidr             = var.vpc_cidr
  private_subnet_cidrs = var.private_subnet_cidrs
  availability_zones   = var.availability_zones
}

module "lambda" {
  source = "./modules/lambda"

  aws_region            = var.aws_region
  inventory_service_dns = var.inventory_service_dns
  subnet_ids            = module.networking.private_subnet_ids
  security_group_ids    = [module.networking.lambda_security_group_id]
}

module "lattice" {
  source = "./modules/lattice"

  vpc_id = module.networking.vpc_id
}
