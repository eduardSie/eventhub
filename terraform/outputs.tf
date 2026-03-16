output "public_ip" {
  description = "Elastic IP — update EC2_HOST secret in GitHub to this value"
  value       = aws_eip.eventhub.public_ip
}

output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.eventhub.id
}

output "data_volume_id" {
  description = "Persistent data EBS volume ID — keep this safe"
  value       = aws_ebs_volume.data.id
}

output "ssh_command" {
  description = "Quick SSH command"
  value       = "ssh ubuntu@${aws_eip.eventhub.public_ip}"
}
