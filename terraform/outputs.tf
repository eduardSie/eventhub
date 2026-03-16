output "public_ip" {
  description = "Elastic IP — update EC2_HOST secret in GitHub to this value"
  value       = data.aws_eip.istatp_eip
}

output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.istatp_instance.id
}

output "ssh_command" {
  description = "Quick SSH command"
  value       = "ssh ubuntu@${data.aws_eip.istatp_eip.public_ip}"
}
