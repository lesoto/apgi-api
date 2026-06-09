"""
APGI API Demonstration Script

This script demonstrates all functionality of the APGI consciousness modeling API.
It assumes the API server is running on http://localhost:8000.

Requirements:
- requests library: pip install requests
- The API server must be running with test/demo credentials available

Usage:
    python demo_script.py
"""

import json
import tempfile
import time
from typing import Any, Dict, Optional, cast

import requests


class APIDemo:
    """Demonstrates APGI API functionality."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        """Initialize the demo with base URL."""
        self.base_url = base_url.rstrip("/")
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.session_id: Optional[str] = None
        self.task_id: Optional[str] = None

    def make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        auth: bool = True,
    ) -> Dict[str, Any]:
        """Make an HTTP request to the API."""
        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/json"}

        if auth and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers, json=data, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            print(f"\n{method.upper()} {endpoint}")
            print(f"Status: {response.status_code}")

            if response.status_code >= 400:
                print(f"Error: {response.text}")
                # Return the JSON response even for errors, so we can check if server is responding
                try:
                    return cast(Dict[str, Any], response.json())
                except json.JSONDecodeError:
                    return {"text": response.text}

            try:
                return cast(Dict[str, Any], response.json())
            except json.JSONDecodeError:
                print("Response: (non-JSON)")
                return {"text": response.text}

        except requests.RequestException as e:
            print(f"Request failed: {e}")
            return {}

    def run_demo(self) -> None:
        """Run the complete API demonstration."""
        print("=== APGI API Demonstration ===\n")

        # Check if server is running
        print("Checking server availability...")
        health_response = self.make_request("GET", "/health")

        # Check if we got any response from server (even if unhealthy)
        if health_response is None or (
            isinstance(health_response, dict) and len(health_response) == 0
        ):
            print("❌ API server is not running on http://localhost:8000")
            print("\nTo run this demo, start the API server first:")
            print("\nOption 1 - Docker Compose (Recommended):")
            print("  cd /path/to/apgi-api")
            print("  docker-compose -f deployment/docker-compose.yml up")
            print("\nOption 2 - Manual setup:")
            print("  1. Start PostgreSQL and Redis")
            print("  2. Run: alembic upgrade head")
            print("  3. Run: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
            print("\nOnce the server is running, re-run this script.")
            return

        if health_response and "status" in health_response:
            print(
                "✓ Server is running (note: some services may be unhealthy without Celery worker)\n"
            )
        else:
            print("✓ Server is running\n")

        # 1. Health Checks
        print("1. HEALTH CHECKS")
        self.make_request("GET", "/health")
        self.make_request("GET", "/health/ready")
        self.make_request("GET", "/health/live")
        self.make_request("GET", "/v1/version")
        self.make_request("GET", "/v1/metrics", auth=False)

        # 2. Authentication
        print("\n2. AUTHENTICATION")

        # Try to get the default user credentials from the temp file or database
        login_data = None
        try:
            import pathlib

            # Find the credentials file
            temp_dir = pathlib.Path(tempfile.gettempdir())
            cred_files = list(temp_dir.glob("apgi_default_user_*.txt"))

            if cred_files:
                # Read the most recent credentials file
                cred_file = max(cred_files, key=lambda p: p.stat().st_mtime)
                content = cred_file.read_text()

                # Parse username and password from file
                username = None
                password = None
                for line in content.splitlines():
                    if line.startswith("Username: "):
                        username = line.replace("Username: ", "").strip()
                    elif line.startswith("Password: "):
                        password = line.replace("Password: ", "").strip()

                if username and password:
                    login_data = {
                        "username": username,
                        "password": password,
                        "remember_me": False,
                    }
        except Exception:  # nosec: B110 - login data fetch failure, will fallback to database
            pass

        # Fallback to database query
        if not login_data:
            try:
                import psycopg2

                conn = psycopg2.connect(
                    host="127.0.0.1",
                    port="5432",
                    database="apgi_api_dev",
                    user="apgi_dev",
                    password="dev_password",  # nosec: B106 - demo script credential
                )
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT username FROM users WHERE username LIKE 'default_%' LIMIT 1;"
                )
                result = cursor.fetchone()
                cursor.close()
                conn.close()

                if result:
                    default_username = result[0]
                    # For this demo, we need the plaintext password which was in the temp file
                    # If temp file is gone, we can't login (passwords are hashed)
                    print(
                        "✗ Credentials file not found and password cannot be recovered from database"
                    )
                    print("  Please restart the server to generate new credentials")
                    return
            except Exception:
                print("✗ Login failed - could not retrieve credentials")
                return
        login_response = self.make_request("POST", "/v1/auth/login", login_data, auth=False)
        if "access_token" in login_response:
            self.access_token = login_response["access_token"]
            self.refresh_token = login_response.get("refresh_token")
            print("✓ Login successful")
        else:
            print("✗ Login failed - stopping demo")
            return

        # 3. Session Management
        print("\n3. SESSION MANAGEMENT")

        # Create session
        session_data = {
            "custom_config": {"demo": True, "test_mode": True},
            "description": "API Demonstration Session",
        }
        create_response = self.make_request("POST", "/v1/sessions", session_data)
        if "session_id" in create_response:
            self.session_id = create_response["session_id"]
            print(f"✓ Session created: {self.session_id}")
        else:
            print("✗ Session creation failed - stopping demo")
            return

        # Get session details
        self.make_request("GET", f"/v1/sessions/{self.session_id}")

        # Start session
        start_response = self.make_request("POST", f"/v1/sessions/{self.session_id}/start")
        if start_response:
            print("✓ Session started")
        time.sleep(1)  # Brief pause

        # Get session state
        self.make_request("GET", f"/v1/sessions/{self.session_id}/state")

        # Get session metrics
        self.make_request("GET", f"/v1/sessions/{self.session_id}/metrics")

        # 4. Task Execution
        print("\n4. TASK EXECUTION")

        # Submit task
        task_data = {
            "task_type": "attentional_blink",
            "parameters": {"num_trials": 10, "duration": 100},
            "priority": 5,
            "webhook_url": "https://example.com/webhook",
        }
        task_response = self.make_request(
            "POST", f"/v1/sessions/{self.session_id}/tasks", task_data
        )
        if "task_id" in task_response:
            self.task_id = task_response["task_id"]
            print(f"✓ Task submitted: {self.task_id}")
        else:
            print("✗ Task submission failed")

        if self.task_id:
            # Get task status
            self.make_request("GET", f"/v1/tasks/{self.task_id}")

            # Wait a moment for task processing
            time.sleep(2)

            # Get task result
            self.make_request("GET", f"/v1/tasks/{self.task_id}/result")

            # Cancel task (if still running)
            self.make_request("DELETE", f"/v1/tasks/{self.task_id}")

        # 5. Session Control
        print("\n5. SESSION CONTROL")

        # Pause session
        self.make_request("POST", f"/v1/sessions/{self.session_id}/pause")

        # Resume session
        self.make_request("POST", f"/v1/sessions/{self.session_id}/start")

        # Stop session
        self.make_request("POST", f"/v1/sessions/{self.session_id}/stop")

        # Reset session
        self.make_request("POST", f"/v1/sessions/{self.session_id}/reset")

        # 6. Data Export
        print("\n6. DATA EXPORT")

        # Export as JSON
        export_json = self.make_request("GET", f"/v1/sessions/{self.session_id}/export/json")
        if export_json:
            print(f"✓ Exported {len(json.dumps(export_json))} characters of JSON data")

        # Export as CSV
        export_csv = self.make_request("GET", f"/v1/sessions/{self.session_id}/export/csv")
        if export_csv:
            print("✓ Exported CSV data")

        # 7. Metrics Dashboard
        print("\n7. METRICS DASHBOARD")

        self.make_request("GET", "/v1/dashboard")
        self.make_request("GET", "/v1/dashboard/overview")
        self.make_request("GET", "/v1/dashboard/sessions")
        self.make_request("GET", "/v1/dashboard/tasks")
        self.make_request("GET", "/v1/dashboard/users")
        self.make_request("GET", "/v1/dashboard/templates")

        # 8. Token Management
        print("\n8. TOKEN MANAGEMENT")

        # Refresh token
        if self.refresh_token:
            refresh_data = {"refresh_token": self.refresh_token}
            refresh_response = self.make_request(
                "POST", "/v1/auth/refresh", refresh_data, auth=False
            )
            if "access_token" in refresh_response:
                self.access_token = refresh_response["access_token"]
                print("✓ Token refreshed")
            else:
                print("✗ Token refresh failed")

        # Logout
        if self.refresh_token:
            logout_data = {"refresh_token": self.refresh_token}
            logout_response = self.make_request("POST", "/v1/auth/logout", logout_data)
            if logout_response == {}:  # 204 No Content returns empty dict
                print("✓ Logout successful")
            else:
                print("✗ Logout failed")

        # 9. Cleanup
        print("\n9. CLEANUP")

        # Delete session
        delete_response = self.make_request("DELETE", f"/v1/sessions/{self.session_id}")
        if delete_response == {}:  # 204 No Content
            print("✓ Session deleted")
        else:
            print("✗ Session deletion failed")

        print("\n=== Demo Complete ===")
        print("All major API functionality has been demonstrated.")
        print("Check the server logs for detailed execution information.")


if __name__ == "__main__":
    # Run the demonstration
    demo = APIDemo()
    demo.run_demo()
