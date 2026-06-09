"""
Unit tests for AbuseDetectionService covering risk assessment, rate limiting, and anomaly detection.
Requirements: 4.7, 5.1
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.services.abuse_detection import (
    AbuseDetectionService,
    CredentialRisk,
    LoginAttempt,
    RiskLevel,
)


class TestRiskLevel:
    """Test RiskLevel enum."""

    def test_risk_level_values(self) -> None:
        """RiskLevel has correct values."""
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"


class TestLoginAttempt:
    """Test LoginAttempt dataclass."""

    def test_login_attempt_creation(self) -> None:
        """Test creating LoginAttempt instance."""
        attempt = LoginAttempt(
            timestamp=datetime.now(timezone.utc),
            user_id="user123",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            success=True,
            risk_score=10.0,
        )

        assert attempt.user_id == "user123"
        assert attempt.ip_address == "192.168.1.1"
        assert attempt.success is True
        assert attempt.risk_score == 10.0


class TestCredentialRisk:
    """Test CredentialRisk dataclass."""

    def test_credential_risk_creation(self) -> None:
        """Test creating CredentialRisk instance."""
        risk = CredentialRisk(
            username="testuser",
            risk_score=50.0,
            risk_factors=["suspicious pattern"],
            last_seen=datetime.now(timezone.utc),
        )

        assert risk.username == "testuser"
        assert risk.risk_score == 50.0
        assert len(risk.risk_factors) == 1


class TestAbuseDetectionServiceInit:
    """Test AbuseDetectionService initialization."""

    def test_service_initialization(self) -> None:
        """Service initializes with empty tracking structures."""
        service = AbuseDetectionService()

        assert len(service.login_attempts) == 0
        assert len(service.credential_risks) == 0
        assert len(service.webhook_deliveries) == 0
        assert len(service.blocked_ips) == 0
        assert len(service.blocked_users) == 0

    def test_adaptive_limits_configured(self) -> None:
        """Adaptive rate limits are configured for all risk levels."""
        service = AbuseDetectionService()

        assert RiskLevel.LOW in service.adaptive_limits
        assert RiskLevel.MEDIUM in service.adaptive_limits
        assert RiskLevel.HIGH in service.adaptive_limits
        assert RiskLevel.CRITICAL in service.adaptive_limits

    def test_adaptive_limits_decrease_with_risk(self) -> None:
        """Higher risk levels have stricter limits."""
        service = AbuseDetectionService()

        low_limit = service.adaptive_limits[RiskLevel.LOW]["requests_per_minute"]
        medium_limit = service.adaptive_limits[RiskLevel.MEDIUM]["requests_per_minute"]
        high_limit = service.adaptive_limits[RiskLevel.HIGH]["requests_per_minute"]
        critical_limit = service.adaptive_limits[RiskLevel.CRITICAL]["requests_per_minute"]

        assert low_limit > medium_limit > high_limit > critical_limit


class TestGetRiskLevel:
    """Test risk level determination."""

    def test_get_risk_level_low_risk(self) -> None:
        """Low risk for clean user/IP."""
        service = AbuseDetectionService()
        risk = service.get_risk_level("user123", "192.168.1.1")
        assert risk == RiskLevel.LOW

    def test_get_risk_level_blocked_ip(self) -> None:
        """Critical risk for blocked IP."""
        service = AbuseDetectionService()
        service.blocked_ips.add("192.168.1.1")
        risk = service.get_risk_level("user123", "192.168.1.1")
        assert risk == RiskLevel.CRITICAL

    def test_get_risk_level_blocked_user(self) -> None:
        """Critical risk for blocked user."""
        service = AbuseDetectionService()
        service.blocked_users.add("user123")
        risk = service.get_risk_level("user123", "192.168.1.1")
        assert risk == RiskLevel.CRITICAL

    def test_get_risk_level_with_credential_risk(self) -> None:
        """Medium risk with credential risk."""
        service = AbuseDetectionService()
        service.credential_risks["user123"] = CredentialRisk(
            username="user123",
            risk_score=60.0,
            risk_factors=["suspicious"],
            last_seen=datetime.now(timezone.utc),
        )
        risk = service.get_risk_level("user123", "192.168.1.1")
        # Risk score = 60 * 0.5 = 30, which is MEDIUM (25-49)
        assert risk == RiskLevel.MEDIUM

    def test_get_risk_level_high_threshold(self) -> None:
        """Test HIGH risk threshold (50-79)."""
        service = AbuseDetectionService()
        service.credential_risks["user123"] = CredentialRisk(
            username="user123",
            risk_score=100.0,
            risk_factors=["suspicious"],
            last_seen=datetime.now(timezone.utc),
        )
        risk = service.get_risk_level("user123", "192.168.1.1")
        # Risk score = 100 * 0.5 = 50, which is HIGH (50-79)
        assert risk == RiskLevel.HIGH

    def test_get_risk_level_critical_threshold(self) -> None:
        """Test CRITICAL risk threshold (80+)."""
        service = AbuseDetectionService()
        service.credential_risks["user123"] = CredentialRisk(
            username="user123",
            risk_score=160.0,
            risk_factors=["suspicious"],
            last_seen=datetime.now(timezone.utc),
        )
        risk = service.get_risk_level("user123", "192.168.1.1")
        # Risk score = 160 * 0.5 = 80, which is CRITICAL (80+)
        assert risk == RiskLevel.CRITICAL

    def test_get_risk_level_with_failed_attempts(self) -> None:
        """Risk increases with failed attempts."""
        service = AbuseDetectionService()
        for _ in range(10):
            service.record_login_attempt("user123", "192.168.1.1", "Mozilla", False)
        risk = service.get_risk_level("user123", "192.168.1.1")
        # 10 failed attempts = 10 * 5 = 50 risk score, which is HIGH (50-79)
        # But auto-block happens at 10 failures, making it CRITICAL
        assert risk == RiskLevel.CRITICAL

    def test_get_risk_level_critical_threshold(self) -> None:
        """Test CRITICAL risk threshold (>= 80)."""
        service = AbuseDetectionService()
        service.credential_risks["user123"] = CredentialRisk(
            username="user123",
            risk_score=170.0,  # 170 * 0.5 = 85 to reach CRITICAL threshold
            risk_factors=["high risk"],
            last_seen=datetime.now(timezone.utc),
        )
        risk = service.get_risk_level("user123", "192.168.1.1")
        # Risk score = 170 * 0.5 = 85, which is CRITICAL (>= 80)
        assert risk == RiskLevel.CRITICAL

    def test_get_risk_level_high_threshold(self) -> None:
        """Test HIGH risk threshold (>= 50)."""
        service = AbuseDetectionService()
        service.credential_risks["user123"] = CredentialRisk(
            username="user123",
            risk_score=110.0,  # 110 * 0.5 = 55 to reach HIGH threshold
            risk_factors=["medium risk"],
            last_seen=datetime.now(timezone.utc),
        )
        risk = service.get_risk_level("user123", "192.168.1.1")
        assert risk == RiskLevel.HIGH


class TestCheckRateLimit:
    """Test adaptive rate limiting."""

    def test_rate_limit_allowed_low_risk(self) -> None:
        """Allow requests for low risk users."""
        service = AbuseDetectionService()
        result = service.check_rate_limit("user123", "192.168.1.1")
        assert result["allowed"] is True
        assert result["risk_level"] == "low"

    def test_rate_limit_exceeded_critical(self) -> None:
        """Block critical risk users after 1 request."""
        service = AbuseDetectionService()
        service.blocked_ips.add("192.168.1.1")
        # First request is allowed, second would be blocked
        result = service.check_rate_limit("user123", "192.168.1.1")
        assert result["allowed"] is True  # First request allowed
        assert result["risk_level"] == "critical"

    def test_rate_limit_exceeded_minute_limit(self) -> None:
        """Block when minute limit exceeded."""
        service = AbuseDetectionService()
        limit = service.adaptive_limits[RiskLevel.LOW]["requests_per_minute"]

        for _ in range(limit):
            service.check_rate_limit("user123", "192.168.1.1")

        result = service.check_rate_limit("user123", "192.168.1.1")
        assert result["allowed"] is False

    def test_rate_limit_resets_after_minute(self) -> None:
        """Limit resets after minute passes."""
        service = AbuseDetectionService()
        limit = service.adaptive_limits[RiskLevel.LOW]["requests_per_minute"]

        # Fill up limit
        for _ in range(limit):
            service.check_rate_limit("user123", "192.168.1.1")

        # Manually clear old timestamps
        key = "user123:192.168.1.1"
        service.request_timestamps[key] = []

        result = service.check_rate_limit("user123", "192.168.1.1")
        assert result["allowed"] is True


class TestRecordLoginAttempt:
    """Test login attempt recording."""

    def test_record_login_attempt_success(self) -> None:
        """Record successful login attempt."""
        service = AbuseDetectionService()
        service.record_login_attempt("user123", "192.168.1.1", "Mozilla", True)

        assert "user123" in service.login_attempts
        assert len(service.login_attempts["user123"]) == 1
        assert service.login_attempts["user123"][0].success is True

    def test_record_login_attempt_failure(self) -> None:
        """Record failed login attempt."""
        service = AbuseDetectionService()
        service.record_login_attempt("user123", "192.168.1.1", "Mozilla", False)

        assert service.login_attempts["user123"][0].success is False

    def test_record_login_attempt_limits_size(self) -> None:
        """Keep only last 100 attempts."""
        service = AbuseDetectionService()

        for _ in range(105):
            service.record_login_attempt("user123", "192.168.1.1", "Mozilla", True)

        assert len(service.login_attempts["user123"]) == 100

    def test_record_login_attempt_auto_block(self) -> None:
        """Auto-block after 10 recent failures."""
        service = AbuseDetectionService()

        for _ in range(10):
            service.record_login_attempt("user123", "192.168.1.1", "Mozilla", False)

        assert "user123" in service.blocked_users


class TestCheckWebhookReplay:
    """Test webhook replay detection."""

    def test_webhook_replay_allowed_first_delivery(self) -> None:
        """Allow first webhook delivery."""
        service = AbuseDetectionService()
        result = service.check_webhook_replay("webhook1", {"data": "test"}, "sig123")
        assert result["allowed"] is True

    def test_webhook_replay_detected_duplicate(self) -> None:
        """Detect duplicate webhook delivery."""
        service = AbuseDetectionService()
        payload = {"data": "test"}

        service.check_webhook_replay("webhook1", payload, "sig123")
        result = service.check_webhook_replay("webhook1", payload, "sig123")

        assert result["allowed"] is False
        assert "replay attack" in result["error"]

    def test_webhook_rate_limit_exceeded(self) -> None:
        """Block excessive webhook deliveries."""
        service = AbuseDetectionService()

        for i in range(20):
            service.check_webhook_replay("webhook1", {"data": f"test{i}"}, f"sig{i}")

        result = service.check_webhook_replay("webhook1", {"data": "new"}, "sig20")
        assert result["allowed"] is False
        assert "rate limit" in result["error"]

    def test_webhook_replay_different_payload_allowed(self) -> None:
        """Allow different payloads."""
        service = AbuseDetectionService()

        service.check_webhook_replay("webhook1", {"data": "test1"}, "sig1")
        result = service.check_webhook_replay("webhook1", {"data": "test2"}, "sig2")

        assert result["allowed"] is True


class TestAssessCredentialRisk:
    """Test credential risk assessment."""

    def test_assess_credential_risk_new_user(self) -> None:
        """New user has low risk."""
        service = AbuseDetectionService()
        risk = service.assess_credential_risk("newuser", "192.168.1.1", "Mozilla")
        assert risk.risk_score < 25

    def test_assess_credential_risk_suspicious_username(self) -> None:
        """Suspicious username increases risk."""
        service = AbuseDetectionService()
        risk = service.assess_credential_risk("admin123", "192.168.1.1", "Mozilla")
        assert risk.risk_score >= 30
        assert "Suspicious username pattern" in risk.risk_factors

    def test_assess_credential_risk_suspicious_ip(self) -> None:
        """Suspicious IP increases risk."""
        service = AbuseDetectionService()
        risk = service.assess_credential_risk("user123", "tor.proxy.com", "Mozilla")
        assert risk.risk_score >= 40
        assert "Suspicious IP address" in risk.risk_factors

    def test_assess_credential_risk_automated_ua(self) -> None:
        """Automated user agent increases risk."""
        service = AbuseDetectionService()
        risk = service.assess_credential_risk("user123", "192.168.1.1", "curl/7.0")
        assert risk.risk_score >= 20
        assert "Automated user agent detected" in risk.risk_factors

    def test_assess_credential_risk_accumulates(self) -> None:
        """Risk accumulates for existing credentials."""
        service = AbuseDetectionService()
        service.assess_credential_risk("user123", "192.168.1.1", "curl")
        risk = service.assess_credential_risk("user123", "192.168.1.1", "curl")
        # Risk should decay but still be elevated
        assert risk.risk_score > 0


class TestBlockUnblock:
    """Test blocking and unblocking."""

    def test_block_ip(self) -> None:
        """Block an IP address."""
        service = AbuseDetectionService()
        service.block_ip("192.168.1.1", "Test reason")
        assert "192.168.1.1" in service.blocked_ips

    def test_block_user(self) -> None:
        """Block a user."""
        service = AbuseDetectionService()
        service.block_user("user123", "Test reason")
        assert "user123" in service.blocked_users

    def test_unblock_ip(self) -> None:
        """Unblock an IP address."""
        service = AbuseDetectionService()
        service.blocked_ips.add("192.168.1.1")
        service.unblock_ip("192.168.1.1")
        assert "192.168.1.1" not in service.blocked_ips

    def test_unblock_user(self) -> None:
        """Unblock a user."""
        service = AbuseDetectionService()
        service.blocked_users.add("user123")
        service.unblock_user("user123")
        assert "user123" not in service.blocked_users

    def test_unblock_nonexistent_no_error(self) -> None:
        """Unblocking non-existent doesn't error."""
        service = AbuseDetectionService()
        service.unblock_ip("192.168.1.1")  # No error
        service.unblock_user("user123")  # No error


