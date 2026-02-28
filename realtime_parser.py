"""
Real-Time Analyze File Parser
Parses individual lines from .analyze files and emits structured events.
Maintains state to detect guide problems and correlate events.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Time format used in .analyze files
TIME_FORMAT = "yyyy-MM-dd hh:mm:ss.zzz"


class RealtimeAnalyzeParser:
    """
    Stateful parser for .analyze file lines.
    Processes lines incrementally and emits high-level events.
    """

    def __init__(self, guide_lost_threshold: float = 30.0, reacquire_alert_count: int = 5,
                 reacquire_alert_window: float = 300.0):
        """
        Args:
            guide_lost_threshold: Seconds of non-guiding before alerting
            reacquire_alert_count: Number of reacquiring events in window to trigger alert
            reacquire_alert_window: Time window (seconds) for reacquiring detection
        """
        self.guide_lost_threshold = guide_lost_threshold
        self.reacquire_alert_count = reacquire_alert_count
        self.reacquire_alert_window = reacquire_alert_window

        self.reset()

    def reset(self):
        """Reset all parser state."""
        self.session_start_time: Optional[str] = None
        self.session_timezone: str = ""

        # Capture state
        self._capture_started_time: Optional[float] = None
        self._capture_started_filter: str = ""
        self._capture_started_exposure: float = 0.0

        # Autofocus state
        self._af_started_time: Optional[float] = None
        self._af_started_filter: str = ""
        self._af_started_temp: float = 0.0

        # Guide state
        self._last_guide_state: str = ""
        self._last_guide_state_time: float = 0.0
        self._guiding_active: bool = False
        self._guide_lost_time: Optional[float] = None
        self._guide_lost_alerted: bool = False
        self._reacquire_times: List[float] = []
        self._reacquire_alerted_at: float = 0.0

        # Align state
        self._align_in_progress: bool = False
        self._align_started_time: Optional[float] = None

        # Mount state
        self._mount_parking: bool = False

        # Scheduler state
        self._current_job: str = ""

        # For clock time computation
        self._session_start_dt: Optional[datetime] = None

    def _to_clock_time(self, offset_seconds: float) -> str:
        """Convert offset seconds to clock time string."""
        if self._session_start_dt:
            dt = self._session_start_dt + timedelta(seconds=offset_seconds)
            return dt.strftime("%H:%M:%S")
        return f"{offset_seconds:.0f}s"

    def _parse_session_start_time(self, time_str: str) -> Optional[datetime]:
        """Parse the AnalyzeStartTime datetime string."""
        formats = [
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(time_str, fmt)
            except ValueError:
                continue
        return None

    def process_lines(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Process multiple lines and return a list of events."""
        events = []
        for line in lines:
            line_events = self._process_line(line)
            events.extend(line_events)
        return events

    def _process_line(self, line: str) -> List[Dict[str, Any]]:
        """Process a single line and return events (0 or more)."""
        line = line.strip()
        if not line or line.startswith('#'):
            return []

        parts = line.split(',')
        if len(parts) < 2:
            return []

        command = parts[0]

        # AnalyzeStartTime is special - no numeric timestamp
        if command == "AnalyzeStartTime" and len(parts) >= 3:
            return self._handle_session_start(parts[1].strip(), parts[2].strip())

        # All other commands have a numeric time offset as second field
        try:
            time_offset = float(parts[1])
        except (ValueError, IndexError):
            return []

        events = []

        if command == "CaptureStarting" and len(parts) >= 4:
            events.extend(self._handle_capture_starting(time_offset, parts))
        elif command == "CaptureComplete" and len(parts) >= 6:
            events.extend(self._handle_capture_complete(time_offset, parts))
        elif command == "CaptureAborted" and len(parts) >= 3:
            events.extend(self._handle_capture_aborted(time_offset, parts))
        elif command == "AutofocusStarting" and len(parts) >= 4:
            events.extend(self._handle_af_starting(time_offset, parts))
        elif command == "AutofocusComplete" and len(parts) >= 4:
            events.extend(self._handle_af_complete(time_offset, parts))
        elif command == "AutofocusAborted" and len(parts) >= 4:
            events.extend(self._handle_af_aborted(time_offset, parts))
        elif command == "GuideState" and len(parts) >= 3:
            events.extend(self._handle_guide_state(time_offset, parts[2].strip()))
        elif command == "MountState" and len(parts) >= 3:
            events.extend(self._handle_mount_state(time_offset, parts[2].strip()))
        elif command == "SchedulerJobStart" and len(parts) >= 3:
            events.extend(self._handle_scheduler_start(time_offset, parts[2].strip()))
        elif command == "SchedulerJobEnd" and len(parts) >= 4:
            reason = parts[3].strip() if len(parts) > 3 else ""
            events.extend(self._handle_scheduler_end(time_offset, parts[2].strip(), reason))
        elif command == "AlignState" and len(parts) >= 3:
            events.extend(self._handle_align_state(time_offset, parts[2].strip()))
        elif command == "MeridianFlipState" and len(parts) >= 3:
            events.extend(self._handle_meridian_flip(time_offset, parts[2].strip()))

        return events

    # --- Session ---

    def _handle_session_start(self, time_str: str, timezone: str) -> List[Dict[str, Any]]:
        self.session_start_time = time_str
        self.session_timezone = timezone
        self._session_start_dt = self._parse_session_start_time(time_str)
        return [{
            'type': 'session_start',
            'start_time': time_str,
            'timezone': timezone,
        }]

    # --- Captures ---

    def _handle_capture_starting(self, time: float, parts: List[str]) -> List[Dict[str, Any]]:
        try:
            self._capture_started_time = time
            self._capture_started_exposure = float(parts[2])
            self._capture_started_filter = parts[3].strip() if len(parts) > 3 else ""
        except (ValueError, IndexError):
            pass
        return []

    def _handle_capture_complete(self, time: float, parts: List[str]) -> List[Dict[str, Any]]:
        try:
            exposure = float(parts[2])
            filter_name = parts[3].strip()
            hfr = float(parts[4])
            filename = parts[5].strip() if len(parts) > 5 else ""
            num_stars = int(parts[6]) if len(parts) > 6 else 0
            median = int(parts[7]) if len(parts) > 7 else 0
            eccentricity = float(parts[8]) if len(parts) > 8 else 0.0

            duration = time - self._capture_started_time if self._capture_started_time else exposure

            # Extract object name from filename
            object_name = self._extract_object_from_filename(filename)

            self._capture_started_time = None
            return [{
                'type': 'capture_complete',
                'time': time,
                'clock_time': self._to_clock_time(time),
                'exposure': exposure,
                'filter': filter_name,
                'hfr': hfr,
                'filename': filename,
                'num_stars': num_stars,
                'median': median,
                'eccentricity': eccentricity,
                'duration': duration,
                'object_name': object_name or self._current_job,
            }]
        except (ValueError, IndexError) as e:
            logger.debug(f"Error parsing CaptureComplete: {e}")
            return []

    def _handle_capture_aborted(self, time: float, parts: List[str]) -> List[Dict[str, Any]]:
        try:
            exposure = float(parts[2])
            self._capture_started_time = None
            return [{
                'type': 'capture_aborted',
                'time': time,
                'clock_time': self._to_clock_time(time),
                'exposure': exposure,
                'filter': self._capture_started_filter,
                'object_name': self._current_job,
            }]
        except (ValueError, IndexError):
            return []

    # --- Autofocus ---

    def _handle_af_starting(self, time: float, parts: List[str]) -> List[Dict[str, Any]]:
        try:
            self._af_started_time = time
            self._af_started_filter = parts[2].strip()
            self._af_started_temp = float(parts[3])
        except (ValueError, IndexError):
            pass
        return []

    def _handle_af_complete(self, time: float, parts: List[str]) -> List[Dict[str, Any]]:
        if self._af_started_time is None:
            return []

        duration = time - self._af_started_time
        filter_name = self._af_started_filter

        # Try to extract solution info from the last field (title)
        solution_info = ""
        r_squared = ""
        position = ""

        # The title field is typically the last comma-separated value
        # e.g.: "L1P [S]: Hyperbola (W) Solution: 10579  R²=0.98"
        full_line = ','.join(parts)
        if "Solution:" in full_line:
            try:
                sol_part = full_line.split("Solution:")[-1].strip()
                # Extract position (number after "Solution:")
                pos_str = sol_part.split()[0]
                position = pos_str
                # Extract R²
                if "R²=" in sol_part or "R²=" in sol_part:
                    r2_part = sol_part.split("R²=")[-1] if "R²=" in sol_part else sol_part.split("R²=")[-1]
                    r_squared = r2_part.strip()
                solution_info = sol_part.strip()
            except (IndexError, ValueError):
                pass

        # Extract temperature from V2 format
        try:
            temperature = float(parts[2])
        except (ValueError, IndexError):
            temperature = self._af_started_temp

        self._af_started_time = None
        return [{
            'type': 'autofocus_complete',
            'time': time,
            'clock_time': self._to_clock_time(time),
            'filter': filter_name,
            'temperature': temperature,
            'duration': duration,
            'position': position,
            'r_squared': r_squared,
            'solution_info': solution_info,
        }]

    def _handle_af_aborted(self, time: float, parts: List[str]) -> List[Dict[str, Any]]:
        duration = time - self._af_started_time if self._af_started_time else 0
        filter_name = self._af_started_filter

        self._af_started_time = None
        return [{
            'type': 'autofocus_aborted',
            'time': time,
            'clock_time': self._to_clock_time(time),
            'filter': filter_name,
            'duration': duration,
        }]

    # --- Guide State ---

    def _handle_guide_state(self, time: float, state: str) -> List[Dict[str, Any]]:
        events = []
        prev_state = self._last_guide_state

        self._last_guide_state = state
        self._last_guide_state_time = time

        # Track guiding active state
        if state == "Guiding":
            # Guide recovered
            if self._guide_lost_time is not None and self._guide_lost_alerted:
                lost_duration = time - self._guide_lost_time
                events.append({
                    'type': 'guide_problem',
                    'subtype': 'recovered',
                    'time': time,
                    'clock_time': self._to_clock_time(time),
                    'duration': lost_duration,
                    'message': f"Guide recovered after {lost_duration:.0f}s",
                })

            self._guiding_active = True
            self._guide_lost_time = None
            self._guide_lost_alerted = False

        elif state == "Reacquiring":
            self._reacquire_times.append(time)
            # Clean old reacquire events outside window
            cutoff = time - self.reacquire_alert_window
            self._reacquire_times = [t for t in self._reacquire_times if t > cutoff]

            # Check for frequent reacquiring
            if (len(self._reacquire_times) >= self.reacquire_alert_count and
                    time - self._reacquire_alerted_at > self.reacquire_alert_window):
                self._reacquire_alerted_at = time
                events.append({
                    'type': 'guide_problem',
                    'subtype': 'frequent_reacquire',
                    'time': time,
                    'clock_time': self._to_clock_time(time),
                    'count': len(self._reacquire_times),
                    'window': self.reacquire_alert_window,
                    'message': f"{len(self._reacquire_times)} reacquiring events in {self.reacquire_alert_window:.0f}s",
                })

        elif state in ("Aborted", "Idle"):
            if self._guiding_active and self._guide_lost_time is None:
                # Guide just lost
                self._guide_lost_time = time
                self._guiding_active = False

            # Check if guide has been lost too long
            if (self._guide_lost_time is not None and
                    not self._guide_lost_alerted and
                    time - self._guide_lost_time >= self.guide_lost_threshold):
                self._guide_lost_alerted = True
                lost_duration = time - self._guide_lost_time
                events.append({
                    'type': 'guide_problem',
                    'subtype': 'lost',
                    'time': time,
                    'clock_time': self._to_clock_time(time),
                    'duration': lost_duration,
                    'message': f"Guide lost for {lost_duration:.0f}s",
                })

        elif state == "Dithering":
            pass  # Normal during capture sequence

        elif state in ("Calibrating", "Looping", "Selecting star"):
            pass  # Normal startup states

        return events

    # --- Mount State ---

    def _handle_mount_state(self, time: float, state: str) -> List[Dict[str, Any]]:
        events = []

        if state == "Parking":
            if not self._mount_parking:
                self._mount_parking = True
                events.append({
                    'type': 'mount_parking',
                    'time': time,
                    'clock_time': self._to_clock_time(time),
                    'state': 'Parking',
                })

        elif state in ("Parked", "Idle"):
            if self._mount_parking:
                self._mount_parking = False
                if state == "Parked":
                    events.append({
                        'type': 'mount_parking',
                        'time': time,
                        'clock_time': self._to_clock_time(time),
                        'state': 'Parked',
                    })

        else:
            # Reset parking flag on any other state (Slewing, Tracking, etc.)
            self._mount_parking = False

        return events

    # --- Scheduler ---

    def _handle_scheduler_start(self, time: float, job_name: str) -> List[Dict[str, Any]]:
        self._current_job = job_name
        return [{
            'type': 'scheduler_job_start',
            'time': time,
            'clock_time': self._to_clock_time(time),
            'job_name': job_name,
        }]

    def _handle_scheduler_end(self, time: float, job_name: str, reason: str) -> List[Dict[str, Any]]:
        self._current_job = ""
        return [{
            'type': 'scheduler_job_end',
            'time': time,
            'clock_time': self._to_clock_time(time),
            'job_name': job_name,
            'reason': reason,
        }]

    # --- Align State ---

    def _handle_align_state(self, time: float, state: str) -> List[Dict[str, Any]]:
        events = []

        if state == "In Progress":
            if not self._align_in_progress:
                self._align_in_progress = True
                self._align_started_time = time

        elif state == "Complete":
            if self._align_in_progress:
                duration = time - self._align_started_time if self._align_started_time else 0
                self._align_in_progress = False
                self._align_started_time = None
                events.append({
                    'type': 'align_complete',
                    'time': time,
                    'clock_time': self._to_clock_time(time),
                    'duration': duration,
                })

        elif state in ("Failed", "Aborted"):
            if self._align_in_progress:
                duration = time - self._align_started_time if self._align_started_time else 0
                self._align_in_progress = False
                self._align_started_time = None
                events.append({
                    'type': 'align_failed',
                    'time': time,
                    'clock_time': self._to_clock_time(time),
                    'duration': duration,
                    'state': state,
                })

        return events

    # --- Meridian Flip ---

    def _handle_meridian_flip(self, time: float, state: str) -> List[Dict[str, Any]]:
        # Only notify on significant states
        if state in ("MOUNT_FLIP_RUNNING", "MOUNT_FLIP_COMPLETED", "MOUNT_FLIP_ERROR"):
            return [{
                'type': 'meridian_flip',
                'time': time,
                'clock_time': self._to_clock_time(time),
                'state': state,
            }]
        return []

    # --- Utilities ---

    @staticmethod
    def _extract_object_from_filename(filename: str) -> str:
        """Extract object name from a capture filename path.
        Example: /home/grm/Pictures/IC_434/Light/S/2026-02-27T00-02-21_IC_434_Light_600_secs_S.fits
        """
        if not filename:
            return ""

        try:
            # Try to extract from the directory structure (Pictures/<object>/Light/...)
            parts = filename.replace('\\', '/').split('/')
            for i, part in enumerate(parts):
                if part == "Pictures" and i + 1 < len(parts):
                    return parts[i + 1].replace('_', ' ')

            # Fallback: try to extract from filename itself
            basename = parts[-1] if parts else filename
            # Pattern: date_OBJECT_Light_...
            name_parts = basename.split('_')
            if len(name_parts) > 2:
                # Skip the date part, find the object name before "Light"
                obj_parts = []
                found_date = False
                for p in name_parts:
                    if not found_date and (p.startswith('20') or p.startswith('19')):
                        found_date = True
                        continue
                    if found_date and p == "Light":
                        break
                    if found_date:
                        obj_parts.append(p)
                if obj_parts:
                    return ' '.join(obj_parts)
        except Exception:
            pass

        return ""
