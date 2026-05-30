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

  aws_region = var.aws_region
}

module "lattice" {
  source = "./modules/lattice"

  lambda_v1_arn          = module.lambda.lambda_v1_arn
  lambda_v2_arn          = module.lambda.lambda_v2_arn
  weight_v1              = var.inventory_v1_weight
  weight_v2              = var.inventory_v2_weight
  orders_lambda_role_arn = var.orders_lambda_role_arn
  account_a_id           = var.account_a_id
}
