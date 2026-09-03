output "cloud_run_url" {
  value = google_cloud_run_v2_service.apgi_core.uri
}

output "cloud_run_service_name" {
  value = google_cloud_run_v2_service.apgi_core.name
}

output "artifact_registry_repository" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.apgi_core.repository_id}"
}

output "wif_provider_resource_name" {
  description = "Pass to google-github-actions/auth's workload_identity_provider input."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "ci_deployer_service_account_email" {
  description = "Pass to google-github-actions/auth's service_account input."
  value       = google_service_account.ci_deployer.email
}

output "cloud_sql_connection_name" {
  value = google_sql_database_instance.apgi.connection_name
}

output "redis_host" {
  value = google_redis_instance.apgi.host
}

output "raw_trial_events_bucket" {
  value = google_storage_bucket.raw_trial_events.name
}

output "bigquery_deidentified_dataset" {
  value = google_bigquery_dataset.deidentified_export.dataset_id
}
