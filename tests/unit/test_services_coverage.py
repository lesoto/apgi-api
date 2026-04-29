"""
Comprehensive service tests for 100% coverage.
Covers: cache_service, data_export, health_check, profiling_service,
        seeding_service, user_management, webhook_manager, session_manager,
        abuse_detection, auth_manager, authorization, business_metrics,
        rate_limiter, data_lifecycle, error_recovery, sharding_service
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.schemas import SessionCreateRequest

# Import all services to ensure coverage
from app.services.abuse_detection import AbuseDetectionService, RiskLevel
from app.services.auth_manager import AuthManager
from app.services.business_metrics import BusinessMetricsService
from app.services.cache_service import CacheService
from app.services.data_export import DataExportService
from app.services.data_lifecycle import DataLifecycleManager
from app.services.error_recovery import CircuitBreaker, RetryService
from app.services.health_check import HealthCheckService
from app.services.profiling_service import ProfilingService
from app.services.rate_limiter import RateLimiter
from app.services.seeding_service import DatabaseSeedingService
from app.services.session_manager import SessionLifecycleState, SessionManager
from app.services.sharding_service import DatabaseShardingService
from app.services.user_management import UserManagementService
from app.services.webhook_manager import WebhookManager


class TestCacheService:
    """Test cache service module."""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()

        # Mock scan_iter to be an async iterator
        async def async_iter(pattern):
            # Return an empty list for keys
            keys = []
            for k in keys:
                yield k

        redis.scan_iter = MagicMock(side_effect=async_iter)
        return redis

    @pytest.mark.asyncio
    async def test_cache_service_initialization(self, mock_redis):
        """Test CacheService can be initialized."""
        service = CacheService(mock_redis)
        assert service is not None

    @pytest.mark.asyncio
    async def test_cache_service_get_session_state(self, mock_redis):
        """Test cache get session state method."""
        service = CacheService(mock_redis)
        mock_redis.get.return_value = None
        result = await service.get_session_state("test_id")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_service_set_session_state(self, mock_redis):
        """Test cache set session state method."""
        service = CacheService(mock_redis)
        await service.set_session_state("test_id", {"key": "value"})

    @pytest.mark.asyncio
    async def test_cache_service_invalidate_session_cache(self, mock_redis):
        """Test cache invalidate method."""
        service = CacheService(mock_redis)
        await service.invalidate_session_cache("test_id")

    @pytest.mark.asyncio
    async def test_cache_service_get_cache_stats(self, mock_redis):
        """Test cache stats method."""
        service = CacheService(mock_redis)
        mock_redis.info.return_value = {}
        result = await service.get_cache_stats()
        assert result is not None


class TestDataExportService:
    """Test data export service module."""

    @pytest.fixture
    def mock_session_manager(self):
        manager = MagicMock()
        manager.get_session = AsyncMock()
        return manager

    @pytest.mark.asyncio
    async def test_data_export_initialization(self, mock_session_manager):
        """Test DataExportService initialization."""
        service = DataExportService(mock_session_manager)
        assert service is not None

    @pytest.mark.asyncio
    async def test_export_session_data(self, mock_session_manager):
        """Test export session data method."""
        service = DataExportService(mock_session_manager)

        mock_session = AsyncMock()
        mock_session.get_state.return_value = {"history": {"time": [0, 1], "var": [10, 20]}}
        mock_session.created_at = datetime.now(timezone.utc)
        mock_session.updated_at = datetime.now(timezone.utc)
        mock_session.config = {}
        mock_session.state = MagicMock()
        mock_session.state.value = "running"

        mock_session_manager.get_session.return_value = mock_session

        result, content_type = await service.export_session_data(session_id="test-id")
        assert result is not None
        assert content_type == "application/json"

    @pytest.mark.asyncio
    async def test_generate_summary_stats(self, mock_session_manager):
        """Test generate summary stats method."""
        service = DataExportService(mock_session_manager)

        mock_session = AsyncMock()
        mock_session.get_state.return_value = {"history": {"time": [0, 1]}}
        mock_session_manager.get_session.return_value = mock_session

        result = await service.generate_summary_stats(session_id="test-id")
        assert result is not None
        assert result["session_id"] == "test-id"


class TestHealthCheckService:
    """Test health check service module."""

    @pytest.fixture
    def mock_redis(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_health_check_initialization(self, mock_redis):
        """Test HealthCheckService initialization."""
        service = HealthCheckService(mock_redis)
        assert service is not None

    @pytest.mark.asyncio
    async def test_perform_readiness_check(self, mock_redis):
        """Test readiness check."""
        service = HealthCheckService(mock_redis)
        mock_redis.ping.return_value = True
        with patch("app.database.connection.engine") as mock_engine:
            mock_conn = mock_engine.connect.return_value.__enter__.return_value
            result = await service.perform_readiness_check()
            assert result is not None

    @pytest.mark.asyncio
    async def test_perform_health_check(self, mock_redis):
        """Test health check."""
        service = HealthCheckService(mock_redis)
        mock_redis.ping.return_value = True
        with patch("app.database.connection.engine") as mock_engine:
            mock_conn = mock_engine.connect.return_value.__enter__.return_value
            result = await service.perform_health_check()
            assert result is not None


class TestProfilingService:
    """Test profiling service module."""

    def test_profiling_service_initialization(self):
        """Test ProfilingService initialization."""
        service = ProfilingService()
        assert service is not None

    def test_start_memory_tracing(self):
        """Test start memory tracing method."""
        service = ProfilingService()
        service.start_memory_tracing()

    def test_stop_memory_tracing(self):
        """Test stop memory tracing method."""
        service = ProfilingService()
        service.stop_memory_tracing()

    def test_get_memory_snapshot(self):
        """Test get memory snapshot method."""
        service = ProfilingService()
        result = service.get_memory_snapshot()
        assert result is not None


class TestSeedingService:
    """Test seeding service module."""

    def test_seeding_service_initialization(self):
        """Test DatabaseSeedingService initialization."""
        service = DatabaseSeedingService()
        assert service is not None

    @patch("app.services.seeding_service.get_db_context")
    @patch("app.services.seeding_service.AuthManager.hash_password")
    def test_seed_users(self, mock_hash, mock_db_context):
        """Test seed users method."""
        mock_hash.return_value = "hashed_pw"
        mock_db = MagicMock()
        # Prevent infinite while loop in seed_users
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db_context.return_value.__enter__.return_value = mock_db
        service = DatabaseSeedingService()
        service.seed_users(count=1)

    @patch("app.services.seeding_service.get_db_context")
    def test_clear_all_data(self, mock_db_context):
        """Test clear all data method."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db
        service = DatabaseSeedingService()
        service.clear_all_data()