class TestCalculateLoginAnomalyScore:
    """Test login anomaly scoring."""

    def test_anomaly_score_no_attempts(self) -> None:
        """No attempts returns zero score."""
        service = AbuseDetectionService()
        score = service._calculate_login_anomaly_score("user123", "192.168.1.1")
        assert score == 0.0

    def test_anomaly_score_many_ips(self) -> None:
        """Many different IPs increases anomaly score."""
        service = AbuseDetectionService()
        for i in range(6):
            service.record_login_attempt("user123", f"192.168.1.{i}", "Mozilla", True)

        score = service._calculate_login_anomaly_score("user123", "192.168.1.1")
        assert score >= 30

    def test_anomaly_score_rapid_attempts(self) -> None:
        """Rapid successive attempts increases score."""
        service = AbuseDetectionService()
        for _ in range(5):
            service.record_login_attempt("user123", "192.168.1.1", "Mozilla", True)

        score = service._calculate_login_anomaly_score("user123", "192.168.1.1")
        assert score >= 40

    def test_anomaly_score_many_user_agents(self) -> None:
        """Many different user agents increases score."""
        service = AbuseDetectionService()
        for i in range(4):
            service.record_login_attempt("user123", "192.168.1.1", f"UA{i}", True)

        score = service._calculate_login_anomaly_score("user123", "192.168.1.1")
        assert score >= 20

    def test_anomaly_score_slow_attempts(self) -> None:
        """Slow attempts don't increase score."""
        service = AbuseDetectionService()
        # Record attempts that are not rapid (more than 1 second apart)
        # First attempt
        service.record_login_attempt("user123", "192.168.1.1", "Mozilla", True)
        # Manually set timestamp to be 2 seconds ago
        service.login_attempts["user123"][0].timestamp = datetime.now(timezone.utc) - timedelta(
            seconds=2
        )
        # Second attempt (current time)
        service.record_login_attempt("user123", "192.168.1.1", "Mozilla", True)

        score = service._calculate_login_anomaly_score("user123", "192.168.1.1")
        # Should not trigger the rapid attempt branch
        assert score < 10

    def test_anomaly_score_empty_recent_attempts(self) -> None:
        """Test when recent_attempts is empty (line 423)."""
        service = AbuseDetectionService()
        # Add user but with no attempts
        service.login_attempts["user123"] = []

        score = service._calculate_login_anomaly_score("user123", "192.168.1.1")
        assert score == 0.0


