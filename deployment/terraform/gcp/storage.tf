# Restricted Cloud Storage for raw trial events, and a BigQuery dataset for
# the de-identified export path (Phase 2 & Phase 3-4).
#
# Access to both is scoped to the runtime SA only — no allUsers, no
# allAuthenticatedUsers, uniform bucket-level access (no legacy per-object
# ACLs to audit), and versioning so a bad write doesn't destroy the raw
# record irreversibly.

resource "google_storage_bucket" "raw_trial_events" {
  project                     = var.project_id
  name                        = "apgi-${var.environment}-raw-trial-events"
  location                    = upper(var.region)
  uniform_bucket_level_access = true
  force_destroy               = false

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 2555 # ~7 years — align with the retention period in the consent text before shortening.
    }
    action {
      type = "Delete"
    }
  }

  soft_delete_policy {
    retention_duration_seconds = 604800 # 7 days, guards the cascading-deletion job against a bad run.
  }

  # Google-managed encryption at rest by default. Swap in a CMEK key by adding
  # an `encryption { default_kms_key_name = ... }` block once one is
  # provisioned — not required for the pilot.

  labels = var.labels
}

# The runtime SA may only append objects (create new trial-event files) and
# read them back for scoring — never list/delete the bucket wholesale. Bulk
# delete is reserved for the cascading-deletion Celery task, which uses this
# same SA's objectAdmin grant but is itself gated by ownership + consent
# checks at the application layer (app/services/data_lifecycle.py).
resource "google_storage_bucket_iam_member" "runtime_object_admin" {
  bucket = google_storage_bucket.raw_trial_events.name
  role   = "roles/storage.objectAdmin"
  member = google_service_account.runtime.member
}

resource "google_bigquery_dataset" "deidentified_export" {
  project                    = var.project_id
  dataset_id                 = "apgi_${var.environment}_deidentified"
  location                   = upper(var.region)
  delete_contents_on_destroy = false

  labels = var.labels
}

resource "google_bigquery_dataset_iam_member" "runtime_writer" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.deidentified_export.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = google_service_account.runtime.member
}
