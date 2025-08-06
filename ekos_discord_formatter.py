"""
Unified Discord Formatter for Ekos Session Data
Supports multiple configurable detail levels from minimal to expert
"""
import numpy as np
import logging
from datetime import datetime
from typing import Dict, List, Any
from collections import defaultdict

# Try to import advanced metrics, fallback gracefully
try:
    from advanced_metrics import AdvancedMetricsCalculator
    ADVANCED_METRICS_AVAILABLE = True
except ImportError:
    ADVANCED_METRICS_AVAILABLE = False
    logging.debug("Advanced metrics not available, using basic mode")

def format_duration(hours: float) -> str:
    """Format duration in hours to human readable format."""
    if hours < 1:
        minutes = int(hours * 60)
        return f"{minutes}m"
    elif hours < 24:
        h = int(hours)
        m = int((hours - h) * 60)
        return f"{h}h {m}m" if m > 0 else f"{h}h"
    else:
        days = int(hours / 24)
        h = int(hours % 24)
        return f"{days}d {h}h" if h > 0 else f"{days}d"

def format_temperature(temp: float) -> str:
    """Format temperature with appropriate precision."""
    return f"{temp:.1f}°C"

def generate_ekos_discord_summary(ekos_data: Dict[str, Any], config: Dict[str, Any] = None) -> str:
    """Generate a Discord-friendly summary from Ekos session data with configurable detail level."""
    if not ekos_data or not ekos_data.get('capture_summary'):
        return "🌙 No Ekos session data available for this period."
    
    config = config or {}
    report_level = config.get('discord_report_level', 'standard')
    
    # Calculate advanced metrics if enabled and available
    # Automatically enable for detailed level, or if explicitly enabled
    advanced_metrics = {}
    should_use_advanced = (report_level == 'detailed' or 
                          config.get('advanced_analytics', {}).get('enabled', False))
    
    if should_use_advanced and ADVANCED_METRICS_AVAILABLE:
        try:
            calculator = AdvancedMetricsCalculator(config)
            advanced_metrics = calculator.calculate_all_advanced_metrics(ekos_data)
            logging.debug(f"Advanced metrics calculated: {list(advanced_metrics.keys())}")
        except Exception as e:
            logging.debug(f"Advanced metrics calculation failed: {e}")
    
    # Route to appropriate formatter based on level
    if report_level == 'minimal':
        return _generate_minimal_report(ekos_data, advanced_metrics, config)
    elif report_level == 'detailed':
        return _generate_detailed_report(ekos_data, advanced_metrics, config)
    else:  # standard or default
        return _generate_standard_report(ekos_data, advanced_metrics, config)

def _generate_minimal_report(ekos_data: Dict[str, Any], advanced_metrics: Dict[str, Any], config: Dict[str, Any]) -> str:
    """Generate minimal report for quick notifications."""
    lines = ["**🔭 Session Summary (Minimal)**"]
    
    total_captures = ekos_data.get('total_captures', 0)
    lines.append(f"📸 **{total_captures} captures completed**")
    
    # Duration if available
    duration = ekos_data.get('session_duration')
    if duration:
        duration_str = format_duration(duration['duration_hours'])
        lines.append(f"⏰ Duration: {duration_str}")
    
    # Add essential session conditions
    conditions_summary = generate_conditions_summary(ekos_data)
    if conditions_summary:
        lines.append("")
        lines.append(conditions_summary)
    
    # Add essential autofocus summary
    autofocus_summary = generate_autofocus_summary(ekos_data.get('autofocus_stats', {}))
    if autofocus_summary:
        lines.append("")
        lines.append(autofocus_summary)
    
    # Critical alerts only
    alerts = advanced_metrics.get('alerts', [])
    critical_alerts = [a for a in alerts if a.get('severity') == 'error']
    if critical_alerts:
        lines.append("")
        lines.append(f"🚨 **{len(critical_alerts)} Critical Issues**")
        for alert in critical_alerts[:3]:  # Max 3 alerts
            lines.append(f"• {alert['message']}")
    
    return "\n".join(lines)