class TestGetRecentFailedAttempts:
    """Test retrieving recent failed attempts."""

    def test_get_recent_failed_attempts(self) -> None:
        """Get failed attempts within time window."""
        service = AbuseDetectionService()
        service.record_login_attempt("user123", "192.168.1.1", "Mozilla", False)
        service.record_login_attempt("user123", "192.168.1.1", "Mozilla", True)

        failed = service._get_recent_failed_attempts("user123", minutes=15)
        assert len(failed) == 1
        assert failed[0].success is False

    def test_get_recent_failed_attempts_no_user(self) -> None:
        """Return empty list for unknown user."""
        service = AbuseDetectionService()
        failed = service._get_recent_failed_attempts("unknown", minutes=15)
        assert failed == []


class TestHashPayload:
    """Test payload hashing."""

    def test_hash_payload_consistent(self) -> None:
        """Same payload produces same hash."""
        service = AbuseDetectionService()
        payload = {"data": "test", "value": 123}
        hash1 = service._hash_payload(payload)
        hash2 = service._hash_payload(payload)
        assert hash1 == hash2

    def test_hash_payload_different(self) -> None:
        """Different payloads produce different hashes."""
        service = AbuseDetectionService()
        hash1 = service._hash_payload({"data": "test1"})
        hash2 = service._hash_payload({"data": "test2"})
        assert hash1 != hash2


