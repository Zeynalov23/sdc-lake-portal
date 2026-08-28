# ---------------------------------------------------------------
# DNS and TLS
#
# Both live here rather than in infra-cluster because their lifetime has
# nothing to do with the cluster's. A certificate for a domain is valid
# whether or not any cluster exists.
#
# For the hosted zone that is not just tidiness: destroying and recreating a
# zone allocates four *new* name servers, which would mean re-editing the
# delegation at the registrar after every `make down`.
# ---------------------------------------------------------------

# The apex domain stays at the registrar. Only this subdomain is delegated to
# Route 53, so anything else the domain is used for is unaffected.
resource "aws_route53_zone" "platform" {
  name = var.dns_zone_name

  tags = {
    Name = var.dns_zone_name
  }
}

# Wildcard, so argocd.<zone>, portal.<zone> and anything added later are
# covered without reissuing. ACM certificates are free and renew themselves
# as long as the validation record stays published.
#
# The certificate must be in the same region as the load balancer that uses
# it. (CloudFront is the exception - it only reads certificates from
# us-east-1 - but the Gateway's NLB is regional.)
resource "aws_acm_certificate" "platform" {
  domain_name       = "*.${var.dns_zone_name}"
  validation_method = "DNS"

  # A wildcard does not cover the apex, so it is listed separately.
  subject_alternative_names = [var.dns_zone_name]

  lifecycle {
    # ACM will not let a certificate in use be destroyed, so create the
    # replacement first when anything forces a new one.
    create_before_destroy = true
  }

  tags = {
    Name = var.dns_zone_name
  }
}

# One validation record per name on the certificate. for_each rather than a
# count because the set is keyed by domain name: with a wildcard and an apex
# that resolve to the same record, a list would produce a duplicate and fail.
resource "aws_route53_record" "acm_validation" {
  for_each = {
    for option in aws_acm_certificate.platform.domain_validation_options :
    option.domain_name => {
      name   = option.resource_record_name
      record = option.resource_record_value
      type   = option.resource_record_type
    }
  }

  zone_id         = aws_route53_zone.platform.zone_id
  name            = each.value.name
  type            = each.value.type
  records         = [each.value.record]
  ttl             = 60
  allow_overwrite = true
}

# Blocks until ACM has seen the records and issued the certificate. On a first
# apply this waits until the registrar delegation is in place - that is
# expected, not a failure. Take the name servers from the output, add them at
# the registrar, and this completes on its own.
resource "aws_acm_certificate_validation" "platform" {
  certificate_arn         = aws_acm_certificate.platform.arn
  validation_record_fqdns = [for record in aws_route53_record.acm_validation : record.fqdn]

  timeouts {
    create = "10m"
  }
}
