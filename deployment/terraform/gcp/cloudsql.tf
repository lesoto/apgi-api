# Cloud SQL for PostgreSQL — the participants/consent/studies/batteries/
# sessions/model_versions schema lives here (Phase 2 migrations).
# Backups + PITR implement the "Backup configuration and restore drill" item;
# the drill procedure itself is documented in docs/DEPLOYMENT.md.

resource "google_sql_database_instance" "apgi" {
  project             = var.project_id
  name                = "apgi-${var.environment}"
  database_version    = "POSTGRES_16"
  region              = var.region
  deletion_protection = var.environment == "production"

  depends_on = [google_service_networking_connection.private_vpc_connection]

  settings {
    tier              = var.db_tier
    availability_type = var.db_high_availability ? "REGIONAL" : "ZONAL"
    disk_autoresize   = true
    disk_type         = "PD_SSD"

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.apgi.id
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "07:00"
      transaction_log_retention_days = 7
      backup_retention_settings {
        retained_backups = var.backup_retention_days
        retention_unit   = "COUNT"
      }
    }

    maintenance_window {
      day          = 7 # Sunday
      hour         = 6
      update_track = "stable"
    }

    database_flags {
      name  = "row_security"
      value = "on" # Postgres RLS policies (Phase 2 migration) are enforced.
    }

    insights_config {
      query_insights_enabled = true
    }

    user_labels = var.labels
  }
}

resource "google_sql_database" "apgi_core" {
  project  = var.project_id
  name     = "apgi_${var.environment}"
  instance = google_sql_database_instance.apgi.name
}

resource "random_password" "db_app_user" {
  length  = 32
  special = false # Cloud SQL Postgres passwords: keep it Terraform-state-safe and DSN-safe.
}

resource "google_sql_user" "apgi_app" {
  project  = var.project_id
  name     = "apgi_app"
  instance = google_sql_database_instance.apgi.name
  password = random_password.db_app_user.result
}

# Wires the generated DSN into the Secret Manager container from secrets.tf.
# NOTE: this value (including the plaintext password) is stored in Terraform
# state like any other resource attribute. Restrict the remote state backend
# (see versions.tf's commented `backend "gcs"`) to the same principals who
# may read the secret directly, and treat state access as equivalent to
# secretAccessor.
resource "google_secret_manager_secret_version" "database_url" {
  secret = google_secret_manager_secret.app["DATABASE_URL"].id
  secret_data = format(
    "postgresql://%s:%s@/%s?host=/cloudsql/%s",
    google_sql_user.apgi_app.name,
    random_password.db_app_user.result,
    google_sql_database.apgi_core.name,
    google_sql_database_instance.apgi.connection_name,
  )
}