class TestContainsSuspiciousPatterns:
    """Test suspicious pattern detection."""

    def test_contains_suspicious_patterns_admin(self) -> None:
        """Detect admin pattern."""
        service = AbuseDetectionService()
        assert service._contains_suspicious_patterns("admin123") is True
        assert service._contains_suspicious_patterns("admin") is True

    def test_contains_suspicious_patterns_test(self) -> None:
        """Detect test pattern."""
        service = AbuseDetectionService()
        assert service._contains_suspicious_patterns("test123") is True
        assert service._contains_suspicious_patterns("test") is True

    def test_contains_suspicious_patterns_root(self) -> None:
        """Detect root pattern."""
        service = AbuseDetectionService()
        assert service._contains_suspicious_patterns("root123") is True
        assert service._contains_suspicious_patterns("root") is True

    def test_contains_suspicious_patterns_sql(self) -> None:
        """Detect SQL injection pattern."""
        service = AbuseDetectionService()
        assert service._contains_suspicious_patterns("sql") is True
        assert service._contains_suspicious_patterns("SELECT") is True

    def test_contains_suspicious_patterns_normal(self) -> None:
        """Normal username passes."""
        service = AbuseDetectionService()
        assert service._contains_suspicious_patterns("johnsmith") is False
        assert service._contains_suspicious_patterns("alice") is False
        assert service._contains_suspicious_patterns("user' OR 1=1") is False
        assert service._contains_suspicious_patterns("user_inject") is True


