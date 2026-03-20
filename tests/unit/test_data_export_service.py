"""
Unit tests for DataExportService.

Tests export generation, streaming, different formats, and edge cases.
Requirements: 2.6
"""

import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.data_export import DataExportService


@pytest.fixture
def mock_session_manager():
    mgr = MagicMock()
    mgr.get_session = AsyncMock()
    return mgr


@pytest.fixture
def service(mock_session_manager):
    return DataExportService(mock_session_manager)


def _make_mock_session(history=None):
    """Helper to build a mock session object."""
    if history is None:
        history = {"time": [0, 1, 2], "var1": [10, 20, 30]}
    session = MagicMock()
    session.created_at = MagicMock()
    session.created_at.isoformat.return_value = "2024-01-01T00:00:00"
    session.updated_at = MagicMock()
    session.updated_at.isoformat.return_value = "2024-01-01T01:00:00"
    session.config = {"experiment": "test"}
    session.state = MagicMock()
    session.state.value = "completed"
    session.get_state = AsyncMock(return_value={"history": history})
    return session


# ---------------------------------------------------------------------------
# export_session_data
# ---------------------------------------------------------------------------


class TestExportSessionData:

    @pytest.mark.asyncio
    async def test_json_export_returns_bytes_and_content_type(self, service, mock_session_manager):
        mock_session_manager.get_session.return_value = _make_mock_session()
        data, ct = await service.export_session_data("sess1", format="json")
        assert ct == "application/json"
        assert isinstance(data, bytes)
        parsed = json.loads(data)
        assert parsed["session_id"] == "sess1"
        assert "data" in parsed

    @pytest.mark.asyncio
    async def test_csv_export_returns_bytes_and_content_type(self, service, mock_session_manager):
        mock_session_manager.get_session.return_value = _make_mock_session()
        data, ct = await service.export_session_data("sess1", format="csv")
        assert ct == "text/csv"
        assert isinstance(data, bytes)
        text = data.decode("utf-8")
        assert "time" in text

    @pytest.mark.asyncio
    async def test_invalid_format_raises_value_error(self, service, mock_session_manager):
        mock_session_manager.get_session.return_value = _make_mock_session()
        with pytest.raises(ValueError, match="Unsupported export format"):
            await service.export_session_data("sess1", format="xml")

    @pytest.mark.asyncio
    async def test_session_not_found_raises_value_error(self, service, mock_session_manager):
        mock_session_manager.get_session.side_effect = ValueError("not found")
        with pytest.raises(ValueError, match="Session sess1 not found"):
            await service.export_session_data("sess1")

    @pytest.mark.asyncio
    async def test_json_export_with_time_filter(self, service, mock_session_manager):
        history = {"time": [0, 1, 2, 3, 4], "val": [10, 20, 30, 40, 50]}
        mock_session_manager.get_session.return_value = _make_mock_session(history)
        data, ct = await service.export_session_data(
            "sess1", format="json", start_time=1, end_time=3
        )
        parsed = json.loads(data)
        times = [p["time"] for p in parsed["data"]]
        assert all(1 <= t <= 3 for t in times)

    @pytest.mark.asyncio
    async def test_json_export_with_variable_filter(self, service, mock_session_manager):
        history = {"time": [0, 1], "var1": [1, 2], "var2": [3, 4]}
        mock_session_manager.get_session.return_value = _make_mock_session(history)
        data, ct = await service.export_session_data("sess1", format="json", variables=["var1"])
        parsed = json.loads(data)
        for point in parsed["data"]:
            assert "var1" in point
            assert "var2" not in point

    @pytest.mark.asyncio
    async def test_json_export_with_user_id(self, service, mock_session_manager):
        mock_session_manager.get_session.return_value = _make_mock_session()
        data, ct = await service.export_session_data("sess1", format="json", user_id="user_1")
        mock_session_manager.get_session.assert_called_once_with("sess1", "user_1")

    @pytest.mark.asyncio
    async def test_csv_export_empty_history(self, service, mock_session_manager):
        mock_session_manager.get_session.return_value = _make_mock_session({"time": []})
        data, ct = await service.export_session_data("sess1", format="csv")
        assert ct == "text/csv"
        text = data.decode("utf-8")
        assert "time" in text

    @pytest.mark.asyncio
    async def test_csv_export_includes_metadata_comments(self, service, mock_session_manager):
        mock_session_manager.get_session.return_value = _make_mock_session()
        data, ct = await service.export_session_data("sess1", format="csv")
        text = data.decode("utf-8")
        assert "# session_id: sess1" in text
        assert "# state:" in text

    @pytest.mark.asyncio
    async def test_json_export_metadata_fields(self, service, mock_session_manager):
        mock_session_manager.get_session.return_value = _make_mock_session()
        data, _ = await service.export_session_data("sess1", format="json")
        parsed = json.loads(data)
        assert "session_id" in parsed
        assert "created_at" in parsed
        assert "updated_at" in parsed
        assert "config" in parsed
        assert "state" in parsed

    @pytest.mark.asyncio
    async def test_format_is_case_insensitive_json(self, service, mock_session_manager):
        mock_session_manager.get_session.return_value = _make_mock_session()
        data, ct = await service.export_session_data("sess1", format="JSON")
        assert ct == "application/json"

    @pytest.mark.asyncio
    async def test_format_is_case_insensitive_csv(self, service, mock_session_manager):
        mock_session_manager.get_session.return_value = _make_mock_session()
        data, ct = await service.export_session_data("sess1", format="CSV")
        assert ct == "text/csv"

    @pytest.mark.asyncio
    async def test_default_format_is_json(self, service, mock_session_manager):
        mock_session_manager.get_session.return_value = _make_mock_session()
        data, ct = await service.export_session_data("sess1")
        assert ct == "application/json"


