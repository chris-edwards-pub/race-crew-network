output "container_service_url" {
  description = "Public URL of the container service"
  value       = aws_lightsail_container_service.app.url
}

output "database_endpoint" {
  description = "MySQL host address"
  value       = aws_lightsail_database.app.master_endpoint_address
}

output "database_port" {
  description = "MySQL port"
  value       = aws_lightsail_database.app.master_endpoint_port
}

output "bucket_name" {
  description = "Object storage bucket name"
  value       = aws_lightsail_bucket.uploads.name
}

output "bucket_access_key_id" {
  description = "Access key ID for the uploads bucket"
  value       = aws_lightsail_bucket_access_key.app.access_key_id
}

output "bucket_secret_access_key" {
  description = "Secret access key for the uploads bucket"
  value       = aws_lightsail_bucket_access_key.app.secret_access_key
  sensitive   = true
}

output "cloudfront_distribution_domain" {
  description = "CloudFront domain name for apex redirect"
  value       = aws_cloudfront_distribution.apex_redirect.domain_name
}
