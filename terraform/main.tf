# --- Container Service ---

resource "aws_lightsail_container_service" "app" {
  name  = var.instance_name
  power = var.container_power
  scale = var.container_scale

  public_domain_names {
    certificate {
      certificate_name = aws_lightsail_certificate.app.name
      domain_names     = ["www.${var.domain_name}"]
    }
  }

  tags = {
    Project = "race-crew-network"
  }
}

# --- SSL Certificate ---

resource "aws_lightsail_certificate" "app" {
  name        = "${var.instance_name}-cert"
  domain_name = "www.${var.domain_name}"
}

# DNS validation record for the SSL certificate
resource "aws_route53_record" "cert_validation" {
  zone_id = var.route53_zone_id
  name    = tolist(aws_lightsail_certificate.app.domain_validation_options)[0].resource_record_name
  type    = tolist(aws_lightsail_certificate.app.domain_validation_options)[0].resource_record_type
  records = [tolist(aws_lightsail_certificate.app.domain_validation_options)[0].resource_record_value]
  ttl     = 60
}

# --- Managed MySQL Database ---

resource "aws_lightsail_database" "app" {
  relational_database_name = "${var.instance_name}-db"
  availability_zone        = var.availability_zone
  master_database_name     = var.db_name
  master_username          = var.db_username
  master_password          = var.db_password
  blueprint_id             = "mysql_8_0"
  bundle_id                = var.db_bundle_id
  publicly_accessible      = true

  tags = {
    Project = "race-crew-network"
  }
}

# --- Object Storage (S3-compatible) ---

resource "aws_lightsail_bucket" "uploads" {
  name      = "${var.instance_name}-uploads"
  bundle_id = "small_1_0"

  tags = {
    Project = "race-crew-network"
  }
}

resource "aws_lightsail_bucket_access_key" "app" {
  bucket_name = aws_lightsail_bucket.uploads.name
}

# --- Container Deployment ---
# Deployments are managed by GitHub Actions (deploy.yml), not Terraform.
# Terraform manages infrastructure only; GH Actions owns the container image
# and environment variables for each deploy.

# --- DNS ---
# www subdomain CNAME pointing to the container service.

resource "aws_route53_record" "app" {
  zone_id = var.route53_zone_id
  name    = "www.${var.domain_name}"
  type    = "CNAME"
  ttl     = 300
  records = [replace(aws_lightsail_container_service.app.url, "/^https?://|/$/", "")]
}

# Naked domain redirect: S3 bucket redirects racecrew.net -> www.racecrew.net
# CloudFront terminates SSL, forwards to S3 website endpoint.

resource "aws_s3_bucket" "redirect" {
  bucket = var.domain_name
}

resource "aws_s3_bucket_website_configuration" "redirect" {
  bucket = aws_s3_bucket.redirect.id

  redirect_all_requests_to {
    host_name = "www.${var.domain_name}"
    protocol  = "https"
  }
}

# --- ACM Certificate for apex domain (must be us-east-1 for CloudFront) ---

resource "aws_acm_certificate" "apex" {
  domain_name       = var.domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "apex_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.apex.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  }

  zone_id = var.route53_zone_id
  name    = each.value.name
  type    = each.value.type
  records = [each.value.record]
  ttl     = 60
}

resource "aws_acm_certificate_validation" "apex" {
  certificate_arn         = aws_acm_certificate.apex.arn
  validation_record_fqdns = [for record in aws_route53_record.apex_cert_validation : record.fqdn]
}

# --- CloudFront distribution for apex redirect ---

resource "aws_cloudfront_distribution" "apex_redirect" {
  enabled         = true
  aliases         = [var.domain_name]
  price_class     = "PriceClass_100"
  is_ipv6_enabled = true
  comment         = "Naked domain redirect for ${var.domain_name}"

  origin {
    domain_name = aws_s3_bucket_website_configuration.redirect.website_endpoint
    origin_id   = "S3RedirectOrigin"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id       = "S3RedirectOrigin"
    viewer_protocol_policy = "allow-all"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 86400
    max_ttl     = 31536000
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.apex.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = {
    Project = "race-crew-network"
  }

  depends_on = [aws_acm_certificate_validation.apex]
}

# Route 53 alias at zone apex points to the CloudFront distribution.

resource "aws_route53_record" "apex" {
  zone_id = var.route53_zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.apex_redirect.domain_name
    zone_id                = aws_cloudfront_distribution.apex_redirect.hosted_zone_id
    evaluate_target_health = false
  }
}