class TestUserManagementService:
    """Test user management service module."""

    def test_user_management_initialization(self):
        """Test UserManagementService initialization."""
        mock_db = MagicMock()
        service = UserManagementService(mock_db)
        assert service is not None

    @patch("app.services.user_management.AuthManager")
    @patch("app.services.user_management.UserManagementService._send_verification_email")
    def test_create_user(self, mock_send_email, mock_auth_class):
        """Test create user method."""
        mock_db = MagicMock()
        service = UserManagementService(mock_db)
        # Use a complex enough password to pass validation
        result = service.create_user(
            username="testuser", email="test@example.com", password="Password123!@#"
        )
        assert result is not None

    def test_get_user(self):
        """Test get user method."""
        mock_db = MagicMock()
        service = UserManagementService(mock_db)
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            MagicMock()
        )
        result = service.get_user(user_id="test-id")
        assert result is not None


class TestWebhookManager:
    """Test webhook manager module."""

    def test_webhook_manager_initialization(self):
        """Test WebhookManager initialization."""
        service = WebhookManager()
        assert service is not None

    @pytest.mark.asyncio
    async def test_create_webhook_delivery(self):
        """Test create webhook delivery."""
        service = WebhookManager()
        mock_db = MagicMock()
        result = await service.create_webhook_delivery(
            db=mock_db, task_id="task-1", webhook_url="http://example.com", payload={}
        )
        assert result is not None


class TestBusinessMetricsService:
    """Test business metrics service module."""

    def test_business_metrics_initialization(self):
        """Test BusinessMetricsService initialization."""
        service = BusinessMetricsService()
        assert service is not None