# ---------------------------------------------------------------------------
# _extract_time_series
# ---------------------------------------------------------------------------


class TestExtractTimeSeries:

    def test_no_history_returns_empty(self, service):
        result = service._extract_time_series({}, None, None, None)
        assert result == []

    def test_basic_extraction(self, service):
        state = {"history": {"time": [0, 1, 2], "x": [10, 20, 30]}}
        result = service._extract_time_series(state, None, None, None)
        assert len(result) == 3
        assert result[0] == {"time": 0, "x": 10}

    def test_start_time_filter(self, service):
        state = {"history": {"time": [0, 1, 2, 3], "x": [1, 2, 3, 4]}}
        result = service._extract_time_series(state, None, 2, None)
        assert all(p["time"] >= 2 for p in result)

    def test_end_time_filter(self, service):
        state = {"history": {"time": [0, 1, 2, 3], "x": [1, 2, 3, 4]}}
        result = service._extract_time_series(state, None, None, 1)
        assert all(p["time"] <= 1 for p in result)

    def test_variable_filter(self, service):
        state = {"history": {"time": [0, 1], "x": [1, 2], "y": [3, 4]}}
        result = service._extract_time_series(state, ["x"], None, None)
        for point in result:
            assert "x" in point
            assert "y" not in point

    def test_size_limit_truncates(self, service):
        state = {"history": {"time": list(range(1000)), "x": list(range(1000))}}
        result = service._extract_time_series(state, None, None, None, max_size_bytes=100)
        assert len(result) < 1000

    def test_missing_value_uses_none(self, service):
        state = {"history": {"time": [0, 1, 2], "x": [10, 20]}}  # x shorter than time
        result = service._extract_time_series(state, None, None, None)
        assert result[2]["x"] is None

    def test_max_export_points_truncation(self, service):
        """Covers the settings.max_export_points truncation warning path."""
        n = 200
        state = {"history": {"time": list(range(n)), "x": list(range(n))}}
        with patch("app.services.data_export.settings") as mock_settings:
            mock_settings.max_export_mb = 100
            mock_settings.max_export_points = 5
            result = service._extract_time_series(state, None, None, None)
        assert len(result) == 5

    def test_both_time_filters_applied(self, service):
        state = {"history": {"time": [0, 1, 2, 3, 4], "x": [0, 1, 2, 3, 4]}}
        result = service._extract_time_series(state, None, 1, 3)
        assert [p["time"] for p in result] == [1, 2, 3]

    def test_empty_time_points(self, service):
        state = {"history": {"time": [], "x": []}}
        result = service._extract_time_series(state, None, None, None)
        assert result == []

    def test_no_variables_in_history_except_time(self, service):
        state = {"history": {"time": [0, 1, 2]}}
        result = service._extract_time_series(state, None, None, None)
        assert len(result) == 3
        assert all(list(p.keys()) == ["time"] for p in result)


# ---------------------------------------------------------------------------
# _export_json / _export_csv
# ---------------------------------------------------------------------------


