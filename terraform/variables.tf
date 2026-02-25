variable "aws_region" {
  description = "AWS region for Lightsail resources"
  type        = string
  default     = "us-east-1"
}

variable "instance_name" {
  description = "Base name for Lightsail resources"
  type        = string
  default     = "race-crew-network"
}

variable "availability_zone" {
  description = "Availability zone for the database"
  type        = string
  default     = "us-east-1a"
}

variable "domain_name" {
  description = "Domain name for the app"
  type        = string
}

variable "route53_zone_id" {
  description = "Route 53 hosted zone ID for the domain"
  type        = string
}

variable "db_password" {
  description = "Master password for the managed MySQL database"
  type        = string
  sensitive   = true
}

variable "db_username" {
  description = "Master username for the managed MySQL database"
  type        = string
  default     = "racecrew"
}

variable "db_name" {
  description = "Database name for the managed MySQL database"
  type        = string
  default     = "racecrew"
}

variable "container_power" {
  description = "Lightsail container service power (nano, micro, small, etc.)"
  type        = string
  default     = "micro"
}

variable "container_scale" {
  description = "Number of container instances to run"
  type        = number
  default     = 1
}

variable "db_bundle_id" {
  description = "Lightsail database bundle (size/price)"
  type        = string
  default     = "micro_2_0"
}
