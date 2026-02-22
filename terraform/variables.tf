variable "aws_region" {
  description = "AWS region for Lightsail instance"
  type        = string
  default     = "us-east-1"
}

variable "instance_name" {
  description = "Name for the Lightsail instance"
  type        = string
  default     = "thistle-regattas"
}

variable "availability_zone" {
  description = "Availability zone for the instance"
  type        = string
  default     = "us-east-1a"
}

variable "blueprint_id" {
  description = "Lightsail blueprint (OS image)"
  type        = string
  default     = "amazon_linux_2023"
}

variable "bundle_id" {
  description = "Lightsail instance bundle (size/price)"
  type        = string
  default     = "small_3_0"
}

variable "ssh_public_key" {
  description = "SSH public key for instance access"
  type        = string
  sensitive   = true
}

variable "repo_url" {
  description = "Git repository URL to clone on the instance"
  type        = string
}

variable "domain_name" {
  description = "Domain name for the app"
  type        = string
}

variable "route53_zone_id" {
  description = "Route 53 hosted zone ID for the domain"
  type        = string
}