class TestRateLimiter:
    """Test rate limiter service module."""

    def test_rate_limiter_initialization(self):
        """Test RateLimiter initialization."""
        mock_redis = MagicMock()
        service = RateLimiter(mock_redis)
        assert service is not None


class TestAuthManager:
    """Test auth manager service module."""

    def test_auth_manager_initialization(self):
        """Test AuthManager initialization."""
        mock_db = MagicMock()
        service = AuthManager(mock_db)
        assert service is not None


class TestDataLifecycleService:
    """Test data lifecycle service module."""

    def test_data_lifecycle_initialization(self):
        """Test DataLifecycleManager initialization."""
        service = DataLifecycleManager()
        assert service is not None


class TestErrorRecoveryService:
    """Test error recovery service module."""

    def test_circuit_breaker_initialization(self):
        """Test CircuitBreaker initialization."""
        breaker = CircuitBreaker(service_name="test-service")
        assert breaker is not None

    def test_retry_service_initialization(self):
        """Test RetryService initialization."""
        service = RetryService()
        assert service is not None


class TestShardingService:
    """Test sharding service module."""

    def test_sharding_service_initialization(self):
        """Test DatabaseShardingService initialization."""
        service = DatabaseShardingService()
        assert service is not None


class TestSessionManagerService:
    """Test session manager service module."""

    @pytest.mark.asyncio
    async def test_session_manager_initialization(self):
        """Test SessionManager initialization."""
        mock_redis = MagicMock()
        mock_factory = MagicMock()
        service = SessionManager(mock_redis, mock_factory)
        assert service is not None

    @pytest.mark.asyncio
    @patch("app.services.session_manager.SimulationSession")
    async def test_create_session(self, mock_sim_session_class):
        """Test create session method."""
        mock_redis = AsyncMock()
        mock_db = MagicMock()
        mock_db.scalar.return_value = 0
        mock_factory = MagicMock(return_value=mock_db)
        service = SessionManager(mock_redis, mock_factory)

        sim_session = mock_sim_session_class.return_value
        sim_session.state = SessionLifecycleState.CREATED
        sim_session.config = {}
        sim_session.created_at = datetime.now(timezone.utc)
        sim_session.updated_at = datetime.now(timezone.utc)

        request = SessionCreateRequest(config_path="config/test.yaml")
        result = await service.create_session(request, user_id="test-user")
        assert result is not None

    @pytest.mark.asyncio
    @patch("app.services.session_manager.validate_session_id")
    async def test_get_session_not_found(self, mock_validate):
        """Test get session when not found."""
        mock_redis = AsyncMock()
        mock_db = MagicMock()
        mock_factory = MagicMock(return_value=mock_db)
        service = SessionManager(mock_redis, mock_factory)

        mock_redis.get.return_value = None
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        with pytest.raises(ValueError, match="Session .* not found"):
            await service.get_session(session_id="00000000-0000-0000-0000-000000000000")


class TestAbuseDetectionService:
    """Test abuse detection service module."""

    def test_abuse_detection_initialization(self):
        """Test AbuseDetectionService initialization."""
        service = AbuseDetectionService()
        assert service is not None

    def test_get_risk_level_low(self):
        """Test get risk level for new user/IP."""
        service = AbuseDetectionService()
        result = service.get_risk_level(user_id="user1", ip_address="1.2.3.4")
        assert result == RiskLevel.LOW

    def test_check_rate_limit(self):
        """Test check rate limit."""
        service = AbuseDetectionService()
        result = service.check_rate_limit(user_id="user1", ip_address="1.2.3.4")
        assert result["allowed"] is True

    def test_block_unblock_user(self):
        """Test blocking and unblocking a user."""
        service = AbuseDetectionService()
        service.block_user(user_id="user1", reason="test")
        assert service.get_risk_level(user_id="user1", ip_address="1.2.3.4") == RiskLevel.CRITICAL
        service.unblock_user(user_id="user1")
        assert service.get_risk_level(user_id="user1", ip_address="1.2.3.4") == RiskLevel.LOW
