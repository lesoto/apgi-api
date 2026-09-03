# SUPERSEDED — kept for historical reference only.
#
# APGI's infrastructure provider is Google Cloud (identifiers.yaml:
# infrastructure.provider). The live Terraform is in ../gcp/. This AWS
# module predates that decision and is not applied anywhere; do not add
# resources here.
#
# Terraform configuration for APGI API infrastructure
# This creates the basic AWS infrastructure for the APGI API

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Variables
variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_cidrs" {
  description = "Subnet CIDR blocks"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

# Provider configuration
provider "aws" {
  region = var.region
}

# VPC
resource "aws_vpc" "apgi_vpc" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "apgi-${var.environment}-vpc"
    Environment = var.environment
  }
}

# Subnets
resource "aws_subnet" "apgi_subnets" {
  count             = length(var.subnet_cidrs)
  vpc_id            = aws_vpc.apgi_vpc.id
  cidr_block        = var.subnet_cidrs[count.index]
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name        = "apgi-${var.environment}-subnet-${count.index + 1}"
    Environment = var.environment
  }
}

# Internet Gateway
resource "aws_internet_gateway" "apgi_igw" {
  vpc_id = aws_vpc.apgi_vpc.id

  tags = {
    Name        = "apgi-${var.environment}-igw"
    Environment = var.environment
  }
}

# Route Table
resource "aws_route_table" "apgi_rt" {
  vpc_id = aws_vpc.apgi_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.apgi_igw.id
  }

  tags = {
    Name        = "apgi-${var.environment}-rt"
    Environment = var.environment
  }
}

# Route Table Association
resource "aws_route_table_association" "apgi_rta" {
  count          = length(aws_subnet.apgi_subnets)
  subnet_id      = aws_subnet.apgi_subnets[count.index].id
  route_table_id = aws_route_table.apgi_rt.id
}

# Security Group for API
resource "aws_security_group" "apgi_api_sg" {
  name        = "apgi-${var.environment}-api-sg"
  description = "Security group for APGI API"
  vpc_id      = aws_vpc.apgi_vpc.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "apgi-${var.environment}-api-sg"
    Environment = var.environment
  }
}

# RDS PostgreSQL Database
resource "aws_db_instance" "apgi_db" {
  allocated_storage      = 20
  engine                 = "postgres"
  engine_version         = "15.4"
  instance_class         = "db.t3.micro"
  db_name                = "apgi_${var.environment}"
  username               = var.db_username
  password               = var.db_password
  parameter_group_name   = "default.postgres15"
  skip_final_snapshot    = true
  vpc_security_group_ids = [aws_security_group.apgi_db_sg.id]
  db_subnet_group_name   = aws_db_subnet_group.apgi_db_subnet.name

  tags = {
    Name        = "apgi-${var.environment}-db"
    Environment = var.environment
  }
}

# Database Security Group
resource "aws_security_group" "apgi_db_sg" {
  name        = "apgi-${var.environment}-db-sg"
  description = "Security group for APGI database"
  vpc_id      = aws_vpc.apgi_vpc.id

  ingress {
    description     = "PostgreSQL"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.apgi_api_sg.id]
  }

  tags = {
    Name        = "apgi-${var.environment}-db-sg"
    Environment = var.environment
  }
}

# Database Subnet Group
resource "aws_db_subnet_group" "apgi_db_subnet" {
  name       = "apgi-${var.environment}-db-subnet"
  subnet_ids = aws_subnet.apgi_subnets[*].id

  tags = {
    Name        = "apgi-${var.environment}-db-subnet"
    Environment = var.environment
  }
}

# ElastiCache Redis
resource "aws_elasticache_cluster" "apgi_redis" {
  cluster_id           = "apgi-${var.environment}-redis"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.apgi_redis_subnet.name
  security_group_ids   = [aws_security_group.apgi_redis_sg.id]

  tags = {
    Name        = "apgi-${var.environment}-redis"
    Environment = var.environment
  }
}

# Redis Security Group
resource "aws_security_group" "apgi_redis_sg" {
  name        = "apgi-${var.environment}-redis-sg"
  description = "Security group for APGI Redis"
  vpc_id      = aws_vpc.apgi_vpc.id

  ingress {
    description     = "Redis"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.apgi_api_sg.id]
  }

  tags = {
    Name        = "apgi-${var.environment}-redis-sg"
    Environment = var.environment
  }
}

# Redis Subnet Group
resource "aws_elasticache_subnet_group" "apgi_redis_subnet" {
  name       = "apgi-${var.environment}-redis-subnet"
  subnet_ids = aws_subnet.apgi_subnets[*].id

  tags = {
    Name        = "apgi-${var.environment}-redis-subnet"
    Environment = var.environment
  }
}

# Data source for availability zones
data "aws_availability_zones" "available" {
  state = "available"
}

# Variables for sensitive data (should be provided via terraform.tfvars or environment)
variable "db_username" {
  description = "Database username"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

# Outputs
output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.apgi_vpc.id
}

output "database_endpoint" {
  description = "Database endpoint"
  value       = aws_db_instance.apgi_db.endpoint
}

output "redis_endpoint" {
  description = "Redis endpoint"
  value       = aws_elasticache_cluster.apgi_redis.cache_nodes[0].address
}

output "api_security_group_id" {
  description = "API security group ID"
  value       = aws_security_group.apgi_api_sg.id
}
