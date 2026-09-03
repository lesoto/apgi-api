# Secret Manager references. Terraform manages the secret *containers*, their
# rotation-reminder schedule, and IAM access — never the secret *values*.
# Values are seeded once by an operator (`gcloud secrets versions add ...`,
# never committed, never in a .tfvars file) and rotated per
# docs/DEPLOYMENT.md's "Secrets Rotation SOP".

locals {
  managed_secrets = [
    "JWT_SECRET_KEY",
    "CURSOR_SIGNING_KEY",
    "WEBHOOK_SECRET_KEY",
    "DATABASE_URL",
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "PII_ENCRYPTION_KEY",
  ]
}

resource "google_pubsub_topic" "secret_rotation_reminder" {
  project = var.project_id
  name    = "apgi-secret-rotation-reminder"
}

resource "google_secret_manager_secret" "app" {
  for_each  = toset(local.managed_secrets)
  project   = var.project_id
  secret_id = each.value

  replication {
    auto {}
  }

  rotation {
    rotation_period    = var.secret_rotation_period_seconds
    next_rotation_time = timeadd(timestamp(), var.secret_rotation_period_seconds)
  }

  topics {
    name = google_pubsub_topic.secret_rotation_reminder.id
  }

  labels = var.labels

  lifecycle {
    # next_rotation_time is a moving target on every apply; ignore drift so
    # `apply` doesn't perpetually want to reset it.
    ignore_changes = [rotation[0].next_rotation_time]
  }
}

# Runtime SA may read secret values; nothing else (including the CI deployer)
# gets secretAccessor — deploys pass secret *references*, never values.
resource "google_secret_manager_secret_iam_member" "runtime_accessor" {
  for_each  = google_secret_manager_secret.app
  project   = var.project_id
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = google_service_account.runtime.member
}