def _generate_standard_report(ekos_data: Dict[str, Any], advanced_metrics: Dict[str, Any], config: Dict[str, Any]) -> str:
    """Generate standard report (enhanced version of original)."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"**🔭 Ekos Session Summary**\n📅 {now}\n"]
    
    # Session overview
    lines.append(_format_session_overview(ekos_data, advanced_metrics))
    lines.append("")
    
    # Capture details
    lines.extend(_format_capture_details(ekos_data, 'basic'))
    
    # Always add session conditions (même si pas d'analytics avancées)
    conditions_summary = generate_conditions_summary(ekos_data)
    if conditions_summary:
        lines.append("")
        lines.append(conditions_summary)
    
    # CRUCIAL: Add guiding summary (always show - most important for astrophotography)
    guide_summary = generate_guide_summary(ekos_data.get('guide_stats', {}))
    if guide_summary:
        lines.append("")
        lines.append(guide_summary)
    
    # Always add autofocus summary (même si pas d'analytics avancées)
    autofocus_summary = generate_autofocus_summary(ekos_data.get('autofocus_stats', {}))
    if autofocus_summary:
        lines.append("")
        lines.append(autofocus_summary)
    
    # Quality summary if advanced metrics available
    if advanced_metrics.get('quality_analysis'):
        lines.append("")
        lines.append(_format_quality_analysis(advanced_metrics['quality_analysis'], 'basic'))
    
    # Issues and alerts
    issues_summary = _format_issues_summary(ekos_data.get('issues_summary', []), advanced_metrics.get('alerts', []))
    if issues_summary:
        lines.append("")
        lines.append(issues_summary)
    
    return "\n".join(lines)

def _generate_detailed_report(ekos_data: Dict[str, Any], advanced_metrics: Dict[str, Any], config: Dict[str, Any]) -> str:
    """Generate detailed report for enthusiasts."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"**🔬 Detailed Ekos Analysis**\n📅 {now}\n"]
    
    # Enhanced session overview
    lines.append(_format_session_overview(ekos_data, advanced_metrics, detail_level='detailed'))
    lines.append("")
    
    # Detailed capture analysis
    lines.extend(_format_capture_details(ekos_data, 'detailed'))
    
    # Quality analysis
    if advanced_metrics.get('quality_analysis'):
        lines.append("")
        lines.append(_format_quality_analysis(advanced_metrics['quality_analysis'], 'detailed'))
    
    # Add standard session conditions (from standard mode)
    conditions_summary = generate_conditions_summary(ekos_data)
    if conditions_summary:
        lines.append("")
        lines.append(conditions_summary)
    
    # CRUCIAL: Add guiding summary (most important for astrophotography)
    guide_summary = generate_guide_summary(ekos_data.get('guide_stats', {}))
    if guide_summary:
        lines.append("")
        lines.append(guide_summary)
    
    # Add standard autofocus summary (from standard mode)
    autofocus_summary = generate_autofocus_summary(ekos_data.get('autofocus_stats', {}))
    if autofocus_summary:
        lines.append("")
        lines.append(autofocus_summary)
    
    # Performance metrics removed - were confusing and not actionable
    # Focus on essential astrophotography metrics instead
    
    # Temperature correlation analysis
    if advanced_metrics.get('temperature_analysis'):
        lines.append("")
        lines.append(_format_temperature_analysis(advanced_metrics['temperature_analysis']))
    
    # Detailed autofocus analysis
    if advanced_metrics.get('autofocus_analysis'):
        lines.append("")
        lines.append(_format_autofocus_analysis(advanced_metrics['autofocus_analysis']))
    
    # Issues and alerts
    issues_summary = _format_issues_summary(ekos_data.get('issues_summary', []), advanced_metrics.get('alerts', []), detail_level='detailed')
    if issues_summary:
        lines.append("")
        lines.append(issues_summary)
    
    # Comprehensive alerts and recommendations
    comprehensive_alerts = _format_comprehensive_alerts(advanced_metrics)
    if comprehensive_alerts:
        lines.append("")
        lines.append(comprehensive_alerts)
    
    return "\n".join(lines)


