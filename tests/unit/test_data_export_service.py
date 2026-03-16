"""
Unit tests for data export service.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from app.services.data_export import DataExportService


class TestDataExportService:
    """Test data export service."""

    @pytest.fixture
    def mock_session_manager(self):
        """Mock session manager."""
        manager = Mock()
        manager.get_session = AsyncMock()
        return manager

    @pytest.fixture
    def service(self, mock_session_manager):
        """Create data export service instance."""
        return DataExportService(mock_session_manager)

    @pytest.mark.asyncio
    async def test_export_session_data_json(self, service):
        """Test successful JSON export."""
        mock_session = Mock()
        mock_session.created_at = Mock()
        mock_session.created_at.isoformat = Mock(return_value="2024-01-01T00:00:00")
        mock_session.updated_at = Mock()
        mock_session.updated_at.isoformat = Mock(return_value="2024-01-01T00:00:00")
        mock_session.config = {}
        mock_session.state = Mock()
        mock_session.state.value = "running"
        mock_session.get_state = AsyncMock(
            return_value={"history": {"time": [0, 1, 2], "var1": [1, 2, 3]}}
        )
        service.session_manager.get_session = AsyncMock(return_value=mock_session)

        data, content_type = await service.export_session_data("session123", format="json")

        assert content_type == "application/json"
        assert data is not None

    @pytest.mark.asyncio
    async def test_export_session_data_csv(self, service):
        """Test successful CSV export."""
        mock_session = Mock()
        mock_session.created_at = Mock()
        mock_session.created_at.isoformat = Mock(return_value="2024-01-01T00:00:00")
        mock_session.updated_at = Mock()
        mock_session.updated_at.isoformat = Mock(return_value="2024-01-01T00:00:00")
        mock_session.config = {}
        mock_session.state = Mock()
        mock_session.state.value = "running"
        mock_session.get_state = AsyncMock(
            return_value={"history": {"time": [0, 1, 2], "var1": [1, 2, 3]}}
        )
        service.session_manager.get_session = AsyncMock(return_value=mock_session)

        data, content_type = await service.export_session_data("session123", format="csv")

        assert content_type == "text/csv"
        assert data is not None

    @pytest.mark.asyncio
    async def test_export_session_data_invalid_format(self, service):
        """Test export with invalid format."""
        mock_session = Mock()
        mock_session.created_at = Mock()
        mock_session.created_at.isoformat = Mock(return_value="2024-01-01T00:00:00")
        mock_session.updated_at = Mock()
        mock_session.updated_at.isoformat = Mock(return_value="2024-01-01T00:00:00")
        mock_session.config = {}
        mock_session.state = Mock()
        mock_session.state.value = "running"
        mock_session.get_state = AsyncMock(return_value={"history": {"time": [0, 1, 2]}})
        service.session_manager.get_session = AsyncMock(return_value=mock_session)

        with pytest.raises(ValueError, match="Unsupported export format"):
            await service.export_session_data("session123", format="invalid")

    @pytest.mark.asyncio
    async def test_export_session_data_not_found(self, service):
        """Test export when session not found."""
        service.session_manager.get_session = AsyncMock(side_effect=ValueError("Session not found"))

        with pytest.raises(ValueError, match="Session session123 not found"):
            await service.export_session_data("session123")

    @pytest.mark.asyncio
    async def test_export_session_data_with_time_filter(self, service):
        """Test export with time filter."""
        mock_session = Mock()
        mock_session.created_at = Mock()
        mock_session.created_at.isoformat = Mock(return_value="2024-01-01T00:00:00")
        mock_session.updated_at = Mock()
        mock_session.updated_at.isoformat = Mock(return_value="2024-01-01T00:00:00")
        mock_session.config = {}
        mock_session.state = Mock()
        mock_session.state.value = "running"
        mock_session.get_state = AsyncMock(
            return_value={"history": {"time": [0, 1, 2, 3, 4], "var1": [1, 2, 3, 4, 5]}}
        )
        service.session_manager.get_session = AsyncMock(return_value=mock_session)

        data, content_type = await service.export_session_data(
            "session123", format="json", start_time=1, end_time=3
        )

        assert content_type == "application/json"

    @pytest.mark.asyncio
    async def test_export_session_data_with_variable_filter(self, service):
        """Test export with variable filter."""
        mock_session = Mock()
        mock_session.created_at = Mock()
        mock_session.created_at.isoformat = Mock(return_value="2024-01-01T00:00:00")
        mock_session.updated_at = Mock()
        mock_session.updated_at.isoformat = Mock(return_value="2024-01-01T00:00:00")
        mock_session.config = {}
        mock_session.state = Mock()
        mock_session.state.value = "running"
        mock_session.get_state = AsyncMock(
            return_value={"history": {"time": [0, 1, 2], "var1": [1, 2, 3], "var2": [4, 5, 6]}}
        )
        service.session_manager.get_session = AsyncMock(return_value=mock_session)

        data, content_type = await service.export_session_data(
            "session123", format="json", variables=["var1"]
        )

        assert content_type == "application/json"

    @pytest.mark.asyncio
    async def test_generate_summary_stats(self, service):
        """Test generating summary statistics."""
        mock_session = Mock()
        mock_session.get_state = AsyncMock(
            return_value={"history": {"time": [0, 1, 2], "var1": [1, 2, 3]}}
        )
        service.session_manager.get_session = AsyncMock(return_value=mock_session)

        stats = await service.generate_summary_stats("session123")

        assert stats["session_id"] == "session123"
        assert stats["num_time_points"] == 3
        assert "variables" in stats

    @pytest.mark.asyncio
    async def test_generate_summary_stats_not_found(self, service):
        """Test summary stats when session not found."""
        service.session_manager.get_session = AsyncMock(side_effect=ValueError("Session not found"))

        with pytest.raises(ValueError, match="Session session123 not found"):
            await service.generate_summary_stats("session123")

    @pytest.mark.asyncio
    async def test_export_time_series(self, service):
        """Test exporting time series data."""
        mock_session = Mock()
        mock_session.get_state = AsyncMock(
            return_value={"history": {"time": [0, 1, 2], "var1": [1, 2, 3]}}
        )
        service.session_manager.get_session = AsyncMock(return_value=mock_session)

        result = await service.export_time_series("session123", variables=["var1"])

        assert result["session_id"] == "session123"
        assert result["variables"] == ["var1"]
        assert "data" in result

    @pytest.mark.asyncio
    async def test_export_time_series_with_downsample(self, service):
        """Test exporting time series with downsampling."""
        mock_session = Mock()
        mock_session.get_state = AsyncMock(
            return_value={"history": {"time": [0, 1, 2, 3, 4], "var1": [1, 2, 3, 4, 5]}}
        )
        service.session_manager.get_session = AsyncMock(return_value=mock_session)

        result = await service.export_time_series("session123", variables=["var1"], downsample=2)

        assert result["num_points"] <= 3  # Downsampled

    @pytest.mark.asyncio
    async def test_export_time_series_with_limit(self, service):
        """Test exporting time series with limit."""
        mock_session = Mock()
        mock_session.get_state = AsyncMock(
            return_value={"history": {"time": list(range(100)), "var1": list(range(100))}}
        )
        service.session_manager.get_session = AsyncMock(return_value=mock_session)

        result = await service.export_time_series("session123", variables=["var1"], limit=10)

        assert result["num_points"] <= 10

    @pytest.mark.asyncio
    async def test_get_event_analysis(self, service):
        """Test getting event analysis."""
        mock_session = Mock()
        mock_session.get_state = AsyncMock(return_value={"history": {}})
        service.session_manager.get_session = AsyncMock(return_value=mock_session)

        result = await service.get_event_analysis("session123", event_type="ignition")

        assert result["session_id"] == "session123"
        assert result["event_type"] == "ignition"
        assert "total_events" in result

    @pytest.mark.asyncio
    async def test_get_event_analysis_not_found(self, service):
        """Test event analysis when session not found."""
        service.session_manager.get_session = AsyncMock(side_effect=ValueError("Session not found"))

        with pytest.raises(ValueError, match="Session session123 not found"):
            await service.get_event_analysis("session123")
