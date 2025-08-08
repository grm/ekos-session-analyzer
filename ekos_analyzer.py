"""
Ekos/KStars Analyze File Parser
Parses .analyze files from KStars/Ekos for session analysis
"""
import os
import re
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any
import glob

class EkosAnalyzer:
    def __init__(self, analyze_dir: str = None):
        # Default path if not specified
        if analyze_dir is None:
            analyze_dir = os.path.expanduser("~/.local/share/kstars/analyze")
        self.analyze_dir = analyze_dir
        
    def find_analyze_files(self, hours: int = 24) -> List[str]:
        """Find .analyze files within the specified time window."""
        if not os.path.exists(self.analyze_dir):
            logging.warning(f"Analyze directory not found: {self.analyze_dir}")
            return []
            
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=hours)
        
        analyze_files = []
        pattern = os.path.join(self.analyze_dir, "*.analyze")
        
        for filepath in glob.glob(pattern):
            try:
                # Extract timestamp from filename: ekos-2025-02-28T23-22-19.analyze
                filename = os.path.basename(filepath)
                match = re.match(r'ekos-(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})\.analyze', filename)
                if match:
                    timestamp_str = match.group(1)
                    # Replace only time part dashes with colons, keep date dashes intact
                    # Split by 'T' to separate date and time parts
                    date_part, time_part = timestamp_str.split('T')
                    time_part = time_part.replace('-', ':')  # Only fix time format
                    timestamp_str = f"{date_part} {time_part}"
                    file_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    
                    if file_time >= cutoff:
                        analyze_files.append(filepath)
                        logging.debug(f"Found analyze file: {filepath} ({file_time})")
                        
            except Exception as e:
                logging.debug(f"Error parsing filename {filepath}: {e}")
                continue
                
        return sorted(analyze_files)
    
    def parse_analyze_file(self, filepath: str) -> Dict[str, Any]:
        """Parse a single .analyze file and extract session data."""
        session_data = {
            'filepath': filepath,
            'session_start': None,
            'kstars_version': None,
            'captures': [],
            'autofocus_sessions': [],
            'temperature_readings': [],
            'mount_coords': [],
            'mount_states': [],
            'guide_stats': [],
            'guide_states': [],
            'align_states': [],
            'scheduler_jobs': [],
            'issues': []
        }
        
        try:
            with open(filepath, 'r') as f:
                lines = f.readlines()
                
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    # Handle header line
                    if line.startswith('#KStars version'):
                        match = re.search(r'version ([\d.]+)', line)
                        if match:
                            session_data['kstars_version'] = match.group(1)
                    continue
                    
                parts = line.split(',')
                if len(parts) < 2:
                    continue
                    
                event_type = parts[0]
                
                # Parse different event types
                if event_type == 'AnalyzeStartTime':
                    if len(parts) >= 2:
                        # Format: AnalyzeStartTime,datetime_str,timezone
                        # parts[1] contains the actual datetime
                        datetime_str = parts[1]
                        # Remove microseconds if present for parsing
                        if '.' in datetime_str:
                            datetime_str = datetime_str.split('.')[0]
                        session_data['session_start'] = datetime_str
                        continue  # Skip timestamp parsing for this line
                
                # Parse timestamp for other events
                try:
                    timestamp = float(parts[1])
                except ValueError:
                    logging.debug(f"Could not parse timestamp: {parts[1]}")
                    continue
                        
                if event_type == 'Temperature':
                    if len(parts) >= 3:
                        temp = float(parts[2])
                        session_data['temperature_readings'].append({
                            'timestamp': timestamp,
                            'temperature': temp
                        })
                        
                elif event_type == 'MountState':
                    if len(parts) >= 3:
                        state = parts[2]
                        session_data['mount_states'].append({
                            'timestamp': timestamp,
                            'state': state
                        })
                        
                elif event_type == 'MountCoords':
                    if len(parts) >= 8:
                        session_data['mount_coords'].append({
                            'timestamp': timestamp,
                            'ra': float(parts[2]),
                            'dec': float(parts[3]),
                            'az': float(parts[4]),
                            'alt': float(parts[5])
                        })
                        
                elif event_type == 'CaptureStarting':
                    if len(parts) >= 4:
                        session_data['captures'].append({
                            'timestamp': timestamp,
                            'event': 'starting',
                            'exposure': float(parts[2]),
                            'filter': parts[3] if len(parts) > 3 else 'Unknown'
                        })
                        
                elif event_type == 'CaptureComplete':
                    if len(parts) >= 6:
                        capture_data = {
                            'timestamp': timestamp,
                            'event': 'complete',
                            'exposure': float(parts[2]),
                            'filter': parts[3],
                            'hfr': float(parts[4]) if parts[4] != '-1.000' else None,
                            'stars': int(parts[6]) if len(parts) > 6 and parts[6] != '-1' else None
                        }
                        session_data['captures'].append(capture_data)
                        
                elif event_type == 'CaptureAborted':
                    session_data['issues'].append({
                        'timestamp': timestamp,
                        'type': 'capture_aborted',
                        'exposure': float(parts[2]) if len(parts) > 2 else None
                    })
                    
                elif event_type == 'AutofocusStarting':
                    if len(parts) >= 5:
                        session_data['autofocus_sessions'].append({
                            'timestamp': timestamp,
                            'event': 'starting',
                            'filter': parts[2],
                            'temperature': float(parts[3]),
                            'step': int(parts[4])
                        })
                        
                elif event_type == 'AutofocusComplete':
                    if len(parts) >= 6:
                        # Parse autofocus result
                        af_data = {
                            'timestamp': timestamp,
                            'event': 'complete',
                            'temperature': float(parts[2]),
                            'step': int(parts[3]),
                            'filter': parts[5],
                            'solution': parts[-1] if len(parts) > 6 else None
                        }
                        
                        # Extract HFR from solution string if available
                        if af_data['solution']:
                            hfr_match = re.search(r'Solution: (\d+)', af_data['solution'])
                            if hfr_match:
                                af_data['focus_position'] = int(hfr_match.group(1))
                                
                        session_data['autofocus_sessions'].append(af_data)
                
                elif event_type == 'GuideStats':
                    # GuideStats,timestamp,dx,dy,pulse_ra,pulse_dec,distance,rms,snr
                    if len(parts) >= 7:
                        guide_data = {
                            'timestamp': timestamp,
                            'dx': float(parts[2]),  # Guide error in RA (arcsec)
                            'dy': float(parts[3]),  # Guide error in DEC (arcsec)
                            'pulse_ra': int(parts[4]),   # RA correction pulse (ms)
                            'pulse_dec': int(parts[5]),  # DEC correction pulse (ms)
                            'distance': float(parts[6]), # Total distance error
                            'rms': float(parts[7]) if len(parts) > 7 else 0.0,  # RMS error
                            'snr': float(parts[8]) if len(parts) > 8 else 0.0   # Signal-to-noise ratio
                        }
                        session_data['guide_stats'].append(guide_data)
                
                elif event_type == 'GuideState':
                    if len(parts) >= 3:
                        session_data['guide_states'].append({
                            'timestamp': timestamp,
                            'state': parts[2]
                        })
                
                elif event_type == 'AlignState':
                    if len(parts) >= 3:
                        session_data['align_states'].append({
                            'timestamp': timestamp,
                            'state': parts[2]
                        })
                
                elif event_type == 'SchedulerJobStart':
                    if len(parts) >= 3:
                        session_data['scheduler_jobs'].append({
                            'timestamp': timestamp,
                            'event': 'start',
                            'object_name': parts[2]
                        })
                
                elif event_type == 'SchedulerJobEnd':
                    if len(parts) >= 3:
                        session_data['scheduler_jobs'].append({
                            'timestamp': timestamp,
                            'event': 'end',
                            'object_name': parts[2] if len(parts) > 2 else 'Unknown'
                        })
                        
        except Exception as e:
            logging.error(f"Error parsing analyze file {filepath}: {e}")
            
        return session_data
    
    def aggregate_session_data(self, session_files: List[str]) -> Dict[str, Any]:
        """Aggregate data from multiple session files."""
        all_sessions = []
        
        for filepath in session_files:
            session_data = self.parse_analyze_file(filepath)
            if session_data['captures'] or session_data['autofocus_sessions']:
                all_sessions.append(session_data)
                
        if not all_sessions:
            return {}
            
        # Combine all sessions
        aggregated = {
            'sessions': all_sessions,
            'total_captures': 0,
            'capture_summary': defaultdict(list),
            'temperature_stats': {},
            'autofocus_stats': {},
            'guide_stats': {},
            'alignment_stats': {},
            'target_objects': [],
            'session_duration': None,
            'issues_summary': []
        }
        
        all_captures = []
        all_temperatures = []
        all_autofocus = []
        all_guide_stats = []
        all_guide_states = []
        all_align_states = []
        all_scheduler_jobs = []
        all_issues = []
        
        earliest_start = None
        latest_end = None
        
        for session in all_sessions:
            # Collect captures
            completed_captures = [c for c in session['captures'] if c['event'] == 'complete']
            all_captures.extend(completed_captures)
            
            # Group by object/filter - don't filter out captures without HFR/stars
            for capture in completed_captures:
                # Try to extract object name from THIS session's scheduler jobs first, then fallback
                obj_name = self._get_object_name_from_scheduler(session['scheduler_jobs']) or self._extract_object_name(session['filepath'])
                key = (obj_name, capture['filter'])
                aggregated['capture_summary'][key].append(capture)
            
            # Collect temperature data
            all_temperatures.extend(session['temperature_readings'])
            
            # Collect autofocus data
            all_autofocus.extend([af for af in session['autofocus_sessions'] if af['event'] == 'complete'])
            
            # Collect guide data
            all_guide_stats.extend(session['guide_stats'])
            all_guide_states.extend(session['guide_states'])
            
            # Collect alignment data
            all_align_states.extend(session['align_states'])
            
            # Collect scheduler/target data
            all_scheduler_jobs.extend(session['scheduler_jobs'])
            
            # Collect issues
            all_issues.extend(session['issues'])
            
            # Track session timing
            logging.debug(f"Processing session timing for {session['filepath']}")
            logging.debug(f"Session start: {session['session_start']}")
            logging.debug(f"Captures count: {len(session['captures'])}")
            
            if session['session_start']:
                try:
                    # Try different datetime formats
                    start_time = None
                    datetime_str = session['session_start']
                    
                    # Try with microseconds first
                    try:
                        start_time = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S.%f')
                        logging.debug(f"Parsed start time with microseconds: {start_time}")
                    except ValueError:
                        # Try without microseconds
                        try:
                            start_time = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
                            logging.debug(f"Parsed start time without microseconds: {start_time}")
                        except ValueError:
                            logging.debug(f"Could not parse datetime: {datetime_str}")
                            # Don't continue, just skip this session's timing
                            start_time = None
                    
                    if start_time:
                        if not earliest_start or start_time < earliest_start:
                            earliest_start = start_time
                            logging.debug(f"Updated earliest start: {earliest_start}")
                            
                        # Estimate end time from last event
                        if session['captures']:
                            last_capture_time = max(c['timestamp'] for c in session['captures'])
                            end_time = start_time + timedelta(seconds=last_capture_time)
                            if not latest_end or end_time > latest_end:
                                latest_end = end_time
                                logging.debug(f"Updated latest end: {latest_end}")
                except Exception as e:
                    logging.debug(f"Error parsing session timing: {e}")
                    pass
        
        aggregated['total_captures'] = len(all_captures)
        
        # Calculate temperature stats
        if all_temperatures:
            temps = [t['temperature'] for t in all_temperatures]
            aggregated['temperature_stats'] = {
                'min': min(temps),
                'max': max(temps),
                'avg': sum(temps) / len(temps),
                'readings_count': len(temps)
            }
        
        # Calculate autofocus stats
        if all_autofocus:
            # Filter out invalid temperatures (Ekos default values)
            valid_temps = [af['temperature'] for af in all_autofocus if af['temperature'] > -999999]
            aggregated['autofocus_stats'] = {
                'sessions_count': len(all_autofocus),
                'avg_temperature': sum(valid_temps) / len(valid_temps) if valid_temps else None
            }
        
        # Calculate guide stats - CRUCIAL for astrophotography
        if all_guide_stats:
            # Calculate distance from dx,dy (more reliable than pre-calculated distance field)
            calculated_distances = []
            for g in all_guide_stats:
                dx = g.get('dx', 0)
                dy = g.get('dy', 0)
                distance = (dx**2 + dy**2)**0.5
                calculated_distances.append(distance)
            
            # Filter outliers (guide corrections > 10 arcsec are usually spurious)
            filtered_distances = [d for d in calculated_distances if d <= 10.0]
            rms_values = [g['rms'] for g in all_guide_stats if g.get('rms', 0) > 0]
            dx_values = [abs(g['dx']) for g in all_guide_stats]
            dy_values = [abs(g['dy']) for g in all_guide_stats]
            
            aggregated['guide_stats'] = {
                'total_measurements': len(all_guide_stats),
                'avg_distance': sum(filtered_distances) / len(filtered_distances) if filtered_distances else 0,
                'max_distance': max(filtered_distances) if filtered_distances else 0,
                'avg_rms': sum(rms_values) / len(rms_values) if rms_values else 0,
                'avg_ra_error': sum(dx_values) / len(dx_values) if dx_values else 0,
                'avg_dec_error': sum(dy_values) / len(dy_values) if dy_values else 0,
                'guide_quality': self._calculate_guide_quality_from_distance(filtered_distances)
            }
        
        # Calculate alignment stats
        if all_align_states:
            successful_aligns = len([a for a in all_align_states if a['state'] == 'Successful'])
            total_align_attempts = len([a for a in all_align_states if a['state'] in ['Successful', 'Failed']])
            
            aggregated['alignment_stats'] = {
                'total_attempts': total_align_attempts,
                'successful': successful_aligns,
                'success_rate': successful_aligns / max(total_align_attempts, 1),
                'states': list(set(a['state'] for a in all_align_states))
            }
        
        # Extract target objects from scheduler jobs
        if all_scheduler_jobs:
            targets = set()
            for job in all_scheduler_jobs:
                if job.get('object_name'):
                    targets.add(job['object_name'])
            aggregated['target_objects'] = list(targets)
        
        # Calculate session duration - fallback to timestamps if no parsed datetime
        if earliest_start and latest_end:
            duration = latest_end - earliest_start
            aggregated['session_duration'] = {
                'start': earliest_start,
                'end': latest_end,
                'duration_hours': duration.total_seconds() / 3600
            }
        elif all_captures:
            # Fallback: estimate duration from capture timestamps
            timestamps = [c['timestamp'] for c in all_captures]
            if timestamps:
                min_ts = min(timestamps)
                max_ts = max(timestamps)
                duration_seconds = max_ts - min_ts
                duration_hours = duration_seconds / 3600
                
                # Create approximate start/end times
                now = datetime.utcnow()
                approx_start = now - timedelta(seconds=max_ts)
                approx_end = now - timedelta(seconds=min_ts)
                
                aggregated['session_duration'] = {
                    'start': approx_start,
                    'end': approx_end,
                    'duration_hours': duration_hours
                }
                logging.debug(f"Estimated session duration from timestamps: {duration_hours:.2f} hours")
        
        # Summarize issues
        aggregated['issues_summary'] = all_issues
        
        return aggregated
    
    def _calculate_guide_quality_from_distance(self, distances: List[float]) -> str:
        """Calculate guide quality rating from real distance calculations."""
        if not distances:
            return "Unknown"
        
        avg_distance = sum(distances) / len(distances)
        
        # Quality thresholds in arcseconds (for real calculated distances)
        if avg_distance < 1.0:
            return "Excellent"
        elif avg_distance < 2.0:
            return "Good"
        elif avg_distance < 3.0:
            return "Average"
        else:
            return "Poor"
    
    def _calculate_guide_quality(self, guide_stats: List[Dict]) -> str:
        """Calculate guide quality rating from guide statistics."""
        if not guide_stats:
            return "Unknown"
        
        # Calculate average distance error (arcsec)
        distances = [g['distance'] for g in guide_stats if g['distance'] > 0]
        if not distances:
            return "No Data"
        
        avg_distance = sum(distances) / len(distances)
        
        # Quality thresholds in arcseconds
        if avg_distance < 1.0:
            return "Excellent"
        elif avg_distance < 2.0:
            return "Good"
        elif avg_distance < 3.0:
            return "Average"
        else:
            return "Poor"
    
    def _get_object_name_from_scheduler(self, scheduler_jobs: List[Dict]) -> str:
        """Extract object name from scheduler job data."""
        if not scheduler_jobs:
            return None
            
        # Find the most recent scheduler job start
        started_jobs = [job for job in scheduler_jobs if job['event'] == 'start']
        if started_jobs:
            # Get the latest started job
            latest_job = max(started_jobs, key=lambda x: x['timestamp'])
            return latest_job.get('object_name', 'Unknown')
        
        return None
    
    def _extract_object_name(self, filepath: str) -> str:
        """Extract object name from filepath or return generic name."""
        # For now, return a generic name based on time
        # In a real implementation, you might correlate with capture logs
        filename = os.path.basename(filepath)
        match = re.match(r'ekos-(\d{4}-\d{2}-\d{2})', filename)
        if match:
            return f"Session_{match.group(1)}"
        return "Unknown"
    
    def analyze_folder(self, hours: int = 24) -> Dict[str, Any]:
        """Main analysis function - equivalent to the original analyze_folder."""
        analyze_files = self.find_analyze_files(hours)
        
        if not analyze_files:
            logging.info("No Ekos analyze files found in time window")
            return {}
            
        logging.info(f"Found {len(analyze_files)} Ekos analyze files")
        return self.aggregate_session_data(analyze_files)