def generate_session_overview(ekos_data: Dict[str, Any]) -> str:
    """Generate global session overview."""
    lines = ["🌙 **Session Overview**"]
    
    # Session duration
    if ekos_data.get('session_duration'):
        duration = ekos_data['session_duration']
        start_time = duration['start'].strftime("%H:%M")
        end_time = duration['end'].strftime("%H:%M")
        duration_str = format_duration(duration['duration_hours'])
        lines.append(f"⏰ Duration: {start_time} → {end_time} ({duration_str})")
    
    # Total captures
    total_captures = ekos_data.get('total_captures', 0)
    lines.append(f"📸 Total Captures: {total_captures}")
    
    # Temperature conditions
    temp_stats = ekos_data.get('temperature_stats', {})
    if temp_stats:
        temp_min = format_temperature(temp_stats['min'])
        temp_max = format_temperature(temp_stats['max'])
        temp_avg = format_temperature(temp_stats['avg'])
        lines.append(f"🌡️ Temperature: {temp_min} → {temp_max} (avg {temp_avg})")
    
    # Objects and filters summary
    capture_summary = ekos_data.get('capture_summary', {})
    if capture_summary:
        objects = set()
        filters = set()
        for (obj, filt), captures in capture_summary.items():
            objects.add(obj)
            filters.add(filt)
        
        lines.append(f"🎯 Objects: {len(objects)} | 🔍 Filters: {len(filters)} ({', '.join(sorted(filters))})")
    
    return "\n".join(lines)

def generate_capture_details(capture_summary: Dict) -> List[str]:
    """Generate detailed capture statistics by object/filter."""
    lines = ["📊 **Capture Details**"]
    
    for (obj, filt), captures in capture_summary.items():
        if not captures:
            continue
            
        n_frames = len(captures)
        
        # Calculate statistics
        hfrs = [c['hfr'] for c in captures if c.get('hfr') is not None]
        stars = [c['stars'] for c in captures if c.get('stars') is not None]
        exposures = [c['exposure'] for c in captures if c.get('exposure') is not None]
        
        if not hfrs and not stars:
            continue
            
        # Format object name (remove Session_ prefix if present)
        display_obj = obj.replace('Session_', '') if obj.startswith('Session_') else obj
        
        # Calculate total integration time
        total_integration = sum(exposures) if exposures else 0
        integration_str = format_duration(total_integration / 3600) if total_integration >= 60 else f"{total_integration:.0f}s"
        
        line_parts = [f"📌 {display_obj} - {filt} ({n_frames} frames, {integration_str})"]
        
        # Add HFR statistics if available
        if hfrs:
            hfr_min = min(hfrs)
            hfr_max = max(hfrs)
            hfr_avg = np.mean(hfrs)
            line_parts.append(f"   🔧 HFR: {hfr_min:.2f} → {hfr_max:.2f} (avg {hfr_avg:.2f})")
        
        # Add star count statistics if available
        if stars:
            stars_min = min(stars)
            stars_max = max(stars)
            stars_avg = np.mean(stars)
            line_parts.append(f"   ⭐ Stars: {stars_min} → {stars_max} (avg {stars_avg:.0f})")
        
        lines.extend(line_parts)
        lines.append("")  # Empty line between objects
    
    return lines

def generate_conditions_summary(ekos_data: Dict[str, Any]) -> str:
    """Generate summary of observing conditions."""
    lines = ["🌤️ **Session Conditions**"]
    
    temp_stats = ekos_data.get('temperature_stats', {})
    if temp_stats:
        temp_range = temp_stats['max'] - temp_stats['min']
        if temp_range > 5:
            stability = "Variable"
        elif temp_range > 2:
            stability = "Moderate"
        else:
            stability = "Stable"
        
        lines.append(f"🌡️ Temperature Stability: {stability} (Δ{temp_range:.1f}°C)")
    
    # Real mount tracking analysis
    mount_summary = generate_mount_tracking_summary(ekos_data)
    if mount_summary:
        lines.append(mount_summary)
    
    return "\n".join(lines) if len(lines) > 1 else ""

