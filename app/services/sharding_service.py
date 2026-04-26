"""
Database Sharding Service

Service for managing database sharding based on user_id for horizontal scalability.
"""

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.config import settings


@dataclass
class ShardConfig:
    """Configuration for a database shard."""

    shard_id: str
    database_url: str
    weight: int = 1  # For weighted distribution
    is_read_replica: bool = False


@dataclass
class ShardInfo:
    """Information about a shard."""

    shard_id: str
    user_range_start: str
    user_range_end: str
    database_url: str
    is_active: bool = True


class DatabaseShardingService:
    """Service for managing database sharding operations."""

    def __init__(self) -> None:
        # Default to single shard configuration
        self.shards: Dict[str, ShardConfig] = {}
        self.num_shards = getattr(settings, "database_shards_count", 1)

        # Initialize shards based on configuration
        self._initialize_shards()

    def _initialize_shards(self) -> None:
        """Initialize shard configurations."""
        # If only one shard, use the main database URL
        if self.num_shards == 1:
            self.shards["shard_0"] = ShardConfig(
                shard_id="shard_0", database_url=settings.database_url, weight=1
            )
            return

        # For multiple shards, expect environment variables like:
        # DATABASE_SHARD_0_URL, DATABASE_SHARD_1_URL, etc.
        for i in range(self.num_shards):
            shard_url_env = f"DATABASE_SHARD_{i}_URL"
            shard_url = getattr(settings, shard_url_env.lower().replace("_", ""), None)

            if shard_url:
                self.shards[f"shard_{i}"] = ShardConfig(
                    shard_id=f"shard_{i}", database_url=shard_url, weight=1
                )
            else:
                # Fallback to main database URL for development
                self.shards[f"shard_{i}"] = ShardConfig(
                    shard_id=f"shard_{i}", database_url=settings.database_url, weight=1
                )

    def get_shard_for_user(self, user_id: str) -> str:
        """
        Get the shard ID for a given user ID.

        Uses consistent hashing to ensure the same user always goes to the same shard.

        Args:
            user_id: The user identifier

        Returns:
            Shard ID string
        """
        if self.num_shards == 1:
            return "shard_0"

        # Use SHA-256 hash of user_id for consistent sharding
        hash_value = int(hashlib.sha256(user_id.encode()).hexdigest(), 16)
        shard_index = hash_value % self.num_shards

        return f"shard_{shard_index}"

    def get_shard_config(self, shard_id: str) -> Optional[ShardConfig]:
        """
        Get configuration for a specific shard.

        Args:
            shard_id: The shard identifier

        Returns:
            ShardConfig if found, None otherwise
        """
        return self.shards.get(shard_id)

    def get_all_shards(self) -> List[ShardInfo]:
        """
        Get information about all configured shards.

        Returns:
            List of ShardInfo objects
        """
        shards_info = []

        for shard_id, config in self.shards.items():
            # Calculate approximate user ID ranges for each shard
            shard_index = int(shard_id.split("_")[1])
            range_size = 2**256 // self.num_shards  # SHA-256 space divided by num_shards

            range_start = hex(shard_index * range_size)[2:].zfill(64)
            range_end = hex((shard_index + 1) * range_size - 1)[2:].zfill(64)

            shards_info.append(
                ShardInfo(
                    shard_id=shard_id,
                    user_range_start=range_start,
                    user_range_end=range_end,
                    database_url=config.database_url,
                    is_active=True,
                )
            )

        return shards_info

    def migrate_user_data(self, user_id: str, from_shard: str, to_shard: str) -> Dict[str, Any]:
        """
        Handle user data migration between shards (for rebalancing).

        This is a placeholder for future implementation of shard rebalancing.

        Args:
            user_id: User to migrate
            from_shard: Source shard
            to_shard: Target shard

        Returns:
            Migration status information
        """
        # In a real implementation, this would:
        # 1. Lock user data
        # 2. Copy data from source to target shard
        # 3. Update shard mappings
        # 4. Remove data from source shard
        # 5. Unlock user data

        return {
            "user_id": user_id,
            "from_shard": from_shard,
            "to_shard": to_shard,
            "status": "not_implemented",
            "message": "Shard migration not yet implemented",
        }

    def get_shard_stats(self) -> Dict[str, Any]:
        """
        Get statistics about shard distribution and usage.

        Returns:
            Dictionary with shard statistics
        """
        total_shards = len(self.shards)
        active_shards = len([s for s in self.shards.values() if not s.is_read_replica])

        return {
            "total_shards": total_shards,
            "active_shards": active_shards,
            "read_replicas": total_shards - active_shards,
            "sharding_strategy": "consistent_hashing",
            "shard_key": "user_id",
            "shards": [
                {
                    "shard_id": shard_id,
                    "weight": config.weight,
                    "is_read_replica": config.is_read_replica,
                }
                for shard_id, config in self.shards.items()
            ],
        }

    def validate_sharding_setup(self) -> Dict[str, Any]:
        """
        Validate that the sharding setup is properly configured.

        Returns:
            Validation results
        """
        issues = []
        warnings = []

        # Check if we have multiple shards but only one database URL
        if self.num_shards > 1 and len(set(s.database_url for s in self.shards.values())) == 1:
            warnings.append("Multiple shards configured but all using the same database URL")

        # Check for missing shard configurations
        for i in range(self.num_shards):
            shard_id = f"shard_{i}"
            if shard_id not in self.shards:
                issues.append(f"Shard {shard_id} is not configured")

        # Check for read replica configuration
        read_replicas = [s for s in self.shards.values() if s.is_read_replica]
        if not read_replicas:
            warnings.append("No read replicas configured for high availability")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "shard_count": self.num_shards,
            "configured_shards": len(self.shards),
        }


# Global sharding service instance
sharding_service = DatabaseShardingService()