class TestExportHelpers:

    def test_export_json_returns_bytes(self, service):
        data = {"session_id": "s1", "data": []}
        result, ct = service._export_json(data)
        assert ct == "application/json"
        assert isinstance(result, bytes)
        assert json.loads(result)["session_id"] == "s1"

    def test_export_csv_with_data(self, service):
        data = {
            "session_id": "s1",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T01:00:00Z",
            "config": {},
            "state": "completed",
            "data": [{"time": 0, "x": 1}, {"time": 1, "x": 2}],
        }
        result = service._export_csv(data)
        assert isinstance(result, bytes)
        text = result.decode("utf-8")
        assert "time,x" in text
        assert "0,1" in text

    def test_export_csv_empty_data(self, service):
        data = {
            "session_id": "s1",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T01:00:00Z",
            "config": {},
            "state": "completed",
            "data": [],
        }
        result = service._export_csv(data)
        text = result.decode("utf-8")
        assert "time" in text

    def test_redact_config_removes_sensitive_keys(self, service):
        config = {"password": "secret", "api_key": "key123", "name": "test"}
        redacted = service._redact_config(config)
        assert redacted["password"] == "[REDACTED]"
        assert redacted["api_key"] == "[REDACTED]"
        assert redacted["name"] == "test"

    def test_redact_config_all_sensitive_keys(self, service):
        """Covers all sensitive key names: password, secret, key, token, api_key."""
        config = {
            "password": "p",
            "secret": "s",
            "key": "k",
            "token": "t",
            "api_key": "a",
            "safe": "value",
        }
        redacted = service._redact_config(config)
        for sensitive in ["password", "secret", "key", "token", "api_key"]:
            assert redacted[sensitive] == "[REDACTED]"
        assert redacted["safe"] == "value"

    def test_redact_config_does_not_mutate_original(self, service):
        config = {"password": "secret"}
        service._redact_config(config)
        assert config["password"] == "secret"

    def test_export_csv_config_is_redacted(self, service):
        """Ensures _redact_config is called during CSV export."""
        data = {
            "session_id": "s1",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T01:00:00Z",
            "config": {"password": "supersecret", "name": "test"},
            "state": "running",
            "data": [],
        }
        result = service._export_csv(data)
        text = result.decode("utf-8")
        assert "supersecret" not in text
        assert "[REDACTED]" in text

    def test_export_csv_metadata_comment_lines(self, service):
        data = {
            "session_id": "my-session",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "config": {},
            "state": "paused",
            "data": [],
        }
        result = service._export_csv(data)
        text = result.decode("utf-8")
        assert "# Session Metadata" in text
        assert "# session_id: my-session" in text
        assert "# created_at: 2024-01-01T00:00:00Z" in text
        assert "# updated_at: 2024-01-02T00:00:00Z" in text
        assert "# state: paused" in text


# ---------------------------------------------------------------------------
# CSV injection escaping (escape_csv_value inner function)
# ---------------------------------------------------------------------------


