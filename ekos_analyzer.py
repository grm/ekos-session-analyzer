"""
Enhanced Ekos/KStars Analyze File Parser
Parses .analyze files from KStars/Ekos for session analysis with improved HFR, FWHM and guide data calculation
"""
import os
import re
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any
import glob
import math

class EkosAnalyzer:
    def __init__(self, analyze_dir: str = None, pixel_scale_arcsec: float = None, guide_quality_thresholds: Dict = None):
        # Default path if not specified
        if analyze_dir is None:
            analyze_dir = "~/.local/share/kstars/analyze"
        # Always expand user home directory (handles ~ in paths)
        self.analyze_dir = os.path.expanduser(analyze_dir)
        self.pixel_scale_arcsec = pixel_scale_arcsec
        
        # Default pixel-based quality thresholds (backwards compatible)
        self.guide_quality_thresholds = guide_quality_thresholds or {
            'excellent_px': 0.5,
            'good_px': 1.0, 
            'average_px': 1.5
        }
        
        # Log setup information if pixel scale is provided
        if self.pixel_scale_arcsec:
            logging.info(f"Pixel scale configured: {self.pixel_scale_arcsec:.2f}\"/pixel")
            logging.info(f"Guide quality thresholds: Excellent < {self.guide_quality_thresholds['excellent_px']:.1f}px, "
                        f"Good < {self.guide_quality_thresholds['good_px']:.1f}px, "
                        f"Average < {self.guide_quality_thresholds['average_px']:.1f}px")
        
    def find_analyze_files(self, hours: int = 24) -> List[str]:
        """Find .analyze files within the specified time window based on actual session start times."""
        if not os.path.exists(self.analyze_dir):
            logging.warning(f"Analyze directory not found: {self.analyze_dir}")
            return []
            
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=hours)
        
        analyze_files = []
        pattern = os.path.join(self.analyze_dir, "*.analyze")
        
        for filepath in glob.glob(pattern):
            try:
                # First, try to get the actual session start time from inside the file
                session_start_time = self._get_session_start_from_file(filepath)
                
                if session_start_time:
                    # Use the actual session start time for filtering
                    if session_start_time >= cutoff:
                        analyze_files.append(filepath)
                        logging.debug(f"Found analyze file with session at {session_start_time}: {filepath}")
                else:
                    # Fallback to filename timestamp if we can't parse session start
                    filename = os.path.basename(filepath)
                    match = re.match(r'ekos-(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})\.analyze', filename)
                    if match:
                        timestamp_str = match.group(1)
                        # Replace only time part dashes with colons, keep date dashes intact
                        date_part, time_part = timestamp_str.split('T')
                        time_part = time_part.replace('-', ':')  # Only fix time format
                        timestamp_str = f"{date_part} {time_part}"
                        file_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                        
                        if file_time >= cutoff:
                            analyze_files.append(filepath)
                            logging.debug(f"Found analyze file (fallback to filename timestamp): {filepath} ({file_time})")
                        
            except Exception as e:
                logging.debug(f"Error parsing file {filepath}: {e}")
                continue
                
        return sorted(analyze_files)
    
    def _get_session_start_from_file(self, filepath: str) -> Optional[datetime]:
        """Extract the actual session start time from inside an analyze file."""
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('AnalyzeStartTime,'):
                        parts = line.split(',')
                        if len(parts) >= 2:
                            datetime_str = parts[1]
                            # Remove microseconds if present for parsing
                            if '.' in datetime_str:
                                datetime_str = datetime_str.split('.')[0]
                            
                            # Try parsing with different formats
                            try:
                                return datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                try:
                                    return datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M:%S')
                                except ValueError:
                                    logging.debug(f"Could not parse session start time: {datetime_str}")
                                    return None
        except Exception as e:
            logging.debug(f"Error reading file {filepath}: {e}")
            return None
        
        return None
    
    def parse_analyze_file(self, filepath: str) -> Dict[str, Any]:
        """Parse a single .analyze file and extract session data with enhanced HFR/FWHM extraction."""
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
                        # Parse HFR directly from capture (field 5)
                        hfr_value = None
                        try:
                            hfr_candidate = float(parts[4])  # HFR is at index 4
                            if hfr_candidate > 0:  # Valid HFR
                                hfr_value = hfr_candidate
                        except (ValueError, IndexError):
                            pass
                        
                        # Parse stars count - at index 7 based on actual Ekos format
                        stars_value = None
                        if len(parts) > 7:
                            try:
                                stars_candidate = int(parts[7])
                                if stars_candidate > 0:  # Valid star count
                                    stars_value = stars_candidate
                            except (ValueError, IndexError):
                                pass
                        
                        capture_data = {
                            'timestamp': timestamp,
                            'event': 'complete',
                            'exposure': float(parts[2]),
                            'filter': parts[3],
                            'hfr': hfr_value,  # Use actual HFR from capture
                            'fwhm': self._calculate_fwhm_from_hfr(hfr_value) if hfr_value else None,
                            'stars': stars_value,
                            'filepath': parts[5] if len(parts) > 5 else None
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
                        # The HFR data is actually in parts[6], not the last part
                        # Format: AutofocusComplete,timestamp,temp,step,reason,filter,HFR_DATA,other_sections...
                        hfr_data_section = parts[6] if len(parts) > 6 else None
                        
                        # Parse autofocus result with enhanced HFR extraction
                        af_data = {
                            'timestamp': timestamp,
                            'event': 'complete',
                            'temperature': float(parts[2]),
                            'step': int(parts[3]),
                            'filter': parts[5],
                            'solution': parts[-1] if len(parts) > 6 else None,
                            'hfr_data_raw': hfr_data_section,  # Raw HFR data section
                            'hfr_values': [],  # Will store all HFR measurements
                            'best_hfr': None,  # Best HFR from the autofocus run
                            'focus_position': None
                        }
                        
                        # Enhanced HFR extraction from HFR data section
                        if hfr_data_section and '|' in hfr_data_section:
                            af_data = self._extract_hfr_from_data_section(af_data, hfr_data_section)
                        
                        # Also try to extract from solution string as fallback
                        if not af_data.get('best_hfr') and af_data['solution']:
                            af_data = self._extract_hfr_from_autofocus(af_data)
                                
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
    
    def _extract_hfr_from_autofocus(self, af_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhanced HFR extraction from autofocus solution string."""
        solution_str = af_data['solution']
        
        if not solution_str:
            return af_data
        
        # Extract focus position from solution
        focus_match = re.search(r'Solution: (\d+)', solution_str)
        if focus_match:
            af_data['focus_position'] = int(focus_match.group(1))
        
        # Parse the detailed autofocus data from the actual file format
        # Example: 22218|1.708|1.708|0|22198|1.820|1.820|0|22178|2.002|2.002|1|...
        if '|' in solution_str:
            # The HFR data is in the 6th field (index 5) of the comma-separated parts
            # Format: AutofocusComplete,timestamp,temp,step,reason,filter,HFR_DATA,other_data...
            parts = solution_str.split(',')
            
            # Look for the part that contains the HFR measurements (should be early in the string)
            hfr_section = None
            for i, part in enumerate(parts):
                if '|' in part and len(part.split('|')) >= 12:  # Should have many measurements (at least 3 groups of 4)
                    # Check if this looks like HFR data (contains numbers in the right format)
                    test_parts = part.split('|')
                    try:
                        # Test if first few elements can be parsed as position|hfr|hfr|outlier
                        int(test_parts[0])  # position
                        float(test_parts[1])  # hfr
                        float(test_parts[2])  # hfr (duplicate)
                        int(test_parts[3])   # outlier flag
                        hfr_section = part
                        logging.debug(f"Found HFR section at index {i}: {part[:100]}...")
                        break
                    except (ValueError, IndexError):
                        continue
            
            if hfr_section:
                measurements = hfr_section.split('|')
                logging.debug(f"Processing {len(measurements)} measurement values")
                
                # Parse measurements in groups of 4: position, hfr, hfr_weight, outlier
                for i in range(0, len(measurements) - 3, 4):
                    try:
                        position = int(measurements[i])
                        hfr = float(measurements[i + 1])
                        hfr_weight = float(measurements[i + 2])
                        outlier = int(measurements[i + 3])
                        
                        # Only include valid HFR measurements (not outliers, reasonable range)
                        if outlier == 0 and 0.5 <= hfr <= 20.0:
                            af_data['hfr_values'].append({
                                'position': position,
                                'hfr': hfr,
                                'weight': hfr_weight
                            })
                            logging.debug(f"Added HFR measurement: pos={position}, hfr={hfr:.3f}, outlier={outlier}")
                    except (ValueError, IndexError) as e:
                        logging.debug(f"Error parsing measurement at index {i}: {e}")
                        continue
        
        # Find the best HFR (minimum value from valid measurements)
        if af_data['hfr_values']:
            best_measurement = min(af_data['hfr_values'], key=lambda x: x['hfr'])
            af_data['best_hfr'] = best_measurement['hfr']
            
            # If we have a focus position, try to find the HFR at that position
            if af_data['focus_position']:
                for measurement in af_data['hfr_values']:
                    if measurement['position'] == af_data['focus_position']:
                        af_data['best_hfr'] = measurement['hfr']
                        logging.debug(f"Using HFR at solution position {af_data['focus_position']}: {af_data['best_hfr']:.3f}")
                        break
            
            logging.debug(f"Extracted {len(af_data['hfr_values'])} HFR measurements, best: {af_data['best_hfr']:.3f}")
        else:
            logging.debug(f"No valid HFR measurements found in autofocus data")
        
        return af_data
    
    def _extract_hfr_from_data_section(self, af_data: Dict[str, Any], hfr_data_section: str) -> Dict[str, Any]:
        """Extract HFR values directly from the HFR data section."""
        if not hfr_data_section or '|' not in hfr_data_section:
            return af_data
        
        # Extract focus position from solution string if available
        if af_data.get('solution'):
            focus_match = re.search(r'Solution: (\d+)', af_data['solution'])
            if focus_match:
                af_data['focus_position'] = int(focus_match.group(1))
        
        measurements = hfr_data_section.split('|')
        logging.debug(f"Processing HFR data section with {len(measurements)} values")
        
        # Parse measurements in groups of 4: position, hfr, hfr_weight, outlier
        for i in range(0, len(measurements) - 3, 4):
            try:
                position = int(measurements[i])
                hfr = float(measurements[i + 1])
                hfr_weight = float(measurements[i + 2])
                outlier = int(measurements[i + 3])
                
                # Only include valid HFR measurements (not outliers, reasonable range)
                if outlier == 0 and 0.5 <= hfr <= 20.0:
                    af_data['hfr_values'].append({
                        'position': position,
                        'hfr': hfr,
                        'weight': hfr_weight
                    })
                    logging.debug(f"Added HFR measurement: pos={position}, hfr={hfr:.3f}, outlier={outlier}")
            except (ValueError, IndexError) as e:
                logging.debug(f"Error parsing HFR measurement at index {i}: {e}")
                continue
        
        # Find the best HFR (minimum value from valid measurements)
        if af_data['hfr_values']:
            best_measurement = min(af_data['hfr_values'], key=lambda x: x['hfr'])
            af_data['best_hfr'] = best_measurement['hfr']
            
            # If we have a focus position, try to find the HFR at that position
            if af_data['focus_position']:
                for measurement in af_data['hfr_values']:
                    if measurement['position'] == af_data['focus_position']:
                        af_data['best_hfr'] = measurement['hfr']
                        logging.debug(f"Using HFR at solution position {af_data['focus_position']}: {af_data['best_hfr']:.3f}")
                        break
            
            logging.debug(f"Extracted {len(af_data['hfr_values'])} HFR measurements from data section, best: {af_data['best_hfr']:.3f}")
        else:
            logging.debug(f"No valid HFR measurements found in data section")
        
        return af_data
    
    def _calculate_fwhm_from_hfr(self, hfr: float) -> float:
        """Calculate FWHM from HFR using the standard conversion factor."""
        if hfr is None or hfr <= 0:
            return None
        # FWHM ≈ HFR × 1.2 (approximate conversion factor)
        return hfr * 1.2
    
    def _associate_autofocus_with_captures(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhanced association of autofocus HFR values with subsequent captures."""
        if not session_data.get('autofocus_sessions') or not session_data.get('captures'):
            return session_data
        
        # Get completed autofocus sessions sorted by timestamp
        completed_autofocus = [af for af in session_data['autofocus_sessions'] if af['event'] == 'complete']
        completed_autofocus.sort(key=lambda x: x['timestamp'])
        
        # Get completed captures sorted by timestamp
        completed_captures = [c for c in session_data['captures'] if c['event'] == 'complete']
        completed_captures.sort(key=lambda x: x['timestamp'])
        
        # For each autofocus session, only fill in missing HFR data (don't overwrite existing)
        for af in completed_autofocus:
            if not af.get('best_hfr'):
                continue
                
            filter_name = af.get('filter', 'Unknown')
            af_timestamp = af['timestamp']
            best_hfr = af['best_hfr']
            
            # Find captures of the same filter that occur after this autofocus
            # Use a more generous time window (up to next autofocus OR 2 hours)
            next_af_timestamp = None
            for next_af in completed_autofocus:
                if (next_af['timestamp'] > af_timestamp and 
                    next_af.get('filter') == filter_name):
                    next_af_timestamp = next_af['timestamp']
                    break
            
            # If no next autofocus, use a 2-hour window
            if next_af_timestamp is None:
                next_af_timestamp = af_timestamp + 7200  # 2 hours in seconds
            
            # Only fill missing HFR data, don't overwrite existing values
            captures_updated = 0
            for capture in completed_captures:
                if (capture['filter'] == filter_name and 
                    capture['timestamp'] > af_timestamp and
                    capture['timestamp'] < next_af_timestamp):
                    
                    # Only update if HFR is missing (preserve real capture HFR values)
                    if capture.get('hfr') is None:
                        capture['hfr'] = best_hfr
                        capture['fwhm'] = self._calculate_fwhm_from_hfr(best_hfr)
                        captures_updated += 1
                        logging.debug(f"Filled missing HFR {best_hfr:.2f} and FWHM {capture['fwhm']:.2f} for {filter_name} capture at {capture['timestamp']}")
            
            if captures_updated > 0:
                logging.debug(f"Filled {captures_updated} missing HFR values from autofocus session at {af_timestamp}")
        
        return session_data
    
    def _calculate_sub_session_metrics(self, sub_session_captures: List[Dict], guide_data: List[Dict]) -> Dict[str, Any]:
        """Calculate comprehensive metrics for a sub-session including HFR, FWHM, and guide stats."""
        metrics = {
            'hfr_stats': {'min': None, 'max': None, 'avg': None, 'measurements': 0},
            'fwhm_stats': {'min': None, 'max': None, 'avg': None, 'measurements': 0},
            'guide_stats': {'avg_distance': 0.0, 'avg_rms': 0.0, 'guide_quality': 'No Data', 'measurements': 0},
            'star_stats': {'min': None, 'max': None, 'avg': None, 'consistency': 1.0}
        }
        
        # Calculate HFR statistics
        hfr_values = [c['hfr'] for c in sub_session_captures if c.get('hfr') is not None]
        if hfr_values:
            metrics['hfr_stats'] = {
                'min': min(hfr_values),
                'max': max(hfr_values),
                'avg': sum(hfr_values) / len(hfr_values),
                'measurements': len(hfr_values)
            }
        
        # Calculate FWHM statistics
        fwhm_values = [c['fwhm'] for c in sub_session_captures if c.get('fwhm') is not None]
        if fwhm_values:
            metrics['fwhm_stats'] = {
                'min': min(fwhm_values),
                'max': max(fwhm_values),
                'avg': sum(fwhm_values) / len(fwhm_values),
                'measurements': len(fwhm_values)
            }
        
        # Calculate guide statistics
        if guide_data:
            # Calculate distance from dx,dy (more reliable than pre-calculated distance field)
            calculated_distances = []
            rms_values = []
            
            for g in guide_data:
                dx = g.get('dx', 0)
                dy = g.get('dy', 0)
                distance = math.sqrt(dx**2 + dy**2)
                calculated_distances.append(distance)
                
                if g.get('rms', 0) > 0:
                    rms_values.append(g['rms'])
            
            # Filter outliers (guide corrections > 10 arcsec are usually spurious)
            filtered_distances = [d for d in calculated_distances if d <= 10.0]
            
            if filtered_distances:
                avg_distance = sum(filtered_distances) / len(filtered_distances)
                avg_rms = sum(rms_values) / len(rms_values) if rms_values else 0.0
                
                # Determine guide quality using pixel scale if available
                quality = self._calculate_guide_quality_from_distance([avg_distance])
                
                metrics['guide_stats'] = {
                    'avg_distance': avg_distance,
                    'avg_rms': avg_rms,
                    'guide_quality': quality,
                    'measurements': len(guide_data)
                }
        
        # Calculate star count statistics
        star_counts = [c['stars'] for c in sub_session_captures if c.get('stars') is not None]
        if star_counts:
            min_stars = min(star_counts)
            max_stars = max(star_counts)
            avg_stars = sum(star_counts) / len(star_counts)
            
            # Calculate consistency (how stable the star count is)
            if max_stars > 0:
                consistency = min_stars / max_stars
            else:
                consistency = 1.0
            
            metrics['star_stats'] = {
                'min': min_stars,
                'max': max_stars,
                'avg': int(avg_stars),
                'consistency': consistency
            }
        
        return metrics
    
    def aggregate_session_data(self, session_files: List[str]) -> Dict[str, Any]:
        """Aggregate data from multiple session files with enhanced metrics calculation."""
        all_sessions = []
        
        for filepath in session_files:
            session_data = self.parse_analyze_file(filepath)
            # Associate autofocus HFR values with captures
            session_data = self._associate_autofocus_with_captures(session_data)
            if session_data['captures'] or session_data['autofocus_sessions']:
                all_sessions.append(session_data)
                
        if not all_sessions:
            return {}
            
        # Combine all sessions
        aggregated = {
            'sessions': all_sessions,
            'total_captures': 0,
            'capture_summary': defaultdict(list),
            'filter_analysis': {},  # Enhanced filter analysis with sub-sessions
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
        
        for session_idx, session in enumerate(all_sessions):
            # Collect captures
            completed_captures = [c for c in session['captures'] if c['event'] == 'complete']
            all_captures.extend(completed_captures)
            
            # Group captures by (object, filter) using per-capture scheduler association
            # This correctly assigns each capture to the scheduler job that was active
            # at the time of capture, not just the latest job in the session.
            fallback_name = self._extract_object_name(session['filepath'])
            for capture in completed_captures:
                obj_name = self._get_object_name_for_capture(
                    capture['timestamp'], session['scheduler_jobs']
                ) or fallback_name
                key = (obj_name, capture['filter'])
                aggregated['capture_summary'][key].append(capture)
            
            # Collect other data
            all_temperatures.extend(session['temperature_readings'])
            all_autofocus.extend([af for af in session['autofocus_sessions'] if af['event'] == 'complete'])
            all_guide_stats.extend(session['guide_stats'])
            all_guide_states.extend(session['guide_states'])
            all_align_states.extend(session['align_states'])
            all_scheduler_jobs.extend(session['scheduler_jobs'])
            all_issues.extend(session['issues'])
            
            # Track session timing
            if session['session_start']:
                try:
                    start_time = None
                    datetime_str = session['session_start']
                    
                    # Try with microseconds first
                    try:
                        start_time = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S.%f')
                    except ValueError:
                        # Try without microseconds
                        try:
                            start_time = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            start_time = None
                    
                    if start_time:
                        if not earliest_start or start_time < earliest_start:
                            earliest_start = start_time
                            
                        # Estimate end time from last event
                        if session['captures']:
                            last_capture_time = max(c['timestamp'] for c in session['captures'])
                            end_time = start_time + timedelta(seconds=last_capture_time)
                            if not latest_end or end_time > latest_end:
                                latest_end = end_time
                except Exception as e:
                    logging.debug(f"Error parsing session timing: {e}")
                    pass
        
        aggregated['total_captures'] = len(all_captures)
        
        # Build enhanced filter analysis with sub-sessions
        aggregated['filter_analysis'] = self._build_enhanced_filter_analysis(
            aggregated['capture_summary'], 
            all_sessions
        )
        
        # Calculate session duration
        if earliest_start and latest_end:
            duration = latest_end - earliest_start
            aggregated['session_duration'] = {
                'start': earliest_start,
                'end': latest_end,
                'duration_hours': duration.total_seconds() / 3600
            }
        
        # Calculate temperature stats
        if all_temperatures:
            temps = [t['temperature'] for t in all_temperatures]
            aggregated['temperature_stats'] = {
                'min': min(temps),
                'max': max(temps),
                'avg': sum(temps) / len(temps),
                'readings_count': len(temps)
            }
        
        # Calculate enhanced autofocus stats
        if all_autofocus:
            valid_temps = [af['temperature'] for af in all_autofocus if af['temperature'] > -999999]
            hfr_values = [af['best_hfr'] for af in all_autofocus if af.get('best_hfr')]
            
            aggregated['autofocus_stats'] = {
                'sessions_count': len(all_autofocus),
                'avg_temperature': sum(valid_temps) / len(valid_temps) if valid_temps else None,
                'avg_hfr': sum(hfr_values) / len(hfr_values) if hfr_values else None,
                'best_hfr': min(hfr_values) if hfr_values else None,
                'worst_hfr': max(hfr_values) if hfr_values else None
            }
        
        # Calculate guide stats
        if all_guide_stats:
            calculated_distances = []
            for g in all_guide_stats:
                dx = g.get('dx', 0)
                dy = g.get('dy', 0)
                distance = math.sqrt(dx**2 + dy**2)
                calculated_distances.append(distance)
            
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
        
        # Summarize issues
        aggregated['issues_summary'] = all_issues
        
        return aggregated
    
    def _build_enhanced_filter_analysis(self, capture_summary: Dict[Tuple[str, str], List[Dict]], 
                                      all_sessions: List[Dict]) -> Dict[str, Any]:
        """
        Build enhanced filter analysis with sub-sessions detection, HFR/FWHM metrics, and guide correlation.
        """
        filter_analysis = {}
        
        # Create session_start mapping for absolute time calculation
        session_start_map = {}
        for session in all_sessions:
            if session['session_start']:
                try:
                    datetime_str = session['session_start']
                    if '.' in datetime_str:
                        datetime_str = datetime_str.split('.')[0]
                    session_start_time = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
                    session_start_map[session['filepath']] = session_start_time
                except ValueError:
                    logging.debug(f"Could not parse session start: {session['session_start']}")
        
        # Group all captures by filter (ignoring object name for now) and track source session
        filter_captures = defaultdict(list)
        for (obj_name, filter_name), captures in capture_summary.items():
            for capture in captures:
                # Find which session this capture belongs to (by timestamp matching)
                capture['source_session'] = None
                for session in all_sessions:
                    session_captures = [c for c in session['captures'] if c['event'] == 'complete']
                    for session_capture in session_captures:
                        if abs(session_capture['timestamp'] - capture['timestamp']) < 1:  # Same timestamp
                            capture['source_session'] = session['filepath']
                            break
                    if capture['source_session']:
                        break
                
                filter_captures[filter_name].append(capture)
        
        # Create mapping of timestamps to guide data from all sessions
        timestamp_to_guide = {}
        for session in all_sessions:
            for guide_point in session.get('guide_stats', []):
                timestamp_to_guide[guide_point['timestamp']] = guide_point
        
        # Analyze each filter
        for filter_name, all_filter_captures in filter_captures.items():
            if not all_filter_captures:
                continue
                
            # Sort captures by timestamp
            sorted_captures = sorted(all_filter_captures, key=lambda x: x['timestamp'])
            
            # Detect temporal sub-sessions (gaps > 30 minutes = 1800 seconds)
            sub_sessions = []
            current_session = []
            
            for i, capture in enumerate(sorted_captures):
                if i == 0:
                    current_session = [capture]
                else:
                    time_gap = capture['timestamp'] - sorted_captures[i-1]['timestamp']
                    if time_gap > 1800:  # 30 minutes gap = new sub-session
                        # Finalize current sub-session
                        if current_session:
                            sub_sessions.append(current_session)
                        current_session = [capture]
                    else:
                        current_session.append(capture)
            
            # Add the last sub-session
            if current_session:
                sub_sessions.append(current_session)
            
            # Analyze each sub-session with enhanced metrics
            analyzed_sub_sessions = []
            for i, sub_session_captures in enumerate(sub_sessions):
                # Use capture completion timestamps for sub-session boundaries
                start_ts = min(cap['timestamp'] for cap in sub_session_captures)
                end_ts = max(cap['timestamp'] for cap in sub_session_captures)
                
                # Find the session start time for this sub-session
                # Use the first capture's source session to get the session start
                session_start_time = None
                for capture in sub_session_captures:
                    if capture.get('source_session') and capture['source_session'] in session_start_map:
                        session_start_time = session_start_map[capture['source_session']]
                        break
                
                # If no session start found, use first available session start as fallback
                if not session_start_time and session_start_map:
                    session_start_time = list(session_start_map.values())[0]
                
                # Calculate absolute times from relative timestamps
                if session_start_time:
                    absolute_start = session_start_time + timedelta(seconds=start_ts)
                    absolute_end = session_start_time + timedelta(seconds=end_ts)
                    start_time_formatted = absolute_start.strftime('%H:%M')
                    end_time_formatted = absolute_end.strftime('%H:%M')
                else:
                    # Fallback to relative times if session start not available
                    start_time_formatted = f"T+{int(start_ts//3600):02d}:{int((start_ts%3600)//60):02d}"
                    end_time_formatted = f"T+{int(end_ts//3600):02d}:{int((end_ts%3600)//60):02d}"
                
                # Expand time window to include guide data during capture acquisition
                # Look for corresponding CaptureStarting events to get the real start time
                expanded_start_ts = start_ts
                expanded_end_ts = end_ts
                
                # Find CaptureStarting events that correspond to our captures
                for session in all_sessions:
                    for capture_event in session.get('captures', []):
                        if capture_event.get('event') == 'starting':
                            # Find if this starting event has a corresponding complete event in our sub-session
                            for completed_capture in sub_session_captures:
                                # Match by filter and proximity (within reasonable time window)
                                time_diff = abs(completed_capture['timestamp'] - capture_event['timestamp'])
                                if (capture_event.get('filter') == completed_capture.get('filter') and
                                    time_diff < 1200):  # Max 20 minutes between start and complete
                                    expanded_start_ts = min(expanded_start_ts, capture_event['timestamp'])
                
                # Add buffer time (30 seconds before and after for guide settling)
                guide_window_start = expanded_start_ts - 30
                guide_window_end = expanded_end_ts + 30
                duration_minutes = (end_ts - expanded_start_ts) / 60
                
                # Find corresponding guide data for this expanded sub-session window
                sub_session_guide_data = []
                for guide_point in timestamp_to_guide.values():
                    if guide_window_start <= guide_point['timestamp'] <= guide_window_end:
                        sub_session_guide_data.append(guide_point)
                
                # Calculate comprehensive metrics for this sub-session
                metrics = self._calculate_sub_session_metrics(sub_session_captures, sub_session_guide_data)
                
                # Extract exposure time and calculate timing info
                exposure_time = sub_session_captures[0]['exposure'] if sub_session_captures else 0
                
                # Create enhanced sub-session analysis
                sub_session_analysis = {
                    'sub_session_id': i + 1,
                    'capture_count': len(sub_session_captures),
                    'start_timestamp': start_ts,
                    'end_timestamp': end_ts,
                    'duration_minutes': duration_minutes,
                    'exposure_time': exposure_time,
                    'start_time_formatted': start_time_formatted,
                    'end_time_formatted': end_time_formatted,
                    'hfr_stats': metrics['hfr_stats'],
                    'fwhm_stats': metrics['fwhm_stats'],
                    'guide_stats': metrics['guide_stats'],
                    'star_stats': metrics['star_stats'],
                    'captures': sub_session_captures
                }
                
                analyzed_sub_sessions.append(sub_session_analysis)
            
            # Calculate global stats for this filter across all sub-sessions
            total_captures = len(all_filter_captures)
            total_duration_minutes = sum(sub['duration_minutes'] for sub in analyzed_sub_sessions)
            
            # Calculate weighted average metrics across sub-sessions
            total_hfr_measurements = sum(sub['hfr_stats']['measurements'] for sub in analyzed_sub_sessions)
            total_fwhm_measurements = sum(sub['fwhm_stats']['measurements'] for sub in analyzed_sub_sessions)
            total_guide_measurements = sum(sub['guide_stats']['measurements'] for sub in analyzed_sub_sessions)
            
            # Weighted averages for HFR
            if total_hfr_measurements > 0:
                weighted_avg_hfr = sum(sub['hfr_stats']['avg'] * sub['hfr_stats']['measurements'] 
                                     for sub in analyzed_sub_sessions if sub['hfr_stats']['avg'] is not None) / total_hfr_measurements
                all_hfr_values = []
                for sub in analyzed_sub_sessions:
                    for cap in sub['captures']:
                        if cap.get('hfr') is not None:
                            all_hfr_values.append(cap['hfr'])
                min_hfr = min(all_hfr_values) if all_hfr_values else None
                max_hfr = max(all_hfr_values) if all_hfr_values else None
            else:
                weighted_avg_hfr = None
                min_hfr = None
                max_hfr = None
            
            # Weighted averages for FWHM
            if total_fwhm_measurements > 0:
                weighted_avg_fwhm = sum(sub['fwhm_stats']['avg'] * sub['fwhm_stats']['measurements'] 
                                      for sub in analyzed_sub_sessions if sub['fwhm_stats']['avg'] is not None) / total_fwhm_measurements
                all_fwhm_values = []
                for sub in analyzed_sub_sessions:
                    for cap in sub['captures']:
                        if cap.get('fwhm') is not None:
                            all_fwhm_values.append(cap['fwhm'])
                min_fwhm = min(all_fwhm_values) if all_fwhm_values else None
                max_fwhm = max(all_fwhm_values) if all_fwhm_values else None
            else:
                weighted_avg_fwhm = None
                min_fwhm = None
                max_fwhm = None
            
            # Weighted averages for guide stats
            if total_guide_measurements > 0:
                weighted_avg_distance = sum(sub['guide_stats']['avg_distance'] * sub['guide_stats']['measurements'] 
                                          for sub in analyzed_sub_sessions if sub['guide_stats']['measurements'] > 0) / total_guide_measurements
                weighted_avg_rms = sum(sub['guide_stats']['avg_rms'] * sub['guide_stats']['measurements'] 
                                     for sub in analyzed_sub_sessions if sub['guide_stats']['measurements'] > 0) / total_guide_measurements
                overall_quality = self._calculate_guide_quality_from_distance([weighted_avg_distance])
            else:
                weighted_avg_distance = 0.0
                weighted_avg_rms = 0.0
                overall_quality = "No Data"
            
            # Create complete filter analysis
            filter_analysis[filter_name] = {
                'total_captures': total_captures,
                'total_sub_sessions': len(analyzed_sub_sessions),
                'total_duration_minutes': total_duration_minutes,
                'total_duration_hours': total_duration_minutes / 60,
                'exposure_time': analyzed_sub_sessions[0]['exposure_time'] if analyzed_sub_sessions else 0,
                'sub_sessions': analyzed_sub_sessions,
                'global_hfr_stats': {
                    'avg': weighted_avg_hfr,
                    'min': min_hfr,
                    'max': max_hfr,
                    'measurements': total_hfr_measurements
                },
                'global_fwhm_stats': {
                    'avg': weighted_avg_fwhm,
                    'min': min_fwhm,
                    'max': max_fwhm,
                    'measurements': total_fwhm_measurements
                },
                'global_guide_stats': {
                    'avg_distance': weighted_avg_distance,
                    'avg_rms': weighted_avg_rms,
                    'guide_quality': overall_quality,
                    'total_measurements': total_guide_measurements
                }
            }
        
        return filter_analysis
    
    def _calculate_guide_quality_from_distance(self, distances: List[float]) -> str:
        """
        Calculate guide quality rating using pixel-scale-based thresholds.
        Much more accurate than fixed arcsecond thresholds!
        """
        if not distances:
            return "Unknown"
        
        avg_distance_arcsec = sum(distances) / len(distances)
        
        # Use pixel-scale-based thresholds if available
        if self.pixel_scale_arcsec and self.pixel_scale_arcsec > 0:
            # Convert arcsecond error to pixel error
            avg_distance_pixels = avg_distance_arcsec / self.pixel_scale_arcsec
            
            # Use pixel-based thresholds (much more accurate!)
            if avg_distance_pixels < self.guide_quality_thresholds['excellent_px']:
                return "Excellent"
            elif avg_distance_pixels < self.guide_quality_thresholds['good_px']:
                return "Good"
            elif avg_distance_pixels < self.guide_quality_thresholds['average_px']:
                return "Average"
            else:
                return "Poor"
        else:
            # Fallback to old arcsecond-based thresholds (less accurate)
            logging.debug("Using legacy arcsecond-based guide quality thresholds - consider configuring pixel scale for better accuracy")
            if avg_distance_arcsec < 1.0:
                return "Excellent"
            elif avg_distance_arcsec < 2.0:
                return "Good"
            elif avg_distance_arcsec < 3.0:
                return "Average"
            else:
                return "Poor"
    
    def _get_object_name_from_scheduler(self, scheduler_jobs: List[Dict]) -> str:
        """Extract object name from scheduler job data (returns latest job - legacy fallback)."""
        if not scheduler_jobs:
            return None
            
        # Find the most recent scheduler job start
        started_jobs = [job for job in scheduler_jobs if job['event'] == 'start']
        if started_jobs:
            # Get the latest started job
            latest_job = max(started_jobs, key=lambda x: x['timestamp'])
            return latest_job.get('object_name', 'Unknown')
        
        return None

    def _get_object_name_for_capture(self, capture_timestamp: float, scheduler_jobs: List[Dict]) -> str:
        """Get the correct object name for a capture based on its timestamp.
        
        Finds which scheduler job was active when the capture was taken by looking
        at the most recent SchedulerJobStart before the capture timestamp.
        """
        if not scheduler_jobs:
            return None
        
        # Get all job start events sorted by timestamp
        started_jobs = sorted(
            [job for job in scheduler_jobs if job['event'] == 'start'],
            key=lambda x: x['timestamp']
        )
        
        if not started_jobs:
            return None
        
        # Find the most recent job start that is before (or at) the capture timestamp
        active_job = None
        for job in started_jobs:
            if job['timestamp'] <= capture_timestamp:
                active_job = job
            else:
                break  # Jobs are sorted, no need to continue
        
        if active_job:
            return active_job.get('object_name', 'Unknown')
        
        # If capture is before any job start, use the first job
        return started_jobs[0].get('object_name', 'Unknown')
    
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
