"""
Real-Time Discord Notifier
Formats and sends Discord messages for real-time Ekos session events.
"""
import logging
import time as time_module
from typing import Dict, Any, Optional

from utils import send_discord_message

logger = logging.getLogger(__name__)


class RealtimeDiscordNotifier:
    """Formats and sends Discord notifications for real-time events."""

    def __init__(self, config: Dict[str, Any]):
        self.webhook_url = config.get('webhook', '')
        self.observatory_name = config.get('realtime', {}).get('observatory_name', '')
        self.min_message_interval = config.get('realtime', {}).get('min_message_interval', 1.0)
        self._last_send_time = 0.0

        if not self.webhook_url:
            logger.warning("No webhook URL configured - notifications will be logged only")

    def _prefix(self) -> str:
        """Return the observatory prefix for messages."""
        if self.observatory_name:
            return f"**[{self.observatory_name}]** "
        return ""

    def _throttle(self):
        """Ensure minimum interval between Discord messages to avoid rate limiting."""
        now = time_module.time()
        elapsed = now - self._last_send_time
        if elapsed < self.min_message_interval:
            time_module.sleep(self.min_message_interval - elapsed)
        self._last_send_time = time_module.time()

    def send_raw(self, message: str):
        """Send a raw message to Discord."""
        if not self.webhook_url:
            logger.info(f"[DRY] {message}")
            return
        try:
            self._throttle()
            send_discord_message(self.webhook_url, message)
            logger.debug(f"Sent: {message[:80]}...")
        except Exception as e:
            logger.error(f"Failed to send Discord message: {e}")

    # --- Session Events ---

    def notify_session_start(self, start_time: str, timezone: str):
        """Notify that a new Ekos session has started."""
        msg = f"🌙 {self._prefix()}New Ekos session started\n"
        msg += f"🕐 {start_time} {timezone}"
        self.send_raw(msg)

    def notify_session_end(self, stats: Dict[str, Any]):
        """Notify session end with compact summary."""
        captures_ok = stats.get('captures_complete', 0)
        captures_fail = stats.get('captures_aborted', 0)
        af_ok = stats.get('autofocus_success', 0)
        af_fail = stats.get('autofocus_failed', 0)
        align_ok = stats.get('align_success', 0)
        align_fail = stats.get('align_failed', 0)
        jobs = stats.get('scheduler_jobs', [])

        msg = f"🌅 {self._prefix()}Session ended\n"

        if jobs:
            msg += f"🎯 Targets: {', '.join(jobs)}\n"

        msg += f"📸 Captures: {captures_ok} ✅"
        if captures_fail > 0:
            msg += f" / {captures_fail} ❌"
        msg += "\n"

        if af_ok > 0 or af_fail > 0:
            msg += f"🔭 Autofocus: {af_ok} ✅"
            if af_fail > 0:
                msg += f" / {af_fail} ❌"
            msg += "\n"

        if align_ok > 0 or align_fail > 0:
            msg += f"🎯 Plate solving: {align_ok} ✅"
            if align_fail > 0:
                msg += f" / {align_fail} ❌"
            msg += "\n"

        self.send_raw(msg)

    # --- Capture Events ---

    def notify_capture_complete(self, event: Dict[str, Any], capture_number: int):
        """Notify a successful capture."""
        obj = event.get('object_name', '')
        filt = event.get('filter', '?')
        exposure = event.get('exposure', 0)
        hfr = event.get('hfr', -1)
        num_stars = event.get('num_stars', 0)
        clock = event.get('clock_time', '')

        msg = f"📸 {self._prefix()}Capture #{capture_number} ✅"
        if obj:
            msg += f" — {obj}"
        msg += "\n"

        details = []
        details.append(f"Filter: **{filt}**")
        details.append(f"Exp: {exposure:.0f}s")
        if hfr > 0:
            details.append(f"HFR: {hfr:.2f}")
        if num_stars > 0:
            details.append(f"⭐ {num_stars}")
        details.append(f"🕐 {clock}")

        msg += " · ".join(details)
        self.send_raw(msg)

    def notify_capture_aborted(self, event: Dict[str, Any], abort_number: int):
        """Notify an aborted capture."""
        obj = event.get('object_name', '')
        filt = event.get('filter', '?')
        exposure = event.get('exposure', 0)
        clock = event.get('clock_time', '')

        msg = f"❌ {self._prefix()}Capture aborted"
        if obj:
            msg += f" — {obj}"
        msg += "\n"

        details = []
        if filt:
            details.append(f"Filter: **{filt}**")
        details.append(f"Exp: {exposure:.0f}s")
        details.append(f"🕐 {clock}")
        details.append(f"Total aborted: {abort_number}")

        msg += " · ".join(details)
        self.send_raw(msg)

    # --- Autofocus Events ---

    def notify_autofocus_complete(self, event: Dict[str, Any]):
        """Notify a successful autofocus."""
        filt = event.get('filter', '?')
        duration = event.get('duration', 0)
        position = event.get('position', '')
        r_squared = event.get('r_squared', '')
        temperature = event.get('temperature', 0)
        clock = event.get('clock_time', '')

        msg = f"🔭 {self._prefix()}Autofocus ✅\n"

        details = []
        if filt:
            details.append(f"Filter: **{filt}**")
        if position:
            details.append(f"Position: {position}")
        if r_squared:
            details.append(f"R²={r_squared}")
        details.append(f"Duration: {duration:.0f}s")
        if temperature:
            details.append(f"🌡️ {temperature:.1f}°C")
        details.append(f"🕐 {clock}")

        msg += " · ".join(details)
        self.send_raw(msg)

    def notify_autofocus_aborted(self, event: Dict[str, Any]):
        """Notify a failed autofocus."""
        filt = event.get('filter', '?')
        duration = event.get('duration', 0)
        clock = event.get('clock_time', '')

        msg = f"🔭 {self._prefix()}Autofocus ❌ FAILED\n"

        details = []
        if filt:
            details.append(f"Filter: **{filt}**")
        details.append(f"Duration: {duration:.0f}s")
        details.append(f"🕐 {clock}")

        msg += " · ".join(details)
        self.send_raw(msg)

    # --- Scheduler Events ---

    def notify_scheduler_job_start(self, event: Dict[str, Any]):
        """Notify scheduler job started."""
        job_name = event.get('job_name', 'Unknown')
        clock = event.get('clock_time', '')

        msg = f"📋 {self._prefix()}Job started: **{job_name}**"
        if clock:
            msg += f" · 🕐 {clock}"
        self.send_raw(msg)

    def notify_scheduler_job_end(self, event: Dict[str, Any]):
        """Notify scheduler job ended."""
        job_name = event.get('job_name', 'Unknown')
        reason = event.get('reason', '')
        clock = event.get('clock_time', '')

        msg = f"📋 {self._prefix()}Job ended: **{job_name}**\n"
        if reason:
            msg += f"💬 Reason: {reason}"
        if clock:
            msg += f" · 🕐 {clock}"
        self.send_raw(msg)

    # --- Guide Events ---

    def notify_guide_problem(self, event: Dict[str, Any]):
        """Notify a guiding problem."""
        subtype = event.get('subtype', '')
        message = event.get('message', '')
        clock = event.get('clock_time', '')

        if subtype == 'lost':
            emoji = "⚠️"
        elif subtype == 'frequent_reacquire':
            emoji = "⚠️"
        elif subtype == 'recovered':
            emoji = "✅"
        else:
            emoji = "🧭"

        msg = f"{emoji} {self._prefix()}Guiding: {message}"
        if clock:
            msg += f" · 🕐 {clock}"
        self.send_raw(msg)

    # --- Align Events ---

    def notify_align_complete(self, event: Dict[str, Any]):
        """Notify a successful plate solving / alignment."""
        duration = event.get('duration', 0)
        clock = event.get('clock_time', '')

        msg = f"🎯 {self._prefix()}Plate solving ✅ Alignment successful\n"
        details = []
        details.append(f"Duration: {duration:.0f}s")
        details.append(f"🕐 {clock}")
        msg += " · ".join(details)
        self.send_raw(msg)

    def notify_align_failed(self, event: Dict[str, Any]):
        """Notify a failed plate solving / alignment."""
        duration = event.get('duration', 0)
        state = event.get('state', 'Failed')
        clock = event.get('clock_time', '')

        msg = f"🎯 {self._prefix()}Plate solving ❌ Alignment FAILED ({state})\n"
        details = []
        details.append(f"Duration: {duration:.0f}s")
        details.append(f"🕐 {clock}")
        msg += " · ".join(details)
        self.send_raw(msg)

    # --- Mount Events ---

    def notify_mount_parking(self, event: Dict[str, Any]):
        """Notify mount parking status."""
        state = event.get('state', '')
        clock = event.get('clock_time', '')

        if state == 'Parking':
            msg = f"🔄 {self._prefix()}Mount parking..."
        else:
            msg = f"✅ {self._prefix()}Mount parked"

        if clock:
            msg += f" · 🕐 {clock}"
        self.send_raw(msg)

    # --- Meridian Flip ---

    def notify_meridian_flip(self, event: Dict[str, Any]):
        """Notify meridian flip status."""
        state = event.get('state', '')
        clock = event.get('clock_time', '')

        state_labels = {
            'MOUNT_FLIP_RUNNING': '🔄 Meridian flip in progress...',
            'MOUNT_FLIP_COMPLETED': '✅ Meridian flip completed',
            'MOUNT_FLIP_ERROR': '❌ Meridian flip ERROR',
        }

        label = state_labels.get(state, f"🔄 Meridian flip: {state}")
        msg = f"{label}"
        if self.observatory_name:
            msg = f"{self._prefix()}{label}"
        if clock:
            msg += f" · 🕐 {clock}"
        self.send_raw(msg)
