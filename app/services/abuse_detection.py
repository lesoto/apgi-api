"""
Abuse Detection and Adaptive Rate Limiting Service

Provides:
- Adaptive rate limiting based on credential risk and user behavior
- Login anomaly detection (location, timing, device fingerprinting)
- Webhook replay protection with stricter controls
- Risk scoring and automated blocking

This service works alongside the security validation middleware to provide
comprehensive abuse prevention.
"""

import hashlib
import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk level classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class LoginAttempt:
    """Represents a login attempt for anomaly detection."""

    timestamp: datetime
    user_id: str
    ip_address: str
    user_agent: str
    success: bool
    risk_score: float


@dataclass
class CredentialRisk:
    """Risk assessment for credentials."""

    username: str
    risk_score: float
    risk_factors: List[str]
    last_seen: datetime


class AbuseDetectionService:
    """
    Service for detecting and preventing abuse through adaptive rate limiting
    and anomaly detection.
    """

    def __init__(self) -> None:
        """Initialize abuse detection service."""
        # Track login attempts per user for anomaly detection
        self.login_attempts: Dict[str, List[LoginAttempt]] = defaultdict(list)

        # Track credential risk scores
        self.credential_risks: Dict[str, CredentialRisk] = {}

        # Track webhook delivery attempts for replay protection
        self.webhook_deliveries: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        # Adaptive rate limits per risk level
        self.adaptive_limits = {
            RiskLevel.LOW: {"requests_per_minute": 100, "requests_per_hour": 1000},
            RiskLevel.MEDIUM: {"requests_per_minute": 30, "requests_per_hour": 300},
            RiskLevel.HIGH: {"requests_per_minute": 10, "requests_per_hour": 100},
            RiskLevel.CRITICAL: {"requests_per_minute": 1, "requests_per_hour": 10},
        }

        # Blocked IPs and users
        self.blocked_ips: Set[str] = set()
        self.blocked_users: Set[str] = set()

        # Track request timestamps for rate limiting
        self.request_timestamps: Dict[str, List[datetime]] = defaultdict(list)

        logger.info("Abuse detection service initialized")

    def get_risk_level(self, user_id: str, ip_address: str) -> RiskLevel:
        """
        Determine risk level for a user/IP combination.

        Args:
            user_id: User identifier
            ip_address: Client IP address

        Returns:
            RiskLevel enum
        """
        risk_score = 0.0

        # Check if IP or user is blocked
        if ip_address in self.blocked_ips:
            return RiskLevel.CRITICAL
        if user_id in self.blocked_users:
            return RiskLevel.CRITICAL

        # Check credential risk
        if user_id in self.credential_risks:
            risk_score += self.credential_risks[user_id].risk_score * 0.5

        # Check login anomaly score
        anomaly_score = self._calculate_login_anomaly_score(user_id, ip_address)
        risk_score += anomaly_score * 0.3

        # Check recent failed attempts
        recent_attempts = self._get_recent_failed_attempts(user_id, minutes=15)
        risk_score += len(recent_attempts) * 5

        # Determine risk level based on score
        if risk_score >= 80:
            return RiskLevel.CRITICAL
        elif risk_score >= 50:
            return RiskLevel.HIGH
        elif risk_score >= 25:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def check_rate_limit(self, user_id: str, ip_address: str) -> Dict[str, Any]:
        """
        Check adaptive rate limit based on risk level.

        Args:
            user_id: User identifier
            ip_address: Client IP address

        Returns:
            Dict with 'allowed' boolean and 'retry_after' seconds if blocked
        """
        risk_level = self.get_risk_level(user_id, ip_address)
        limits = self.adaptive_limits[risk_level]

        # Get recent request count for this user/IP
        key = f"{user_id}:{ip_address}"
        now = datetime.now(timezone.utc)

        # Clean old timestamps
        if key not in self.request_timestamps:
            self.request_timestamps[key] = []

        self.request_timestamps[key] = [
            ts for ts in self.request_timestamps[key] if ts > now - timedelta(minutes=1)
        ]

        # Check minute limit
        if len(self.request_timestamps[key]) >= limits["requests_per_minute"]:
            logger.warning(
                f"Rate limit exceeded for user {user_id} at risk level {risk_level.value}"
            )
            return {
                "allowed": False,
                "retry_after": 60,
                "risk_level": risk_level.value,
                "limit": limits["requests_per_minute"],
            }

        # Add current request timestamp
        self.request_timestamps[key].append(now)

        return {
            "allowed": True,
            "risk_level": risk_level.value,
            "limit": limits["requests_per_minute"],
        }

    def record_login_attempt(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        success: bool,
    ) -> None:
        """
        Record a login attempt for anomaly detection.

        Args:
            user_id: User identifier
            ip_address: Client IP address
            user_agent: User agent string
            success: Whether login was successful
        """
        attempt = LoginAttempt(
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            risk_score=self._calculate_login_anomaly_score(user_id, ip_address),
        )

        self.login_attempts[user_id].append(attempt)

        # Clean old attempts (keep last 100)
        if len(self.login_attempts[user_id]) > 100:
            self.login_attempts[user_id] = self.login_attempts[user_id][-100:]

        # Auto-block if too many recent failures
        recent_failures = self._get_recent_failed_attempts(user_id, minutes=10)
        if len(recent_failures) >= 10:
            logger.warning(f"Auto-blocking user {user_id} due to excessive failed logins")
            self.blocked_users.add(user_id)

    def check_webhook_replay(
        self,
        webhook_id: str,
        payload: Dict[str, Any],
        signature: str,
    ) -> Dict[str, Any]:
        """
        Check for webhook replay attacks with stricter controls.

        Args:
            webhook_id: Webhook identifier
            payload: Webhook payload
            signature: Webhook signature

        Returns:
            Dict with 'allowed' boolean and error message if blocked
        """
        # Create payload hash for replay detection
        payload_hash = self._hash_payload(payload)

        # Check for recent duplicate deliveries
        now = datetime.now(timezone.utc)
        recent_deliveries = [
            d
            for d in self.webhook_deliveries[webhook_id]
            if now - d["timestamp"] < timedelta(minutes=5)
        ]

        for delivery in recent_deliveries:
            if delivery["hash"] == payload_hash:
                logger.warning(f"Webhook replay detected for webhook {webhook_id}")
                return {
                    "allowed": False,
                    "error": "Duplicate webhook delivery detected (replay attack)",
                }

        # Check for excessive delivery rate
        if len(recent_deliveries) >= 20:
            logger.warning(f"Webhook rate limit exceeded for webhook {webhook_id}")
            return {
                "allowed": False,
                "error": "Webhook delivery rate limit exceeded",
            }

        # Record this delivery
        self.webhook_deliveries[webhook_id].append(
            {
                "timestamp": now,
                "hash": payload_hash,
                "signature": signature,
            }
        )

        # Clean old deliveries
        self.webhook_deliveries[webhook_id] = [
            d
            for d in self.webhook_deliveries[webhook_id]
            if now - d["timestamp"] < timedelta(hours=1)
        ]

        return {"allowed": True}

    def assess_credential_risk(
        self,
        username: str,
        ip_address: str,
        user_agent: str,
    ) -> CredentialRisk:
        """
        Assess risk level for a credential (username).

        Args:
            username: Username to assess
            ip_address: Client IP address
            user_agent: User agent string

        Returns:
            CredentialRisk object
        """
        risk_factors = []
        risk_score = 0.0

        # Check if username has been associated with suspicious activity
        if username in self.credential_risks:
            existing_risk = self.credential_risks[username]
            risk_score = existing_risk.risk_score * 0.7  # Decay old risk
            risk_factors.extend(existing_risk.risk_factors)

        # Check for common attack patterns in username
        if self._contains_suspicious_patterns(username):
            risk_score += 30
            risk_factors.append("Suspicious username pattern")

        # Check IP reputation (simplified - in production use a real IP reputation service)
        if self._is_suspicious_ip(ip_address):
            risk_score += 40
            risk_factors.append("Suspicious IP address")

        # Check user agent for automation tools
        if self._is_automated_user_agent(user_agent):
            risk_score += 20
            risk_factors.append("Automated user agent detected")

        # Cap risk score at 100
        risk_score = min(risk_score, 100.0)

        credential_risk = CredentialRisk(
            username=username,
            risk_score=risk_score,
            risk_factors=risk_factors,
            last_seen=datetime.now(timezone.utc),
        )

        self.credential_risks[username] = credential_risk

        return credential_risk

    def block_ip(self, ip_address: str, reason: str, duration_hours: int = 24) -> None:
        """
        Block an IP address for a specified duration.

        Args:
            ip_address: IP address to block
            reason: Reason for blocking
            duration_hours: Duration in hours (default 24)
        """
        self.blocked_ips.add(ip_address)
        logger.warning(f"Blocked IP {ip_address} for {duration_hours} hours: {reason}")

        # In production, you would schedule an unblock task
        # For now, this is a manual block

    async def is_request_blocked(self, request: Any) -> bool:
        """
        Check if a request should be blocked based on various risk factors.

        Args:
            request: The HTTP request to check

        Returns:
            True if request should be blocked, False otherwise
        """
        try:
            # Extract client information from request
            client = getattr(request, "client", None)
            if client is None:
                # Can't determine client, block for safety
                return True

            host = getattr(client, "host", None)
            if host is None:
                return True

            # Check if IP is blocked
            if host in self.blocked_ips:
                return True

            # Get user ID from request state if authenticated
            user_id = None
            if hasattr(request, "state") and hasattr(request.state, "user"):
                user_id = getattr(request.state.user, "user_id", None)

            if user_id and user_id in self.blocked_users:
                return True

            # Check risk level
            risk_level = self.get_risk_level(user_id or "anonymous", host)
            if risk_level == RiskLevel.CRITICAL:
                return True

            return False
        except Exception as e:
            # If we can't determine, block for safety
            logger.warning(f"Error checking if request blocked: {e}")
            return True

    def block_user(self, user_id: str, reason: str) -> None:
        """
        Block a user account.

        Args:
            user_id: User ID to block
            reason: Reason for blocking
        """
        self.blocked_users.add(user_id)
        logger.warning(f"Blocked user {user_id}: {reason}")

    def unblock_ip(self, ip_address: str) -> None:
        """Unblock an IP address."""
        if ip_address in self.blocked_ips:
            self.blocked_ips.remove(ip_address)
            logger.info(f"Unblocked IP {ip_address}")

    def unblock_user(self, user_id: str) -> None:
        """Unblock a user."""
        if user_id in self.blocked_users:
            self.blocked_users.remove(user_id)
            logger.info(f"Unblocked user {user_id}")

    def _calculate_login_anomaly_score(self, user_id: str, ip_address: str) -> float:
        """Calculate anomaly score based on login patterns."""
        if user_id not in self.login_attempts:
            return 0.0

        recent_attempts = self.login_attempts[user_id][-20:]  # Last 20 attempts
        if not recent_attempts:
            return 0.0

        anomaly_score = 0.0

        # Check for IP changes
        unique_ips = set(attempt.ip_address for attempt in recent_attempts)
        if len(unique_ips) > 5:
            anomaly_score += 30

        # Check for rapid successive attempts
        timestamps = [attempt.timestamp for attempt in recent_attempts]
        for i in range(1, len(timestamps)):
            if (timestamps[i] - timestamps[i - 1]).total_seconds() < 1:
                anomaly_score += 10

        # Check for user agent changes
        unique_uas = set(attempt.user_agent for attempt in recent_attempts)
        if len(unique_uas) > 3:
            anomaly_score += 20

        # Normalize score to 0-100
        return min(anomaly_score, 100.0)

    def _get_recent_failed_attempts(self, user_id: str, minutes: int) -> List[LoginAttempt]:
        """Get recent failed login attempts for a user."""
        if user_id not in self.login_attempts:
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        return [
            attempt
            for attempt in self.login_attempts[user_id]
            if not attempt.success and attempt.timestamp > cutoff
        ]

    def _hash_payload(self, payload: Dict[str, Any]) -> str:
        """Create a hash of the payload for replay detection."""
        payload_str = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(payload_str.encode()).hexdigest()

    def _contains_suspicious_patterns(self, username: str) -> bool:
        """Check if username contains suspicious patterns."""
        suspicious_patterns = [
            r"admin\d*",
            r"test\d*",
            r"root\d*",
            r"sql",
            r"inject",
            r"<script",
            r"union",
            r"select",
        ]

        username_lower = username.lower()
        for pattern in suspicious_patterns:
            if re.search(pattern, username_lower):
                return True
        return False

    def _is_suspicious_ip(self, ip_address: str) -> bool:
        """
        Check if IP is suspicious (simplified check).

        In production, integrate with IP reputation services like:
        - AbuseIPDB
        - Project Honey Pot
        - MaxMind GeoIP
        """
        # Simplified checks
        if ip_address.startswith("192.168.") or ip_address.startswith("10."):
            return False  # Private IPs are generally not suspicious

        # Check for common VPN/proxy patterns (simplified)
        suspicious_patterns = ["tor", "vpn", "proxy"]
        if any(pattern in ip_address.lower() for pattern in suspicious_patterns):
            return True

        return False

    def _is_automated_user_agent(self, user_agent: str) -> bool:
        """Check if user agent indicates automation."""
        automated_indicators = [
            "bot",
            "crawler",
            "spider",
            "scraper",
            "curl",
            "wget",
            "python-requests",
            "postman",
            "insomnia",
        ]

        user_agent_lower = user_agent.lower()
        return any(indicator in user_agent_lower for indicator in automated_indicators)


# Global instance
abuse_detection_service = AbuseDetectionService()
