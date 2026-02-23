# SSH key pair for GitHub Actions to connect
resource "aws_lightsail_key_pair" "deploy" {
  name       = "${var.instance_name}-deploy-key"
  public_key = var.ssh_public_key
}

# The Lightsail instance
resource "aws_lightsail_instance" "app" {
  name              = var.instance_name
  availability_zone = var.availability_zone
  blueprint_id      = var.blueprint_id
  bundle_id         = var.bundle_id
  key_pair_name     = aws_lightsail_key_pair.deploy.name
  user_data = templatefile("${path.module}/user-data.sh", {
    repo_url = var.repo_url
  })

  tags = {
    Project = "race-crew-network"
  }
}

# Static IP so the address survives instance stop/start
resource "aws_lightsail_static_ip" "app" {
  name = "${var.instance_name}-ip"
}

# Attach static IP to instance
resource "aws_lightsail_static_ip_attachment" "app" {
  static_ip_name = aws_lightsail_static_ip.app.name
  instance_name  = aws_lightsail_instance.app.name

  lifecycle {
    replace_triggered_by = [aws_lightsail_instance.app.id]
  }
}

# Firewall: allow SSH (22), HTTP (80), HTTPS (443)
resource "aws_lightsail_instance_public_ports" "app" {
  instance_name = aws_lightsail_instance.app.name

  port_info {
    protocol  = "tcp"
    from_port = 22
    to_port   = 22
  }

  port_info {
    protocol  = "tcp"
    from_port = 80
    to_port   = 80
  }

  port_info {
    protocol  = "tcp"
    from_port = 443
    to_port   = 443
  }
}

# DNS: point domain to static IP
resource "aws_route53_record" "app" {
  zone_id = var.route53_zone_id
  name    = var.domain_name
  type    = "A"
  ttl     = 300
  records = [aws_lightsail_static_ip.app.ip_address]
}
