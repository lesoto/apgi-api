# Private networking for Memorystore (Redis) and Cloud SQL private IP.
# Cloud Run reaches both through a Serverless VPC Access connector; Cloud SQL
# is additionally reachable via the Cloud SQL Auth Proxy socket Cloud Run
# mounts natively, so the connector is really only load-bearing for Redis.

resource "google_compute_network" "apgi" {
  project                 = var.project_id
  name                    = "apgi-${var.environment}"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.required]
}

resource "google_compute_subnetwork" "apgi" {
  project       = var.project_id
  name          = "apgi-${var.environment}-subnet"
  region        = var.region
  network       = google_compute_network.apgi.id
  ip_cidr_range = "10.10.0.0/24"
}

resource "google_vpc_access_connector" "apgi" {
  project       = var.project_id
  name          = "apgi-${substr(var.environment, 0, 10)}-conn"
  region        = var.region
  network       = google_compute_network.apgi.name
  ip_cidr_range = "10.10.1.0/28"
  min_instances = 2
  max_instances = 3
}

resource "google_compute_global_address" "private_service_range" {
  project       = var.project_id
  name          = "apgi-${var.environment}-private-svc"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 20
  network       = google_compute_network.apgi.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.apgi.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_service_range.name]
}
