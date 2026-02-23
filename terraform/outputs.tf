output "instance_name" {
  description = "Lightsail instance name"
  value       = aws_lightsail_instance.app.name
}

output "static_ip" {
  description = "Static IP address — point racecrew.net A record here"
  value       = aws_lightsail_static_ip.app.ip_address
}

output "instance_username" {
  description = "Default SSH username for Amazon Linux 2023"
  value       = "ec2-user"
}