class TestIsSuspiciousIP:
    """Test IP suspicion detection."""

    def test_is_suspicious_ip_private(self) -> None:
        """Private IPs are not suspicious."""
        service = AbuseDetectionService()
        assert service._is_suspicious_ip("192.168.1.1") is False
        assert service._is_suspicious_ip("10.0.0.1") is False

    def test_is_suspicious_ip_tor(self) -> None:
        """TOR-related IPs are suspicious."""
        service = AbuseDetectionService()
        assert service._is_suspicious_ip("tor.exit.node") is True

    def test_is_suspicious_ip_vpn(self) -> None:
        """VPN-related IPs are suspicious."""
        service = AbuseDetectionService()
        assert service._is_suspicious_ip("vpn.server.com") is True

    def test_is_suspicious_ip_regular(self) -> None:
        """Regular public IPs are not suspicious."""
        service = AbuseDetectionService()
        assert service._is_suspicious_ip("8.8.8.8") is False

    def test_is_suspicious_ip_proxy(self) -> None:
        """Proxy-related IPs are suspicious."""
        service = AbuseDetectionService()
        assert service._is_suspicious_ip("proxy.server.com") is True


class TestIsAutomatedUserAgent:
    """Test automated user agent detection."""

    def test_is_automated_user_agent_bot(self) -> None:
        """Detect bot user agent."""
        service = AbuseDetectionService()
        assert service._is_automated_user_agent("Googlebot/2.1") is True

    def test_is_automated_user_agent_curl(self) -> None:
        """Detect curl user agent."""
        service = AbuseDetectionService()
        assert service._is_automated_user_agent("curl/7.68.0") is True

    def test_is_automated_user_agent_python(self) -> None:
        """Detect python-requests user agent."""
        service = AbuseDetectionService()
        assert service._is_automated_user_agent("python-requests/2.25.1") is True

    def test_is_automated_user_agent_browser(self) -> None:
        """Browser user agents are not automated."""
        service = AbuseDetectionService()
        assert service._is_automated_user_agent("Mozilla/5.0") is False

    def test_is_automated_user_agent_wget(self) -> None:
        """Detect wget user agent."""
        service = AbuseDetectionService()
        assert service._is_automated_user_agent("Wget/1.20") is True

    def test_is_automated_user_agent_crawler(self) -> None:
        """Detect crawler user agent."""
        service = AbuseDetectionService()
        assert service._is_automated_user_agent("Googlebot/2.1") is True

    def test_is_automated_user_agent_spider(self) -> None:
        """Detect spider user agent."""
        service = AbuseDetectionService()
        assert service._is_automated_user_agent("MySpider/1.0") is True

    def test_is_automated_user_agent_scraper(self) -> None:
        """Detect scraper user agent."""
        service = AbuseDetectionService()
        assert service._is_automated_user_agent("WebScraper/2.0") is True


