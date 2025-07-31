"""
Advanced Metrics Calculator for Astro Session Analysis
Specialized calculations for data lovers and deep session analysis
"""
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict
import statistics
from scipy import stats
from scipy.stats import linregress


class AdvancedMetricsCalculator:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.alert_thresholds = self.config.get('alert_thresholds', {})
        
    def calculate_all_advanced_metrics(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate all advanced metrics for a session."""
        metrics = {}
        
        # Extract data for analysis
        captures = self._extract_capture_data(session_data)
        temperatures = session_data.get('temperature_readings', [])
        autofocus_sessions = session_data.get('autofocus_sessions', [])
        
        if not captures:
            return metrics
            
        # Quality and Seeing Analysis
        metrics['quality_analysis'] = self.analyze_image_quality(captures)
        
        # Temperature Analysis
        if temperatures:
            metrics['temperature_analysis'] = self.analyze_temperature_effects(captures, temperatures)
        
        # Performance Analysis
        metrics['performance_analysis'] = self.analyze_session_performance(session_data)
        
        # Efficiency Analysis
        metrics['efficiency_analysis'] = self.calculate_session_efficiency(session_data)
        
        # Autofocus Analysis
        if autofocus_sessions:
            metrics['autofocus_analysis'] = self.analyze_autofocus_performance(autofocus_sessions, temperatures)
        
        # Temporal Analysis
        metrics['temporal_analysis'] = self.analyze_temporal_patterns(captures, temperatures)
        
        # Alert Analysis
        metrics['alerts'] = self.generate_performance_alerts(metrics)
        
        return metrics
    
    def analyze_image_quality(self, captures: List[Dict]) -> Dict[str, Any]:
        """Analyze image quality metrics in detail."""
        analysis = {}
        
        # Extract HFR and star data
        hfr_data = [c['hfr'] for c in captures if c.get('hfr') is not None]
        star_data = [c['stars'] for c in captures if c.get('stars') is not None]
        
        if not hfr_data:
            return analysis
        
        # Basic HFR statistics
        analysis['hfr_stats'] = {
            'mean': np.mean(hfr_data),
            'median': np.median(hfr_data),
            'std': np.std(hfr_data),
            'min': np.min(hfr_data),
            'max': np.max(hfr_data),
            'range': np.max(hfr_data) - np.min(hfr_data)
        }
        
        # HFR Stability Index (lower is better)
        if analysis['hfr_stats']['mean'] > 0:
            analysis['hfr_stability_index'] = analysis['hfr_stats']['std'] / analysis['hfr_stats']['mean']
        
        # Seeing conditions estimation
        avg_hfr = analysis['hfr_stats']['mean']
        if avg_hfr < 2.0:
            seeing_condition = "Excellent"
        elif avg_hfr < 3.0:
            seeing_condition = "Good"
        elif avg_hfr < 4.0:
            seeing_condition = "Average"
        else:
            seeing_condition = "Poor"
        analysis['seeing_condition'] = seeing_condition
        
        # HFR trend analysis
        if len(hfr_data) > 3:
            timestamps = list(range(len(hfr_data)))
            slope, intercept, r_value, p_value, std_err = linregress(timestamps, hfr_data)
            analysis['hfr_trend'] = {
                'slope': slope,
                'correlation': r_value,
                'p_value': p_value,
                'trend_direction': 'improving' if slope < -0.01 else 'degrading' if slope > 0.01 else 'stable'
            }
        
        # Star detection analysis
        if star_data:
            analysis['star_detection'] = {
                'mean': np.mean(star_data),
                'std': np.std(star_data),
                'consistency_score': 1 - (np.std(star_data) / max(np.mean(star_data), 1))
            }
        
        # Quality score (0-100)
        quality_score = self._calculate_quality_score(analysis)
        analysis['quality_score'] = quality_score
        
        return analysis
    
    def analyze_temperature_effects(self, captures: List[Dict], temperatures: List[Dict]) -> Dict[str, Any]:
        """Analyze temperature effects on image quality."""
        analysis = {}
        
        if not temperatures or not captures:
            return analysis
        
        temp_values = [t['temperature'] for t in temperatures]
        analysis['temperature_stats'] = {
            'min': np.min(temp_values),
            'max': np.max(temp_values),
            'mean': np.mean(temp_values),
            'std': np.std(temp_values),
            'range': np.max(temp_values) - np.min(temp_values)
        }
        
        # Thermal stability score (0-1, higher is better)
        temp_range = analysis['temperature_stats']['range']
        if temp_range < 1:
            thermal_stability = 1.0
        elif temp_range < 3:
            thermal_stability = 0.8
        elif temp_range < 5:
            thermal_stability = 0.6
        else:
            thermal_stability = max(0.2, 1.0 - (temp_range / 20))
        
        analysis['thermal_stability_score'] = thermal_stability
        
        # Temperature-HFR correlation
        hfr_data = [c['hfr'] for c in captures if c.get('hfr') is not None]
        if len(hfr_data) > 5 and len(temp_values) > 5:
            # Interpolate temperatures to match capture timestamps
            capture_temps = self._interpolate_temperatures(captures, temperatures)
            if len(capture_temps) == len(hfr_data):
                correlation, p_value = stats.pearsonr(capture_temps, hfr_data)
                analysis['temp_hfr_correlation'] = {
                    'correlation': correlation,
                    'p_value': p_value,
                    'significant': p_value < 0.05
                }
        
        return analysis
    
    def analyze_session_performance(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze overall session performance."""
        analysis = {}
        
        captures = session_data.get('capture_summary', {})
        issues = session_data.get('issues_summary', [])
        total_captures = session_data.get('total_captures', 0)
        
        # Success rate calculation
        aborted_captures = len([i for i in issues if i.get('type') == 'capture_aborted'])
        total_attempts = total_captures + aborted_captures
        success_rate = total_captures / max(total_attempts, 1)
        
        analysis['success_rate'] = success_rate
        analysis['total_attempts'] = total_attempts
        analysis['failed_captures'] = aborted_captures
        
        # Performance by filter
        filter_performance = {}
        for (obj, filt), capture_list in captures.items():
            if capture_list:
                hfr_values = [c['hfr'] for c in capture_list if c.get('hfr')]
                if hfr_values:
                    filter_performance[filt] = {
                        'count': len(capture_list),
                        'avg_hfr': np.mean(hfr_values),
                        'hfr_consistency': 1 - (np.std(hfr_values) / max(np.mean(hfr_values), 1))
                    }
        
        analysis['filter_performance'] = filter_performance
        
        # Session productivity score (0-100)
        productivity_score = min(100, success_rate * 100 * (total_captures / max(10, total_captures)))
        analysis['productivity_score'] = productivity_score
        
        return analysis
    
    def calculate_session_efficiency(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate session efficiency metrics."""
        analysis = {}
        
        duration = session_data.get('session_duration')
        logging.debug(f"Session duration data: {duration}")
        if not duration:
            logging.debug("No session duration found, cannot calculate efficiency")
            return analysis
        
        total_duration_hours = duration['duration_hours']
        captures = self._extract_capture_data(session_data)
        
        if not captures:
            return analysis
        
        # Calculate actual imaging time
        imaging_time = sum(c.get('exposure', 0) for c in captures) / 3600  # hours
        
        # Efficiency metrics
        analysis['total_duration_hours'] = total_duration_hours
        analysis['imaging_time_hours'] = imaging_time
        analysis['imaging_efficiency'] = imaging_time / max(total_duration_hours, 0.1)
        analysis['avg_time_per_frame'] = (total_duration_hours * 3600) / max(len(captures), 1)
        
        # Downtime analysis
        downtime_hours = total_duration_hours - imaging_time
        analysis['downtime_hours'] = downtime_hours
        analysis['downtime_percentage'] = (downtime_hours / max(total_duration_hours, 0.1)) * 100
        
        return analysis
    
    def analyze_autofocus_performance(self, autofocus_sessions: List[Dict], temperatures: List[Dict]) -> Dict[str, Any]:
        """Analyze autofocus session performance."""
        analysis = {}
        
        completed_af = [af for af in autofocus_sessions if af.get('event') == 'complete']
        
        if not completed_af:
            return analysis
        
        analysis['total_sessions'] = len(completed_af)
        
        # Temperature correlation
        if temperatures:
            af_temps = [af['temperature'] for af in completed_af if af.get('temperature')]
            if af_temps:
                analysis['temperature_stats'] = {
                    'mean': np.mean(af_temps),
                    'std': np.std(af_temps),
                    'range': np.max(af_temps) - np.min(af_temps)
                }
        
        # Filter-specific analysis
        filter_af_stats = defaultdict(list)
        for af in completed_af:
            filt = af.get('filter', 'Unknown')
            filter_af_stats[filt].append(af)
        
        analysis['by_filter'] = {}
        for filt, af_list in filter_af_stats.items():
            analysis['by_filter'][filt] = {
                'sessions': len(af_list),
                'avg_temperature': np.mean([af['temperature'] for af in af_list if af.get('temperature')])
            }
        
        # Frequency analysis
        if len(completed_af) > 1:
            timestamps = [af['timestamp'] for af in completed_af]
            intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
            analysis['avg_interval_minutes'] = np.mean(intervals) / 60
        
        return analysis
    
    def analyze_temporal_patterns(self, captures: List[Dict], temperatures: List[Dict]) -> Dict[str, Any]:
        """Analyze temporal patterns in the session."""
        analysis = {}
        
        if not captures:
            return analysis
        
        # Hourly performance analysis
        timestamps = [c['timestamp'] for c in captures]
        if timestamps:
            start_time = min(timestamps)
            hourly_stats = defaultdict(list)
            
            for capture in captures:
                hour = int((capture['timestamp'] - start_time) / 3600)
                if capture.get('hfr'):
                    hourly_stats[hour].append(capture['hfr'])
            
            hourly_analysis = {}
            for hour, hfr_list in hourly_stats.items():
                if hfr_list:
                    hourly_analysis[hour] = {
                        'avg_hfr': np.mean(hfr_list),
                        'capture_count': len(hfr_list)
                    }
            
            analysis['hourly_performance'] = hourly_analysis
        
        # Best/worst periods detection
        if len(captures) > 10:
            window_size = max(5, len(captures) // 4)
            best_hfr = float('inf')
            worst_hfr = 0
            best_window = None
            worst_window = None
            
            for i in range(len(captures) - window_size + 1):
                window_captures = captures[i:i+window_size]
                window_hfrs = [c['hfr'] for c in window_captures if c.get('hfr')]
                
                if window_hfrs:
                    avg_hfr = np.mean(window_hfrs)
                    if avg_hfr < best_hfr:
                        best_hfr = avg_hfr
                        best_window = i
                    if avg_hfr > worst_hfr:
                        worst_hfr = avg_hfr
                        worst_window = i
            
            analysis['optimal_periods'] = {
                'best_window_start': best_window,
                'best_avg_hfr': best_hfr,
                'worst_window_start': worst_window,
                'worst_avg_hfr': worst_hfr
            }
        
        return analysis
    
    def generate_performance_alerts(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate alerts based on performance thresholds."""
        alerts = []
        
        # HFR drift alert
        quality = metrics.get('quality_analysis', {})
        hfr_trend = quality.get('hfr_trend', {})
        if hfr_trend.get('slope', 0) > self.alert_thresholds.get('hfr_drift_warning', 0.5):
            alerts.append({
                'type': 'hfr_drift',
                'severity': 'warning',
                'message': f"HFR showing degrading trend: {hfr_trend['slope']:.3f} pixels/frame"
            })
        
        # High HFR alert
        hfr_stats = quality.get('hfr_stats', {})
        max_hfr = hfr_stats.get('max', 0)
        if max_hfr > 4.0:
            alerts.append({
                'type': 'high_hfr',
                'severity': 'warning' if max_hfr < 5.0 else 'error',
                'message': f"High HFR detected: {max_hfr:.2f} pixels (consider refocusing)"
            })
        
        # Temperature swing alert
        temp_analysis = metrics.get('temperature_analysis', {})
        temp_range = temp_analysis.get('temperature_stats', {}).get('range', 0)
        if temp_range > self.alert_thresholds.get('temperature_swing_warning', 5.0):
            alerts.append({
                'type': 'temperature_swing',
                'severity': 'warning',
                'message': f"Large temperature swing: {temp_range:.1f}°C"
            })
        
        # Success rate alert
        performance = metrics.get('performance_analysis', {})
        success_rate = performance.get('success_rate', 1.0)
        if success_rate < self.alert_thresholds.get('success_rate_warning', 0.8):
            alerts.append({
                'type': 'low_success_rate',
                'severity': 'error',
                'message': f"Low success rate: {success_rate*100:.1f}%"
            })
        
        return alerts
    
    def _extract_capture_data(self, session_data: Dict[str, Any]) -> List[Dict]:
        """Extract and flatten capture data from session."""
        captures = []
        capture_summary = session_data.get('capture_summary', {})
        
        for (obj, filt), capture_list in capture_summary.items():
            for capture in capture_list:
                capture_enhanced = capture.copy()
                capture_enhanced['object'] = obj
                capture_enhanced['filter'] = filt
                captures.append(capture_enhanced)
        
        return sorted(captures, key=lambda x: x.get('timestamp', 0))
    
    def _interpolate_temperatures(self, captures: List[Dict], temperatures: List[Dict]) -> List[float]:
        """Interpolate temperature values to match capture timestamps."""
        if not temperatures or not captures:
            return []
        
        temp_times = [t['timestamp'] for t in temperatures]
        temp_values = [t['temperature'] for t in temperatures]
        capture_times = [c['timestamp'] for c in captures if c.get('hfr')]
        
        interpolated = []
        for cap_time in capture_times:
            # Simple linear interpolation
            closest_idx = min(range(len(temp_times)), key=lambda i: abs(temp_times[i] - cap_time))
            interpolated.append(temp_values[closest_idx])
        
        return interpolated
    
    def _calculate_quality_score(self, quality_analysis: Dict[str, Any]) -> float:
        """Calculate overall quality score (0-100)."""
        score = 50  # base score
        
        # HFR contribution (lower is better)
        hfr_stats = quality_analysis.get('hfr_stats', {})
        avg_hfr = hfr_stats.get('mean', 5.0)
        if avg_hfr < 2.0:
            score += 30
        elif avg_hfr < 3.0:
            score += 20
        elif avg_hfr < 4.0:
            score += 10
        else:
            score -= 10
        
        # Stability contribution
        stability = quality_analysis.get('hfr_stability_index', 1.0)
        if stability < 0.1:
            score += 20
        elif stability < 0.2:
            score += 10
        elif stability > 0.5:
            score -= 20
        
        return max(0, min(100, score))
