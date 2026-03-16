terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  backend "s3" {
    bucket = "terraform-istatp"
    key    = "prod/terraform.tfstate"
    region = "eu-central-1"
  }

}

provider "aws" {
  region = var.aws_region
}