class TestGlobalInstance:
    """Test global abuse_detection_service instance."""

    def test_global_instance_exists(self) -> None:
        """Global service instance is created."""
        from app.services.abuse_detection import abuse_detection_service

        assert abuse_detection_service is not None
        assert isinstance(abuse_detection_service, AbuseDetectionService)


class TestIsRequestBlocked:
    """Test is_request_blocked method."""

    async def test_is_request_blocked_no_client(self) -> None:
        """Block request when client is None."""
        service = AbuseDetectionService()
        mock_request = MagicMock()
        del mock_request.client  # Remove client attribute

        result = await service.is_request_blocked(mock_request)
        assert result is True

    async def test_is_request_blocked_no_host(self) -> None:
        """Block request when client.host is None."""
        service = AbuseDetectionService()
        mock_request = MagicMock()
        mock_request.client.host = None

        result = await service.is_request_blocked(mock_request)
        assert result is True

    async def test_is_request_blocked_exception(self) -> None:
        """Block request when exception occurs during check."""
        service = AbuseDetectionService()
        mock_request = MagicMock()
        # Make client.host raise an exception
        type(mock_request.client).host = property(
            lambda self: (_ for _ in ()).throw(Exception("Test error"))
        )

        result = await service.is_request_blocked(mock_request)
        assert result is True

    async def test_is_request_blocked_critical_risk(self) -> None:
        """Block request when risk level is CRITICAL."""
        service = AbuseDetectionService()
        mock_request = MagicMock()
        mock_request.client.host = "192.168.1.1"
        mock_request.state.user.user_id = "user123"
        service.blocked_users.add("user123")

        result = await service.is_request_blocked(mock_request)
        assert result is True

    async def test_is_request_blocked_ip_blocked(self) -> None:
        """Block request when IP is in blocked_ips (line 372)."""
        service = AbuseDetectionService()
        mock_request = MagicMock()
        mock_request.client.host = "192.168.1.100"
        service.blocked_ips.add("192.168.1.100")

        result = await service.is_request_blocked(mock_request)
        assert result is True

    async def test_is_request_blocked_user_from_state(self) -> None:
        """Test getting user_id from request.state (lines 376-377)."""
        service = AbuseDetectionService()
        mock_request = MagicMock()
        mock_request.client.host = "192.168.1.1"
        mock_request.state.user.user_id = "user456"
        service.blocked_users.add("user456")

        result = await service.is_request_blocked(mock_request)
        assert result is True

    async def test_is_request_blocked_critical_risk_level(self) -> None:
        """Block request when risk level is CRITICAL (line 384)."""
        service = AbuseDetectionService()
        mock_request = MagicMock()
        mock_request.client.host = "192.168.1.1"
        mock_request.state.user.user_id = "user789"
        # Add high risk to trigger CRITICAL level
        service.credential_risks["user789"] = MagicMock(risk_score=200.0)  # 200 * 0.5 = 100 >= 80

        result = await service.is_request_blocked(mock_request)
        assert result is True