def generate_mount_tracking_summary(ekos_data: Dict[str, Any]) -> str:
    """Generate mount tracking analysis - only if meaningful data available."""
    # Get mount data from all sessions
    all_sessions = ekos_data.get('sessions', [])
    if not all_sessions:
        return ""
    
    mount_states = []
    
    for session in all_sessions:
        mount_states.extend(session.get('mount_states', []))
    
    if not mount_states:
        return ""
    
    # Analyze mount states
    state_counts = {}
    for state_entry in mount_states:
        state = state_entry['state']
        state_counts[state] = state_counts.get(state, 0) + 1
    
    # Only show if we have significant tracking data
    tracking_states = state_counts.get('Tracking', 0)
    total_states = len(mount_states)
    total_captures = ekos_data.get('total_captures', 1)
    
    # Suppress if insufficient data or misleading
    # (Less than 50% tracking ratio OR less than 0.5 events per capture)
    if tracking_states == 0 or tracking_states / total_captures < 0.5:
        return ""  # Don't show potentially confusing metric
    
    tracking_ratio = tracking_states / total_states
    if tracking_ratio > 0.8:
        tracking_quality = "Excellent"
    elif tracking_ratio > 0.6:
        tracking_quality = "Good"
    elif tracking_ratio > 0.4:
        tracking_quality = "Average"
    else:
        return ""  # Don't show "Poor" - likely misleading
    
    return f"🔭 Mount Tracking: {tracking_quality} ({tracking_states} events)"

def generate_guide_summary(guide_stats: Dict[str, Any]) -> str:
    """Generate guiding performance summary - CRUCIAL for astrophotography."""
    if not guide_stats or not guide_stats.get('total_measurements'):
        return ""
    
    lines = ["🌟 **Guiding Performance**"]
    
    total_measurements = guide_stats['total_measurements']
    avg_distance = guide_stats.get('avg_distance', 0)
    guide_quality = guide_stats.get('guide_quality', 'Unknown')
    
    lines.append(f"📊 Measurements: {total_measurements}")
    lines.append(f"🎯 Avg Error: {avg_distance:.2f}″")
    
    # Quality assessment with emoji
    quality_emoji = {
        'Excellent': '🟢',
        'Good': '🟡', 
        'Average': '🟠',
        'Poor': '🔴',
        'Unknown': '⚪'
    }
    
    emoji = quality_emoji.get(guide_quality, '⚪')
    lines.append(f"{emoji} Guide Quality: {guide_quality}")
    
    # Add detailed error breakdown if available
    ra_error = guide_stats.get('avg_ra_error', 0)
    dec_error = guide_stats.get('avg_dec_error', 0)
    if ra_error > 0 or dec_error > 0:
        lines.append(f"📈 RA: {ra_error:.2f}″ | DEC: {dec_error:.2f}″")
    
    return "\n".join(lines)

def generate_autofocus_summary(autofocus_stats: Dict[str, Any]) -> str:
    """Generate autofocus session summary."""
    if not autofocus_stats or not autofocus_stats.get('sessions_count'):
        return ""
    
    lines = ["🎯 **Autofocus Summary**"]
    
    sessions_count = autofocus_stats['sessions_count']
    avg_temp = autofocus_stats.get('avg_temperature', 0)
    
    lines.append(f"🔄 Sessions: {sessions_count}")
    if avg_temp:
        lines.append(f"🌡️ Average Temperature: {format_temperature(avg_temp)}")
    
    # Determine focus stability
    if sessions_count <= 2:
        stability = "Excellent"
    elif sessions_count <= 5:
        stability = "Good"
    else:
        stability = "Frequent adjustments"
    
    lines.append(f"📈 Focus Stability: {stability}")
    
    return "\n".join(lines)

def generate_issues_summary(issues: List[Dict[str, Any]]) -> str:
    """Generate summary of session issues."""
    if not issues:
        return ""
    
    lines = ["⚠️ **Session Issues**"]
    
    # Group issues by type
    issue_counts = defaultdict(int)
    for issue in issues:
        issue_type = issue.get('type', 'unknown')
        issue_counts[issue_type] += 1
    
    for issue_type, count in issue_counts.items():
        if issue_type == 'capture_aborted':
            lines.append(f"❌ Aborted Captures: {count}")
        else:
            lines.append(f"⚠️ {issue_type.replace('_', ' ').title()}: {count}")
    
    return "\n".join(lines)

# Helper formatting methods for advanced reports

