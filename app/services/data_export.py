"""
Data Export Service

Handles exporting simulation session data in various formats (JSON, CSV).
"""

import json
import logging
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime

from app.services.session_manager import SessionManager

logger = logging.getLogger(__name__)


class DataExportService:
    """
    Service for exporting simulation session data.

    Provides methods to export session data in JSON and CSV formats
    with optional filtering and metadata inclusion.
    """

    def __init__(self, session_manager: SessionManager):
        """
        Initialize data export service.

        Args:
            session_manager: SessionManager instance for accessing session data
        """
        self.session_manager = session_manager
        logger.info("DataExportService initialized")

    async def export_session_data(
        self,
        session_id: str,
        format: str = "json",
        variables: Optional[List[str]] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> Tuple[bytes, str]:
        """
        Export session data in the specified format.

        Args:
            session_id: Session identifier
            format: Export format ('json' or 'csv')
            variables: Optional list of variables to include
            start_time: Optional start time filter (milliseconds)
            end_time: Optional end time filter (milliseconds)

        Returns:
            Tuple of (data_bytes, content_type)

        Raises:
            ValueError: If session not found or format invalid
        """
        # Get session
        try:
            session = await self.session_manager.get_session(session_id)
        except ValueError as e:
            raise ValueError(f"Session {session_id} not found") from e

        # Get session state
        state = await session.get_state()

        # Build export data with metadata
        export_data = {
            "session_id": session_id,
            "created_at": session.created_at.isoformat() + "Z",
            "updated_at": session.updated_at.isoformat() + "Z",
            "config": session.config,
            "state": session.state.value,
            "data": self._extract_time_series(state, variables, start_time, end_time),
        }

        # Export in requested format
        if format.lower() == "json":
            return self._export_json(export_data)
        elif format.lower() == "csv":
            return self._export_csv(export_data)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def _extract_time_series(
        self,
        state: Dict[str, Any],
        variables: Optional[List[str]],
        start_time: Optional[float],
        end_time: Optional[float],
    ) -> List[Dict[str, Any]]:
        """
        Extract time series data from session state.

        Args:
            state: Session state dictionary
            variables: Optional list of variables to include
            start_time: Optional start time filter
            end_time: Optional end time filter

        Returns:
            List of time series data points
        """
        # Extract history from state
        history = state.get("history", {})

        # Build time series data
        time_series = []

        # Get time points
        time_points = history.get("time", [])

        for i, t in enumerate(time_points):
            # Apply time filter
            if start_time is not None and t < start_time:
                continue
            if end_time is not None and t > end_time:
                continue

            # Build data point
            data_point = {"time": t}

            # Add variables
            for var_name, var_values in history.items():
                if var_name == "time":
                    continue

                # Apply variable filter
                if variables is not None and var_name not in variables:
                    continue

                # Add value if available
                if i < len(var_values):
                    data_point[var_name] = var_values[i]

            time_series.append(data_point)

        return time_series

    def _export_json(self, export_data: Dict[str, Any]) -> Tuple[bytes, str]:
        """
        Export data as JSON.

        Args:
            export_data: Data to export

        Returns:
            Tuple of (json_bytes, content_type)
        """
        json_str = json.dumps(export_data, indent=2)
        return (json_str.encode("utf-8"), "application/json")

    def _export_csv(self, export_data: Dict[str, Any]) -> Tuple[bytes, str]:
        """
        Export data as CSV with metadata in comments.

        Args:
            export_data: Data to export

        Returns:
            Tuple of (csv_bytes, content_type)
        """
        lines = []

        # Add metadata as comments
        lines.append("# Session Metadata")
        lines.append(f"# session_id: {export_data['session_id']}")
        lines.append(f"# created_at: {export_data['created_at']}")
        lines.append(f"# updated_at: {export_data['updated_at']}")
        lines.append(f"# config: {json.dumps(export_data['config'])}")
        lines.append(f"# state: {export_data['state']}")
        lines.append("")

        # Get time series data
        time_series = export_data.get("data", [])

        if time_series:
            # Get all variable names
            var_names = set()
            for point in time_series:
                var_names.update(point.keys())
            var_names.discard("time")
            var_names = sorted(var_names)

            # Write header
            header = "time," + ",".join(var_names)
            lines.append(header)

            # Write data rows
            for point in time_series:
                time_val = point.get("time", "")
                values = [str(point.get(var, "")) for var in var_names]
                row = f"{time_val}," + ",".join(values)
                lines.append(row)
        else:
            # Empty data
            lines.append("time")

        csv_str = "\n".join(lines) + "\n"
        return (csv_str.encode("utf-8"), "text/csv")

    async def generate_summary_stats(self, session_id: str) -> Dict[str, Any]:
        """
        Generate summary statistics for a session.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary with summary statistics

        Raises:
            ValueError: If session not found
        """
        # Get session
        try:
            session = await self.session_manager.get_session(session_id)
        except ValueError as e:
            raise ValueError(f"Session {session_id} not found") from e

        # Get session state
        state = await session.get_state()

        # Extract history
        history = state.get("history", {})

        # Compute basic statistics
        stats = {
            "session_id": session_id,
            "num_time_points": len(history.get("time", [])),
            "variables": list(history.keys()),
        }

        return stats

    async def export_time_series(
        self,
        session_id: str,
        variables: List[str],
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        downsample: Optional[int] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Export time series data with pagination.

        Args:
            session_id: Session identifier
            variables: List of variables to include
            start_time: Optional start time filter
            end_time: Optional end time filter
            downsample: Optional downsampling factor
            limit: Maximum number of data points
            cursor: Pagination cursor

        Returns:
            Dictionary with time series data and pagination info

        Raises:
            ValueError: If session not found
        """
        # Get session
        try:
            session = await self.session_manager.get_session(session_id)
        except ValueError as e:
            raise ValueError(f"Session {session_id} not found") from e

        # Get session state
        state = await session.get_state()

        # Extract time series
        time_series = self._extract_time_series(state, variables, start_time, end_time)

        # Apply downsampling
        if downsample and downsample > 1:
            time_series = time_series[::downsample]

        # Apply limit
        if limit:
            time_series = time_series[:limit]

        return {
            "session_id": session_id,
            "variables": variables,
            "num_points": len(time_series),
            "data": time_series,
            "next_cursor": None,  # Simplified - no pagination in this implementation
        }

    async def get_event_analysis(
        self, session_id: str, event_type: str = "ignition"
    ) -> Dict[str, Any]:
        """
        Get event analysis for a session.

        Args:
            session_id: Session identifier
            event_type: Type of event to analyze

        Returns:
            Dictionary with event analysis

        Raises:
            ValueError: If session not found
        """
        # Get session
        try:
            session = await self.session_manager.get_session(session_id)
        except ValueError as e:
            raise ValueError(f"Session {session_id} not found") from e

        # Get session state
        state = await session.get_state()

        # Simplified event analysis
        return {"session_id": session_id, "event_type": event_type, "total_events": 0, "events": []}
