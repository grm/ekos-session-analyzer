"""
Ekos Real-Time Session Monitor
Watches the analyze directory for new .analyze files and tails them in real-time,
sending Discord notifications for key events as they happen.

Usage:
    python realtime_monitor.py -c config.yml
    python realtime_monitor.py -c config.yml -v  # verbose/debug mode
"""
import sys
import os
import time
import signal
import logging
import argparse
import glob
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path

from utils import load_config, setup_logging, send_discord_message
from realtime_parser import RealtimeAnalyzeParser
from realtime_notifier import RealtimeDiscordNotifier

logger = logging.getLogger(__name__)


class AnalyzeFileWatcher:
    """Watches a directory for .analyze files and tails the latest one."""

    def __init__(self, analyze_dir: str, poll_interval: float = 1.0):
        self.analyze_dir = os.path.expanduser(analyze_dir)
        self.poll_interval = poll_interval
        self.current_file: Optional[str] = None
        self.file_position: int = 0

    def find_latest_file(self) -> Optional[str]:
        """Find the most recently modified .analyze file."""
        pattern = os.path.join(self.analyze_dir, "*.analyze")
        files = glob.glob(pattern)
        if not files:
            return None
        return max(files, key=os.path.getmtime)

    def check_for_new_file(self) -> Optional[str]:
        """Check if a newer .analyze file exists."""
        latest = self.find_latest_file()
        if latest and latest != self.current_file:
            return latest
        return None

    def read_new_lines(self) -> List[str]:
        """Read new lines from the current file since last position."""
        if not self.current_file or not os.path.exists(self.current_file):
            return []

        try:
            with open(self.current_file, 'r') as f:
                f.seek(self.file_position)
                new_data = f.read()
                self.file_position = f.tell()

            if not new_data:
                return []

            lines = new_data.split('\n')
            return [line for line in lines if line.strip()]

        except Exception as e:
            logger.error(f"Error reading file {self.current_file}: {e}")
            return []

    def switch_to_file(self, filepath: str, from_beginning: bool = False):
        """Switch to watching a new file."""
        old_file = self.current_file
        self.current_file = filepath

        if from_beginning:
            self.file_position = 0
        else:
            try:
                self.file_position = os.path.getsize(filepath)
            except OSError:
                self.file_position = 0

        logger.info(f"Watching file: {filepath} (from_beginning={from_beginning})")
        return old_file


