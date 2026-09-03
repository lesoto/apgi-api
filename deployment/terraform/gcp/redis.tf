# Memorystore Redis — cache/session store (db/0) and Celery broker/backend
# (db/1, db/2 selected at the app layer via REDIS_URL path segments, same as
# local development; Memorystore itself is a single logical instance).

resource "google_redis_instance" "apgi" {
  project            = var.project_id
  name               = "apgi-${var.environment}"
  region             = var.region
  tier               = var.redis_tier
  memory_size_gb     = var.redis_memory_size_gb
  redis_version      = "REDIS_7_2"
  authorized_network = google_compute_network.apgi.id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"
  auth_enabled       = true

  depends_on = [google_service_networking_connection.private_vpc_connection]

  labels = var.labels
}
