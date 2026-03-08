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

  backup_retention_enabled = true
  preferred_backup_window  = "06:00-06:30" # 2:00–2:30 AM ET
  apply_immediately        = true
  final_snapshot_name      = "${var.instance_name}-db-final-snapshot"

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

resource "null_resource" "bucket_versioning" {
  triggers = {
    bucket_name = aws_lightsail_bucket.uploads.name
  }

  provisioner "local-exec" {
    command = "aws lightsail update-bucket --bucket-name ${aws_lightsail_bucket.uploads.name} --versioning Enabled --region ${var.aws_region}"
  }

  depends_on = [aws_lightsail_bucket.uploads]
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

# --- SES Email ---

resource "aws_ses_domain_identity" "app" {
  domain = var.domain_name
}

resource "aws_ses_domain_dkim" "app" {
  domain = aws_ses_domain_identity.app.domain
}

resource "aws_ses_domain_mail_from" "app" {
  domain           = aws_ses_domain_identity.app.domain
  mail_from_domain = "mail.${var.domain_name}"
}

# DKIM CNAME records (3 tokens)
resource "aws_route53_record" "ses_dkim" {
  count   = 3
  zone_id = var.route53_zone_id
  name    = "${aws_ses_domain_dkim.app.dkim_tokens[count.index]}._domainkey.${var.domain_name}"
  type    = "CNAME"
  ttl     = 300
  records = ["${aws_ses_domain_dkim.app.dkim_tokens[count.index]}.dkim.amazonses.com"]
}

# SPF TXT record on root domain (includes both Outlook and SES)
resource "aws_route53_record" "spf" {
  zone_id = var.route53_zone_id
  name    = var.domain_name
  type    = "TXT"
  ttl     = 300
  records = ["v=spf1 include:spf.protection.outlook.com include:amazonses.com -all"]
}

# DMARC TXT record
resource "aws_route53_record" "dmarc" {
  zone_id = var.route53_zone_id
  name    = "_dmarc.${var.domain_name}"
  type    = "TXT"
  ttl     = 300
  records = ["v=DMARC1; p=none;"]
}

# MAIL FROM MX record
resource "aws_route53_record" "ses_mail_from_mx" {
  zone_id = var.route53_zone_id
  name    = "mail.${var.domain_name}"
  type    = "MX"
  ttl     = 300
  records = ["10 feedback-smtp.${var.aws_region}.amazonses.com"]
}

# MAIL FROM SPF record
resource "aws_route53_record" "ses_mail_from_spf" {
  zone_id = var.route53_zone_id
  name    = "mail.${var.domain_name}"
  type    = "TXT"
  ttl     = 300
  records = ["v=spf1 include:amazonses.com -all"]
}

# --- SES IAM User ---
# Dedicated IAM user for SES sending (Lightsail bucket keys lack SES permissions).

resource "aws_iam_user" "ses_sender" {
  name = "${var.instance_name}-ses-sender"

  tags = {
    Project = "race-crew-network"
  }
}

resource "aws_iam_user_policy" "ses_send" {
  name = "ses-send-raw-email"
  user = aws_iam_user.ses_sender.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ses:SendRawEmail", "ses:SendEmail"]
        Resource = "arn:aws:ses:${var.aws_region}:${data.aws_caller_identity.current.account_id}:identity/*"
      }
    ]
  })
}

resource "aws_iam_access_key" "ses_sender" {
  user = aws_iam_user.ses_sender.name
}

data "aws_caller_identity" "current" {}

# --- SES Bounce & Complaint Notifications ---

# SNS topic for SES bounce/complaint notifications
resource "aws_sns_topic" "ses_notifications" {
  name = "ses-bounce-complaint"

  tags = {
    Project = "race-crew-network"
  }
}

# Subscribe the app webhook to the SNS topic
resource "aws_sns_topic_subscription" "ses_webhook" {
  topic_arn = aws_sns_topic.ses_notifications.arn
  protocol  = "https"
  endpoint  = "https://www.${var.domain_name}/webhooks/ses"
}

# SES notification configuration — bounces
resource "aws_ses_identity_notification_topic" "bounce" {
  topic_arn                = aws_sns_topic.ses_notifications.arn
  notification_type        = "Bounce"
  identity                 = aws_ses_domain_identity.app.domain
  include_original_headers = false
}

# SES notification configuration — complaints
resource "aws_ses_identity_notification_topic" "complaint" {
  topic_arn                = aws_sns_topic.ses_notifications.arn
  notification_type        = "Complaint"
  identity                 = aws_ses_domain_identity.app.domain
  include_original_headers = false
}
