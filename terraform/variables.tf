variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-central-1"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.micro"
}

variable "key_name" {
  description = "Name of the EC2 key pair (must already exist in AWS)"
  type        = string
}

variable "data_volume_size_gb" {
  description = "Size of the persistent data EBS in GB"
  type        = number
  default     = 20
}

variable "data_volume_az" {
  description = "AZ for the data EBS — must match the EC2 instance AZ"
  type        = string
  default     = "eu-central-1a"
}

variable "app_dir" {
  description = "Directory on the EC2 instance where the app lives"
  type        = string
  default     = "/home/ubuntu/app"
}

variable "tags" {
  description = "Common tags applied to all resources"
  type        = map(string)
  default = {
    Project   = "eventhub"
    ManagedBy = "terraform"
  }
}