def _format_session_overview(ekos_data: Dict[str, Any], advanced_metrics: Dict[str, Any], detail_level: str = 'basic') -> str:
    """Format session overview with configurable detail."""
    lines = ["🌙 **Session Overview**"]
    
    # Basic info
    total_captures = ekos_data.get('total_captures', 0)
    lines.append(f"📸 Total Captures: {total_captures}")
    
    # Duration
    duration = ekos_data.get('session_duration')
    if duration:
        duration_str = format_duration(duration['duration_hours'])
        start_time = duration['start'].strftime("%H:%M")
        end_time = duration['end'].strftime("%H:%M")
        lines.append(f"⏰ Duration: {start_time} → {end_time} ({duration_str})")
    
    # Temperature
    temp_stats = ekos_data.get('temperature_stats', {})
    if temp_stats:
        temp_min = f"{temp_stats['min']:.1f}°C"
        temp_max = f"{temp_stats['max']:.1f}°C"
        temp_avg = f"{temp_stats['avg']:.1f}°C"
        
        if detail_level in ['detailed', 'expert']:
            temp_analysis = advanced_metrics.get('temperature_analysis', {})
            stability_score = temp_analysis.get('thermal_stability_score', 0)
            stability_text = f" (Stability: {stability_score*100:.0f}%)"
        else:
            stability_text = ""
        
        lines.append(f"🌡️ Temperature: {temp_min} → {temp_max} (avg {temp_avg}){stability_text}")
    
    # Objects and filters
    capture_summary = ekos_data.get('capture_summary', {})
    if capture_summary:
        objects = set()
        filters = set()
        for (obj, filt), captures in capture_summary.items():
            objects.add(obj)
            filters.add(filt)
        lines.append(f"🎯 Objects: {len(objects)} | 🔍 Filters: {len(filters)} ({', '.join(sorted(filters))})")
    
    # Quality score removed - was arbitrary and not actionable
    
    return "\n".join(lines)

def _format_capture_details(ekos_data: Dict[str, Any], detail_level: str = 'basic') -> List[str]:
    """Format capture details with configurable detail level."""
    lines = ["📊 **Capture Details**"]
    
    capture_summary = ekos_data.get('capture_summary', {})
    for (obj, filt), captures in capture_summary.items():
        if not captures:
            continue
        
        n_frames = len(captures)
        
        # Calculate statistics based on detail level
        hfrs = [c['hfr'] for c in captures if c.get('hfr') is not None]
        stars = [c['stars'] for c in captures if c.get('stars') is not None]
        exposures = [c['exposure'] for c in captures if c.get('exposure') is not None]
        
        if not hfrs and not stars:
            continue
        
        # Object name formatting
        display_obj = obj.replace('Session_', '') if obj.startswith('Session_') else obj
        
        # Calculate sub duration format (NxTTTs)
        sub_format = ""
        if exposures:
            # Group by exposure duration to show format like "10x300s + 5x120s"
            from collections import Counter
            exposure_counts = Counter(exposures)
            sub_parts = []
            for exp_time, count in sorted(exposure_counts.items(), key=lambda x: (-x[1], -x[0])):  # Sort by count desc, then duration desc
                sub_parts.append(f"{count}x{int(exp_time)}s")
            sub_format = " + ".join(sub_parts)
        
        # Integration time
        total_integration = sum(exposures) if exposures else 0
        integration_str = format_duration(total_integration / 3600) if total_integration >= 60 else f"{total_integration:.0f}s"
        
        lines.append(f"📌 {display_obj} - {filt} ({sub_format}, {integration_str})")
        
        # HFR and FWHM statistics
        if hfrs:
            # Calculate FWHM from HFR (FWHM ≈ HFR × 2.35 for Gaussian PSF)
            fwhms = [hfr * 2.35 for hfr in hfrs]
            
            if detail_level == 'basic':
                lines.append(f"   🔧 HFR: {min(hfrs):.2f} → {max(hfrs):.2f} (avg {np.mean(hfrs):.2f})")
                lines.append(f"   📐 FWHM: {min(fwhms):.2f} → {max(fwhms):.2f} (avg {np.mean(fwhms):.2f})")
            elif detail_level in ['advanced', 'detailed']:
                lines.append(f"   🔧 HFR: {min(hfrs):.2f} → {max(hfrs):.2f} (avg {np.mean(hfrs):.2f}, σ {np.std(hfrs):.2f})")
                lines.append(f"   📐 FWHM: {min(fwhms):.2f} → {max(fwhms):.2f} (avg {np.mean(fwhms):.2f}, σ {np.std(fwhms):.2f})")
            elif detail_level == 'expert':
                lines.append(f"   🔧 HFR: min {min(hfrs):.2f} | max {max(hfrs):.2f} | mean {np.mean(hfrs):.2f} | median {np.median(hfrs):.2f} | σ {np.std(hfrs):.2f}")
                lines.append(f"   📐 FWHM: min {min(fwhms):.2f} | max {max(fwhms):.2f} | mean {np.mean(fwhms):.2f} | median {np.median(fwhms):.2f} | σ {np.std(fwhms):.2f}")
        
        # Star statistics
        if stars:
            if detail_level == 'basic':
                lines.append(f"   ⭐ Stars: {min(stars)} → {max(stars)} (avg {np.mean(stars):.0f})")
            elif detail_level in ['advanced', 'detailed', 'expert']:
                consistency = 1 - (np.std(stars) / max(np.mean(stars), 1))
                lines.append(f"   ⭐ Stars: {min(stars)} → {max(stars)} (avg {np.mean(stars):.0f}, consistency {consistency:.2f})")
        
        lines.append("")
    
    return lines