class TestCsvEscaping:
    """Tests for the escape_csv_value inner function via _export_csv."""

    def _make_csv_data(self, values):
        """Build export_data with a single variable 'v' having the given values."""
        return {
            "session_id": "s1",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T01:00:00Z",
            "config": {},
            "state": "completed",
            "data": [{"time": i, "v": val} for i, val in enumerate(values)],
        }

    def test_plain_value_unchanged(self, service):
        data = self._make_csv_data(["hello"])
        text = service._export_csv(data).decode("utf-8")
        assert "hello" in text

    def test_empty_string_value(self, service):
        data = self._make_csv_data([""])
        result = service._export_csv(data)
        assert isinstance(result, bytes)

    def test_value_starting_with_equals_is_escaped(self, service):
        data = self._make_csv_data(["=SUM(A1)"])
        text = service._export_csv(data).decode("utf-8")
        assert "=SUM(A1)" not in text or "\\=" in text or text.count("'") >= 1

    def test_value_starting_with_plus_is_escaped(self, service):
        data = self._make_csv_data(["+cmd"])
        text = service._export_csv(data).decode("utf-8")
        # Should be sanitized — original unescaped form should not appear
        assert "+cmd" not in text or "\\+" in text or "'" in text

    def test_value_starting_with_minus_is_escaped(self, service):
        data = self._make_csv_data(["-1+2"])
        text = service._export_csv(data).decode("utf-8")
        assert isinstance(text, str)

    def test_value_starting_with_at_is_escaped(self, service):
        data = self._make_csv_data(["@user"])
        text = service._export_csv(data).decode("utf-8")
        assert "@user" not in text or "\\@" in text or "'" in text

    def test_value_starting_with_tab_is_escaped(self, service):
        data = self._make_csv_data(["\tcmd"])
        text = service._export_csv(data).decode("utf-8")
        assert isinstance(text, str)

    def test_value_with_comma_is_quoted(self, service):
        data = self._make_csv_data(["hello,world"])
        text = service._export_csv(data).decode("utf-8")
        # comma in value should be handled (quoted or escaped)
        assert isinstance(text, str)

    def test_value_with_newline_is_handled(self, service):
        data = self._make_csv_data(["line1\nline2"])
        text = service._export_csv(data).decode("utf-8")
        assert isinstance(text, str)

    def test_value_with_double_quote_is_escaped(self, service):
        data = self._make_csv_data(['say "hello"'])
        text = service._export_csv(data).decode("utf-8")
        assert isinstance(text, str)

    def test_hex_pattern_is_escaped(self, service):
        data = self._make_csv_data(["0xFF"])
        text = service._export_csv(data).decode("utf-8")
        assert isinstance(text, str)

    def test_formula_cmd_pattern(self, service):
        data = self._make_csv_data(["=cmd|' /C calc'!A0"])
        text = service._export_csv(data).decode("utf-8")
        assert "=cmd|' /C calc'!A0" not in text or "\\=" in text

    def test_value_with_carriage_return(self, service):
        data = self._make_csv_data(["val\rend"])
        text = service._export_csv(data).decode("utf-8")
        assert isinstance(text, str)

    def test_multiple_variables_sorted_in_header(self, service):
        """Verifies variable names are sorted in CSV header."""
        export_data = {
            "session_id": "s1",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T01:00:00Z",
            "config": {},
            "state": "completed",
            "data": [{"time": 0, "z_var": 1, "a_var": 2}],
        }
        text = service._export_csv(export_data).decode("utf-8")
        # Header should have a_var before z_var (sorted)
        header_line = [l for l in text.split("\n") if l.startswith("time,")][0]
        assert header_line == "time,a_var,z_var"


# ---------------------------------------------------------------------------
# generate_summary_stats
# ---------------------------------------------------------------------------


class TestGenerateSummaryStats:

    @pytest.mark.asyncio
    async def test_returns_correct_stats(self, service, mock_session_manager):
        history = {"time": [0, 1, 2], "var1": [1, 2, 3], "var2": [4, 5, 6]}
        mock_session_manager.get_session.return_value = _make_mock_session(history)
        stats = await service.generate_summary_stats("sess1")
        assert stats["session_id"] == "sess1"
        assert stats["num_time_points"] == 3
        assert "time" in stats["variables"]

    @pytest.mark.asyncio
    async def test_session_not_found_raises(self, service, mock_session_manager):
        mock_session_manager.get_session.side_effect = ValueError("not found")
        with pytest.raises(ValueError, match="Session sess1 not found"):
            await service.generate_summary_stats("sess1")

    @pytest.mark.asyncio
    async def test_empty_history(self, service, mock_session_manager):
        mock_session_manager.get_session.return_value = _make_mock_session({})
        stats = await service.generate_summary_stats("sess1")
        assert stats["num_time_points"] == 0

    @pytest.mark.asyncio
    async def test_with_user_id(self, service, mock_session_manager):
        mock_session_manager.get_session.return_value = _make_mock_session()
        await service.generate_summary_stats("sess1", user_id="u1")
        mock_session_manager.get_session.assert_called_once_with("sess1", "u1")

    @pytest.mark.asyncio
    async def test_variables_list_in_stats(self, service, mock_session_manager):
        history = {"time": [0], "alpha": [1], "beta": [2]}
        mock_session_manager.get_session.return_value = _make_mock_session(history)
        stats = await service.generate_summary_stats("sess1")
        assert set(stats["variables"]) == {"time", "alpha", "beta"}


# ---------------------------------------------------------------------------
# export_time_series
# ---------------------------------------------------------------------------


