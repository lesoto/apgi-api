# Workload Identity Federation — GitHub Actions authenticates to GCP by
# exchanging its OIDC token for short-lived GCP credentials. No service-account
# key files are ever generated or stored as GitHub secrets (identifiers.yaml:
# infrastructure.keyless_ci, governing doc §9.6).

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "github-actions-pool"
  display_name              = "GitHub Actions"
  description               = "Federates GitHub Actions OIDC tokens for keyless CI/CD."
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions-provider"
  display_name                       = "GitHub Actions OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  # Only tokens minted for this exact repository AND ref (prefix match, so
  # var.github_deploy_ref = "refs/tags/v" restricts production to tagged
  # releases) may exchange for GCP credentials — a fork, an unrelated repo, or
  # a PR branch cannot impersonate the deployer.
  attribute_condition = "assertion.repository == \"${var.github_repository}\" && assertion.ref.startsWith(\"${var.github_deploy_ref}\")"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "ci_deployer" {
  project      = var.project_id
  account_id   = "ci-deployer"
  display_name = "GitHub Actions CI/CD deployer (${var.environment})"
  description  = "Builds images and deploys Cloud Run revisions. Impersonated via WIF — no keys."
}

# Only the configured ref (var.github_deploy_ref) may impersonate the deployer
# service account, on top of the pool-level repository restriction above.
resource "google_service_account_iam_member" "ci_deployer_wif_binding" {
  service_account_id = google_service_account.ci_deployer.name
  role                = "roles/iam.workloadIdentityUser"
  member = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}