def _format_quality_analysis(quality_analysis: Dict[str, Any], detail_level: str = 'basic') -> str:
    """Format quality analysis with configurable detail."""
    lines = ["📊 **Image Quality Analysis**"]
    
    hfr_stats = quality_analysis.get('hfr_stats', {})
    if not hfr_stats:
        return ""
    
    # Basic HFR stats
    lines.append(f"🔧 HFR: {hfr_stats['min']:.2f} → {hfr_stats['max']:.2f} (avg {hfr_stats['mean']:.2f})")
    
    # Seeing condition
    seeing = quality_analysis.get('seeing_condition', 'Unknown')
    lines.append(f"👁️ Seeing Conditions: {seeing}")
    
    if detail_level in ['advanced', 'expert']:
        # Stability index
        stability = quality_analysis.get('hfr_stability_index', 0)
        lines.append(f"📈 HFR Stability: {stability:.3f} (lower is better)")
        
        # Trend analysis
        trend = quality_analysis.get('hfr_trend', {})
        if trend:
            direction = trend.get('trend_direction', 'stable')
            slope = trend.get('slope', 0)
            lines.append(f"📉 Trend: {direction} ({slope:+.4f}/frame)")
    
    if detail_level == 'expert':
        # Star detection consistency
        star_detection = quality_analysis.get('star_detection', {})
        if star_detection:
            consistency = star_detection.get('consistency_score', 0)
            lines.append(f"⭐ Star Detection Consistency: {consistency:.3f}")
    
    return "\n".join(lines)

def _format_performance_analysis(performance_analysis: Dict[str, Any], detail_level: str = 'basic') -> str:
    """Format performance analysis."""
    lines = ["🎯 **Performance Analysis**"]
    
    success_rate = performance_analysis.get('success_rate', 0)
    lines.append(f"✅ Success Rate: {success_rate*100:.1f}%")
    
    productivity = performance_analysis.get('productivity_score', 0)
    lines.append(f"📈 Productivity Score: {productivity:.0f}/100")
    
    if detail_level == 'expert':
        filter_perf = performance_analysis.get('filter_performance', {})
        if filter_perf:
            lines.append("🔍 **Filter Performance:**")
            for filt, stats in filter_perf.items():
                consistency = stats.get('hfr_consistency', 0)
                lines.append(f"   • {filt}: HFR {stats['avg_hfr']:.2f} (consistency {consistency:.2f})")
    
    return "\n".join(lines)

def _format_efficiency_analysis(efficiency_analysis: Dict[str, Any], detail_level: str = 'basic') -> str:
    """Format efficiency analysis."""
    lines = ["⚡ **Session Efficiency**"]
    
    efficiency = efficiency_analysis.get('imaging_efficiency', 0)
    lines.append(f"📸 Imaging Efficiency: {efficiency*100:.1f}%")
    
    if detail_level in ['detailed', 'expert']:
        imaging_time = efficiency_analysis.get('imaging_time_hours', 0)
        downtime = efficiency_analysis.get('downtime_hours', 0)
        
        lines.append(f"⏰ Imaging Time: {format_duration(imaging_time)}")
        lines.append(f"⏸️ Downtime: {format_duration(downtime)} ({efficiency_analysis.get('downtime_percentage', 0):.1f}%)")
        
        if detail_level == 'expert':
            avg_time = efficiency_analysis.get('avg_time_per_frame', 0)
            lines.append(f"📊 Avg Time/Frame: {avg_time:.0f}s")
    
    return "\n".join(lines)