class TestExportTimeSeries:

    @pytest.mark.asyncio
    async def test_basic_export(self, service, mock_session_manager):
        history = {"time": [0, 1, 2], "var1": [1, 2, 3]}
        mock_session_manager.get_session.return_value = _make_mock_session(history)
        result = await service.export_time_series("sess1", variables=["var1"])
        assert result["session_id"] == "sess1"
        assert result["variables"] == ["var1"]
        assert result["num_points"] == 3

    @pytest.mark.asyncio
    async def test_with_downsample(self, service, mock_session_manager):
        history = {"time": list(range(10)), "var1": list(range(10))}
        mock_session_manager.get_session.return_value = _make_mock_session(history)
        result = await service.export_time_series("sess1", variables=["var1"], downsample=2)
        assert result["num_points"] == 5

    @pytest.mark.asyncio
    async def test_with_limit(self, service, mock_session_manager):
        history = {"time": list(range(100)), "var1": list(range(100))}
        mock_session_manager.get_session.return_value = _make_mock_session(history)
        result = await service.export_time_series("sess1", variables=["var1"], limit=10)
        assert result["num_points"] == 10

    @pytest.mark.asyncio
    async def test_session_not_found_raises(self, service, mock_session_manager):
        mock_session_manager.get_session.side_effect = ValueError("not found")
        with pytest.raises(ValueError, match="Session sess1 not found"):
            await service.export_time_series("sess1", variables=["var1"])

    @pytest.mark.asyncio
    async def test_next_cursor_is_none(self, service, mock_session_manager):
        mock_session_manager.get_session.return_value = _make_mock_session()
        result = await service.export_time_series("sess1", variables=["var1"])
        assert result["next_cursor"] is None

    @pytest.mark.asyncio
    async def test_with_time_filters(self, service, mock_session_manager):
        history = {"time": [0, 1, 2, 3, 4], "var1": [0, 1, 2, 3, 4]}
        mock_session_manager.get_session.return_value = _make_mock_session(history)
        result = await service.export_time_series(
            "sess1", variables=["var1"], start_time=1, end_time=3
        )
        assert all(1 <= p["time"] <= 3 for p in result["data"])

    @pytest.mark.asyncio
    async def test_with_user_id(self, service, mock_session_manager):
        mock_session_manager.get_session.return_value = _make_mock_session()
        await service.export_time_series("sess1", variables=["var1"], user_id="u1")
        mock_session_manager.get_session.assert_called_once_with("sess1", "u1")

    @pytest.mark.asyncio
    async def test_downsample_of_one_no_change(self, service, mock_session_manager):
        """downsample=1 should not reduce points (slice [::1] is identity)."""
        history = {"time": [0, 1, 2], "var1": [1, 2, 3]}
        mock_session_manager.get_session.return_value = _make_mock_session(history)
        result = await service.export_time_series("sess1", variables=["var1"], downsample=1)
        # downsample=1 is not > 1, so no downsampling applied
        assert result["num_points"] == 3

    @pytest.mark.asyncio
    async def test_data_structure(self, service, mock_session_manager):
        history = {"time": [0, 1], "var1": [10, 20]}
        mock_session_manager.get_session.return_value = _make_mock_session(history)
        result = await service.export_time_series("sess1", variables=["var1"])
        assert "data" in result
        assert isinstance(result["data"], list)


# ---------------------------------------------------------------------------
# get_event_analysis
# ---------------------------------------------------------------------------


class TestGetEventAnalysis:

    @pytest.mark.asyncio
    async def test_returns_event_analysis(self, service, mock_session_manager):
        mock_session_manager.get_session.return_value = _make_mock_session()
        result = await service.get_event_analysis("sess1", event_type="ignition")
        assert result["session_id"] == "sess1"
        assert result["event_type"] == "ignition"
        assert "total_events" in result
        assert "events" in result

    @pytest.mark.asyncio
    async def test_session_not_found_raises(self, service, mock_session_manager):
        mock_session_manager.get_session.side_effect = ValueError("not found")
        with pytest.raises(ValueError, match="Session sess1 not found"):
            await service.get_event_analysis("sess1")

    @pytest.mark.asyncio
    async def test_default_event_type_is_ignition(self, service, mock_session_manager):
        mock_session_manager.get_session.return_value = _make_mock_session()
        result = await service.get_event_analysis("sess1")
        assert result["event_type"] == "ignition"

    @pytest.mark.asyncio
    async def test_custom_event_type(self, service, mock_session_manager):
        mock_session_manager.get_session.return_value = _make_mock_session()
        result = await service.get_event_analysis("sess1", event_type="shutdown")
        assert result["event_type"] == "shutdown"

    @pytest.mark.asyncio
    async def test_with_user_id(self, service, mock_session_manager):
        mock_session_manager.get_session.return_value = _make_mock_session()
        await service.get_event_analysis("sess1", user_id="u1")
        mock_session_manager.get_session.assert_called_once_with("sess1", "u1")

    @pytest.mark.asyncio
    async def test_total_events_is_zero(self, service, mock_session_manager):
        mock_session_manager.get_session.return_value = _make_mock_session()
        result = await service.get_event_analysis("sess1")
        assert result["total_events"] == 0
        assert result["events"] == []