class RealtimeMonitor:
    """Main real-time monitoring daemon."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.analyze_dir = config.get('analyze_dir', '~/.local/share/kstars/analyze')
        self.poll_interval = config.get('realtime', {}).get('poll_interval', 2.0)
        self.session_timeout = config.get('realtime', {}).get('session_timeout_minutes', 30)
        self.observatory_name = config.get('realtime', {}).get('observatory_name', '')

        # Guide alert thresholds from config
        rt_config = config.get('realtime', {})
        guide_lost_threshold = rt_config.get('guide_lost_threshold_seconds', 30.0)
        reacquire_alert_count = rt_config.get('reacquire_alert_count', 5)
        reacquire_alert_window = rt_config.get('reacquire_alert_window_seconds', 300.0)

        self.watcher = AnalyzeFileWatcher(self.analyze_dir, self.poll_interval)
        self.parser = RealtimeAnalyzeParser(
            guide_lost_threshold=guide_lost_threshold,
            reacquire_alert_count=reacquire_alert_count,
            reacquire_alert_window=reacquire_alert_window,
        )
        self.notifier = RealtimeDiscordNotifier(config)

        self._running = False
        self._last_event_time: Optional[datetime] = None
        self._session_active = False
        self._session_stats: Dict[str, Any] = {}
        self._reset_session_stats()

    def _reset_session_stats(self):
        """Reset session statistics."""
        self._session_stats = {
            'captures_complete': 0,
            'captures_aborted': 0,
            'autofocus_success': 0,
            'autofocus_failed': 0,
            'scheduler_jobs': [],
            'session_start': None,
        }

    def _check_session_timeout(self):
        """Check if the current session has ended (no activity for N minutes)."""
        if not self._session_active or not self._last_event_time:
            return

        timeout = timedelta(minutes=self.session_timeout)
        if datetime.now() - self._last_event_time > timeout:
            self._end_session()

    def _start_session(self, start_time_str: str, timezone: str):
        """Notify that a new session has started."""
        self._session_active = True
        self._reset_session_stats()
        self._session_stats['session_start'] = start_time_str
        self._last_event_time = datetime.now()

        self.notifier.notify_session_start(start_time_str, timezone)
        logger.info(f"Session started: {start_time_str} {timezone}")

    def _end_session(self):
        """Notify that a session has ended with a compact summary."""
        if not self._session_active:
            return

        self._session_active = False
        self.notifier.notify_session_end(self._session_stats)
        logger.info(f"Session ended. Stats: {self._session_stats}")
        self._reset_session_stats()

    def _process_events(self, events: List[Dict[str, Any]]):
        """Process parsed events and send notifications."""
        for event in events:
            event_type = event.get('type', '')
            self._last_event_time = datetime.now()

            if event_type == 'session_start':
                self._start_session(event.get('start_time', ''), event.get('timezone', ''))

            elif event_type == 'capture_complete':
                self._session_stats['captures_complete'] += 1
                self.notifier.notify_capture_complete(event, self._session_stats['captures_complete'])

            elif event_type == 'capture_aborted':
                self._session_stats['captures_aborted'] += 1
                self.notifier.notify_capture_aborted(event, self._session_stats['captures_aborted'])

            elif event_type == 'autofocus_complete':
                self._session_stats['autofocus_success'] += 1
                self.notifier.notify_autofocus_complete(event)

            elif event_type == 'autofocus_aborted':
                self._session_stats['autofocus_failed'] += 1
                self.notifier.notify_autofocus_aborted(event)

            elif event_type == 'scheduler_job_start':
                job_name = event.get('job_name', 'Unknown')
                if job_name not in self._session_stats['scheduler_jobs']:
                    self._session_stats['scheduler_jobs'].append(job_name)
                self.notifier.notify_scheduler_job_start(event)

            elif event_type == 'scheduler_job_end':
                self.notifier.notify_scheduler_job_end(event)

            elif event_type == 'guide_problem':
                self.notifier.notify_guide_problem(event)

            elif event_type == 'align_complete':
                self._session_stats['align_success'] = self._session_stats.get('align_success', 0) + 1
                self.notifier.notify_align_complete(event)

            elif event_type == 'align_failed':
                self._session_stats['align_failed'] = self._session_stats.get('align_failed', 0) + 1
                self.notifier.notify_align_failed(event)

            elif event_type == 'meridian_flip':
                self.notifier.notify_meridian_flip(event)

    def run(self):
        """Main monitoring loop."""
        self._running = True
        logger.info(f"Starting real-time monitor for: {self.analyze_dir}")
        logger.info(f"Poll interval: {self.poll_interval}s, Session timeout: {self.session_timeout}min")

        if self.observatory_name:
            logger.info(f"Observatory: {self.observatory_name}")

        # Initial file detection
        latest = self.watcher.find_latest_file()
        if latest:
            self.watcher.switch_to_file(latest, from_beginning=False)
            logger.info(f"Attached to existing file: {latest}")
        else:
            logger.info("No .analyze files found yet. Waiting...")

        # Send startup notification
        startup_msg = "🟢 Moniteur temps réel démarré"
        if self.observatory_name:
            startup_msg = f"🟢 **[{self.observatory_name}]** Moniteur temps réel démarré"
        startup_msg += f"\n📁 Surveillance: `{self.analyze_dir}`"

        try:
            self.notifier.send_raw(startup_msg)
        except Exception as e:
            logger.error(f"Failed to send startup message: {e}")

        # Main loop
        while self._running:
            try:
                # Check for newer file
                new_file = self.watcher.check_for_new_file()
                if new_file:
                    logger.info(f"New analyze file detected: {new_file}")
                    if self._session_active:
                        self._end_session()
                    self.watcher.switch_to_file(new_file, from_beginning=True)
                    self.parser.reset()

                # Read and process new lines
                new_lines = self.watcher.read_new_lines()
                if new_lines:
                    events = self.parser.process_lines(new_lines)
                    if events:
                        self._process_events(events)

                # Check session timeout
                self._check_session_timeout()

                time.sleep(self.poll_interval)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
                time.sleep(5)

        # Clean shutdown
        if self._session_active:
            self._end_session()

        shutdown_msg = "🔴 Moniteur temps réel arrêté"
        if self.observatory_name:
            shutdown_msg = f"🔴 **[{self.observatory_name}]** Moniteur temps réel arrêté"

        try:
            self.notifier.send_raw(shutdown_msg)
        except Exception:
            pass

        logger.info("Monitor stopped.")

    def stop(self):
        """Signal the monitor to stop."""
        self._running = False


def main():
    parser = argparse.ArgumentParser(
        description="Ekos Real-Time Session Monitor - sends Discord notifications for live session events"
    )
    parser.add_argument("-c", "--config", required=True, help="Path to config YAML file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose (debug) output")
    args = parser.parse_args()

    config = load_config(args.config)
    if not config:
        print("❌ Failed to load config.")
        sys.exit(1)

    log_level = config.get("log_level", "INFO")
    if args.verbose:
        log_level = "DEBUG"
    setup_logging(verbose=(log_level == "DEBUG"))

    webhook = config.get('webhook', '')
    if not webhook:
        print("❌ No webhook URL configured in config file.")
        sys.exit(1)

    monitor = RealtimeMonitor(config)

    # Handle graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        monitor.stop()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    print(f"🔭 Starting Ekos Real-Time Monitor...")
    print(f"📁 Watching: {os.path.expanduser(config.get('analyze_dir', ''))}")
    observatory = config.get('realtime', {}).get('observatory_name', '')
    if observatory:
        print(f"🏠 Observatory: {observatory}")
    print("Press Ctrl+C to stop.\n")

    monitor.run()


if __name__ == "__main__":
    main()