def _format_temperature_analysis(temp_analysis: Dict[str, Any]) -> str:
    """Format detailed temperature analysis."""
    lines = ["🌡️ **Temperature Analysis**"]
    
    temp_stats = temp_analysis.get('temperature_stats', {})
    if temp_stats:
        stability = temp_analysis.get('thermal_stability_score', 0)
        lines.append(f"📊 Thermal Stability: {stability*100:.0f}% (Range: {temp_stats['range']:.1f}°C)")
    
    # Temperature-HFR correlation
    correlation = temp_analysis.get('temp_hfr_correlation', {})
    if correlation:
        corr_value = correlation.get('correlation', 0)
        significant = correlation.get('significant', False)
        sig_text = " (significant)" if significant else ""
        lines.append(f"📈 Temp-HFR Correlation: {corr_value:.3f}{sig_text}")
    
    return "\n".join(lines)

def _format_autofocus_analysis(autofocus_analysis: Dict[str, Any]) -> str:
    """Format autofocus analysis section."""
    lines = ["🎯 **Autofocus Analysis**"]
    
    total_sessions = autofocus_analysis.get('total_sessions', 0)
    lines.append(f"🔄 Sessions: {total_sessions}")
    
    by_filter = autofocus_analysis.get('by_filter', {})
    if by_filter:
        lines.append("🔍 **By Filter:**")
        for filt, stats in by_filter.items():
            avg_temp = stats.get('avg_temperature', 0)
            sessions = stats.get('sessions', 0)
            lines.append(f"   • {filt}: {sessions} sessions (avg temp {avg_temp:.1f}°C)")
    
    avg_interval = autofocus_analysis.get('avg_interval_minutes', 0)
    if avg_interval > 0:
        lines.append(f"⏱️ Avg Interval: {avg_interval:.0f} minutes")
    
    return "\n".join(lines)

def _format_comprehensive_alerts(advanced_metrics: Dict[str, Any]) -> str:
    """Format comprehensive alerts and recommendations."""
    lines = ["🤖 **Analysis & Recommendations**"]
    
    alerts = advanced_metrics.get('alerts', [])
    if alerts:
        for alert in alerts:
            severity_emoji = "🚨" if alert.get('severity') == 'error' else "⚠️"
            lines.append(f"{severity_emoji} {alert['message']}")
    
    # Add recommendations based on analysis
    quality = advanced_metrics.get('quality_analysis', {})
    if quality:
        seeing = quality.get('seeing_condition', '')
        if seeing == 'Poor':
            lines.append("💡 Consider waiting for better seeing conditions")
        elif seeing == 'Excellent':
            lines.append("🎉 Excellent conditions - great time for detailed imaging!")
    
    return "\n".join(lines) if len(lines) > 1 else ""

def _format_issues_summary(issues: List[Dict[str, Any]], alerts: List[Dict[str, Any]], detail_level: str = 'basic') -> str:
    """Format issues and alerts summary."""
    if not issues and not alerts:
        return ""
    
    lines = ["⚠️ **Issues & Alerts**"]
    
    # Original issues
    if issues:
        issue_counts = defaultdict(int)
        for issue in issues:
            issue_type = issue.get('type', 'unknown')
            issue_counts[issue_type] += 1
        
        for issue_type, count in issue_counts.items():
            if issue_type == 'capture_aborted':
                lines.append(f"❌ Aborted Captures: {count}")
            else:
                lines.append(f"⚠️ {issue_type.replace('_', ' ').title()}: {count}")
    
    # Advanced alerts
    if alerts:
        for alert in alerts:
            severity_emoji = "🚨" if alert.get('severity') == 'error' else "⚠️"
            lines.append(f"{severity_emoji} {alert['message']}")
    
    return "\n".join(lines) if len(lines) > 1 else ""

def generate_fallback_summary(fits_results: Dict) -> str:
    """Generate fallback summary when Ekos data is not available."""
    # This is the original FITS-based summary for compatibility
    try:
        from analyzer import generate_discord_summary
        return generate_discord_summary(fits_results)
    except ImportError:
        return "No data available for analysis."
