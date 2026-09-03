# Terraform + provider version pins for APGI's GCP infrastructure (Phase 0C).
#
# Two environments share this module via -var-file (see environments/*.tfvars):
# `production` (apgiframework.com traffic) and `research` (pilot data, §7).
# They are separate GCP projects with separate state — never share a backend.

terraform {
  required_version = ">= 1.7.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.40"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.40"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Remote state must live outside either project it describes. Bootstrap this
  # bucket by hand once (gsutil mb + versioning), then uncomment:
  #
  # backend "gcs" {
  #   bucket = "apgi-terraform-state"
  #   prefix = "gcp/<environment>"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}
