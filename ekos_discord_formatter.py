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

def generate_ekos_discord_summary(ekos_data: Dict[str, Any], config: Dict[str, Any] = None) -> List[str]:
    """Generate Discord-friendly summary(s) from Ekos session data with automatic message splitting."""
    if not ekos_data or ekos_data.get('total_captures', 0) == 0:
        return ["🌙 No Ekos session data available for this period."]
    
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
        return [_generate_minimal_report(ekos_data, advanced_metrics, config)]
    elif report_level == 'detailed':
        return _generate_detailed_report_fragments(ekos_data, advanced_metrics, config)
    else:  # standard or default
        standard_result = _generate_standard_report(ekos_data, advanced_metrics, config)
        # Handle both single string and list of strings from standard report
        if isinstance(standard_result, list):
            return standard_result
        else:
            return [standard_result]

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

def _generate_standard_report(ekos_data: Dict[str, Any], advanced_metrics: Dict[str, Any], config: Dict[str, Any]) -> List[str]:
    """Generate standard report with intelligent splitting if needed."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    
    # Build header and basic sections
    header_lines = [f"**🔭 Ekos Session Summary**\n📅 {now}\n"]
    
    # Session overview
    header_lines.append(_format_session_overview(ekos_data, advanced_metrics))
    header_lines.append("")
    
    # Always add session conditions
    conditions_summary = generate_conditions_summary(ekos_data)
    if conditions_summary:
        header_lines.append(conditions_summary)
        header_lines.append("")
    
    # CRUCIAL: Add guiding summary (always show - most important for astrophotography)
    # Try both legacy guide_stats and new filter_analysis structure
    guide_summary = generate_guide_summary(ekos_data.get('guide_stats', {}))
    if not guide_summary:
        # Extract from filter_analysis if legacy structure not available
        guide_summary = extract_guide_summary_from_filter_analysis(ekos_data.get('filter_analysis', {}))
    
    if guide_summary:
        header_lines.append(guide_summary)
        header_lines.append("")
    
    # Build footer sections
    footer_lines = []
    
    # Always add autofocus summary
    autofocus_summary = generate_autofocus_summary(ekos_data.get('autofocus_stats', {}))
    if autofocus_summary:
        footer_lines.append(autofocus_summary)
        footer_lines.append("")
    
    # Quality summary if advanced metrics available
    if advanced_metrics.get('quality_analysis'):
        footer_lines.append(_format_quality_analysis(advanced_metrics['quality_analysis'], 'basic'))
        footer_lines.append("")
    
    # Issues and alerts
    issues_summary = _format_issues_summary(ekos_data.get('issues_summary', []), advanced_metrics.get('alerts', []))
    if issues_summary:
        footer_lines.append(issues_summary)
    
    # NEW: Check if we need intelligent splitting for filter analysis
    filter_analysis = ekos_data.get('filter_analysis', {})
    if filter_analysis:
        # Calculate space used by header and footer
        header_content = "\n".join(header_lines)
        footer_content = "\n".join(footer_lines)
        fixed_content_length = len(header_content) + len(footer_content) + 100  # +100 for spacing
        
        # Check if filter analysis needs splitting
        filter_summary = generate_filter_analysis_summary(filter_analysis, ekos_data.get('capture_summary', {}))
        
        # Test the complete message length without truncation to decide if splitting is needed
        complete_test_message = header_content + "\n\n" + filter_summary
        if footer_content:
            complete_test_message += "\n\n" + footer_content
        
        # Use validate_discord_message with allow_oversized=True to get accurate length without truncation
        from utils import validate_discord_message
        validated_test = validate_discord_message(complete_test_message, allow_oversized=True)
        
        if len(validated_test) > 1900:  # Discord limit with margin
            # Use intelligent splitting
            messages = []
            
            # First message: Header + conditions + guide
            first_message = header_content
            if len(first_message) < 1900:
                messages.append(first_message)
            
            # Filter analysis messages (split intelligently between filters)
            filter_messages = split_filter_analysis_intelligently(filter_analysis)
            messages.extend(filter_messages)
            
            # Final message: Footer content
            if footer_lines and len(footer_content) > 10:
                footer_message = f"**🔭 Session Summary (Final)**\n\n{footer_content}"
                if len(footer_message) < 1900:
                    messages.append(footer_message)
            
            return messages
        else:
            # Single message fits
            all_content = header_content + "\n\n" + filter_summary
            if footer_content:
                all_content += "\n\n" + footer_content
            return [all_content]
    else:
        # Fallback to legacy filter guide summary if new analysis not available
        filter_guide_summary = generate_filter_guide_summary(ekos_data.get('filter_guide_stats', {}))
        if filter_guide_summary:
            header_lines.append(filter_guide_summary)
            header_lines.append("")
        
        # Single message
        all_content = "\n".join(header_lines)
        if footer_lines:
            all_content += "\n" + "\n".join(footer_lines)
        return [all_content]

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
    
    # NEW: Add detailed guiding by filter for detailed reports
    filter_guide_summary = generate_filter_guide_summary(ekos_data.get('filter_guide_stats', {}))
    if filter_guide_summary:
        lines.append("")
        lines.append(filter_guide_summary)
    
    # NEW: Add detailed session breakdown by filter for detailed reports
    detailed_filter_sessions = generate_detailed_filter_sessions(ekos_data.get('detailed_sessions', {}))
    if detailed_filter_sessions:
        lines.append("")
        lines.append(detailed_filter_sessions)
    
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

def _generate_detailed_report_fragments(ekos_data: Dict[str, Any], advanced_metrics: Dict[str, Any], config: Dict[str, Any]) -> List[str]:
    """Generate detailed report split into multiple messages to respect Discord limits."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    fragments = []
    
    # Fragment 1: Main Summary
    fragment1_lines = [f"**🔬 Detailed Ekos Analysis (1/3)**\n📅 {now}\n"]
    fragment1_lines.append(_format_session_overview(ekos_data, advanced_metrics, detail_level='detailed'))
    fragment1_lines.append("")
    fragment1_lines.extend(_format_capture_details(ekos_data, 'detailed'))
    
    # Quality analysis if available
    if advanced_metrics.get('quality_analysis'):
        fragment1_lines.append("")
        fragment1_lines.append(_format_quality_analysis(advanced_metrics['quality_analysis'], 'detailed'))
    
    # Session conditions
    conditions_summary = generate_conditions_summary(ekos_data)
    if conditions_summary:
        fragment1_lines.append("")
        fragment1_lines.append(conditions_summary)
    
    fragments.append("\n".join(fragment1_lines))
    
    # Fragment 2: Guiding Analysis  
    fragment2_lines = [f"**🎯 Guiding Analysis (2/3)**\n"]
    
    # Global guiding summary
    guide_summary = generate_guide_summary(ekos_data.get('guide_stats', {}))
    if not guide_summary:
        # Extract from filter_analysis if legacy structure not available
        guide_summary = extract_guide_summary_from_filter_analysis(ekos_data.get('filter_analysis', {}))
    
    if guide_summary:
        fragment2_lines.append(guide_summary)
        fragment2_lines.append("")
    
    # NEW: Use comprehensive filter analysis with sub-sessions for detailed reports
    filter_analysis_summary = generate_filter_analysis_summary(ekos_data.get('filter_analysis', {}))
    if filter_analysis_summary:
        fragment2_lines.append(filter_analysis_summary)
        fragment2_lines.append("")
    else:
        # Fallback to legacy structures if new analysis not available
        filter_guide_summary = generate_filter_guide_summary(ekos_data.get('filter_guide_stats', {}))
        if filter_guide_summary:
            fragment2_lines.append(filter_guide_summary)
            fragment2_lines.append("")
        
        # Detailed session breakdown by filter (legacy)
        detailed_filter_sessions = generate_detailed_filter_sessions(ekos_data.get('detailed_sessions', {}))
        if detailed_filter_sessions:
            fragment2_lines.append(detailed_filter_sessions)
    
    fragments.append("\n".join(fragment2_lines))
    
    # Fragment 3: Technical Analysis & Alerts
    fragment3_lines = [f"**🤖 Technical Analysis (3/3)**\n"]
    
    # Autofocus summary
    autofocus_summary = generate_autofocus_summary(ekos_data.get('autofocus_stats', {}))
    if autofocus_summary:
        fragment3_lines.append(autofocus_summary)
        fragment3_lines.append("")
    
    # Temperature analysis
    if advanced_metrics.get('temperature_analysis'):
        fragment3_lines.append(_format_temperature_analysis(advanced_metrics['temperature_analysis']))
        fragment3_lines.append("")
    
    # Detailed autofocus analysis
    if advanced_metrics.get('autofocus_analysis'):
        fragment3_lines.append(_format_autofocus_analysis(advanced_metrics['autofocus_analysis']))
        fragment3_lines.append("")
    
    # Issues and alerts
    issues_summary = _format_issues_summary(ekos_data.get('issues_summary', []), advanced_metrics.get('alerts', []), detail_level='detailed')
    if issues_summary:
        fragment3_lines.append(issues_summary)
        fragment3_lines.append("")
    
    # Comprehensive alerts and recommendations
    comprehensive_alerts = _format_comprehensive_alerts(advanced_metrics)
    if comprehensive_alerts:
        fragment3_lines.append(comprehensive_alerts)
    
    fragments.append("\n".join(fragment3_lines))
    
    return fragments


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
    # Check both legacy guide_stats and new filter_analysis structure
    if guide_stats and guide_stats.get('total_measurements'):
        # Legacy structure
        total_measurements = guide_stats['total_measurements']
        avg_distance = guide_stats.get('avg_distance', 0)
        guide_quality = guide_stats.get('guide_quality', 'Unknown')
        ra_error = guide_stats.get('avg_ra_error', 0)
        dec_error = guide_stats.get('avg_dec_error', 0)
    else:
        # Try to extract from ekos_data structure passed in context
        return ""
    
    lines = ["🌟 **Guiding Performance**"]
    
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
    if ra_error > 0 or dec_error > 0:
        lines.append(f"📈 RA: {ra_error:.2f}″ | DEC: {dec_error:.2f}″")
    
    return "\n".join(lines)


def extract_guide_summary_from_filter_analysis(filter_analysis: Dict[str, Any]) -> str:
    """Extract overall guiding summary from filter analysis structure."""
    if not filter_analysis:
        return ""
    
    # Aggregate guide stats across all filters
    total_measurements = 0
    all_distances = []
    all_qualities = []
    
    for filter_name, analysis in filter_analysis.items():
        global_guide = analysis.get('global_guide_stats', {})
        if global_guide.get('total_measurements', 0) > 0:
            measurements = global_guide['total_measurements']
            distance = global_guide.get('avg_distance', 0)
            quality = global_guide.get('guide_quality', 'Unknown')
            
            total_measurements += measurements
            if distance > 0:
                # Weight by number of measurements
                for _ in range(measurements):
                    all_distances.append(distance)
            all_qualities.append(quality)
    
    if total_measurements == 0:
        return ""
    
    # Calculate weighted average
    avg_distance = sum(all_distances) / len(all_distances) if all_distances else 0
    
    # Determine overall quality (take the most common, or worst if tied)
    quality_counts = {}
    for quality in all_qualities:
        quality_counts[quality] = quality_counts.get(quality, 0) + 1
    
    if quality_counts:
        # Get most common quality, but prefer worse quality if tied
        quality_priority = {'Poor': 0, 'Average': 1, 'Good': 2, 'Excellent': 3}
        sorted_qualities = sorted(quality_counts.items(), 
                                key=lambda x: (-x[1], quality_priority.get(x[0], 4)))
        overall_quality = sorted_qualities[0][0]
    else:
        overall_quality = 'Unknown'
    
    lines = ["🌟 **Guiding Performance**"]
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
    
    emoji = quality_emoji.get(overall_quality, '⚪')
    lines.append(f"{emoji} Guide Quality: {overall_quality}")
    
    return "\n".join(lines)

def generate_filter_analysis_blocks(filter_analysis: Dict[str, Any], capture_summary: Dict = None) -> List[Dict[str, Any]]:
    """Generate comprehensive capture details blocks grouped by object then by filter."""
    if not filter_analysis:
        return []
    
    # Use capture_summary for HFR/Stars data if available
    capture_summary = capture_summary or {}
    
    # First, group filters by object
    objects_data = {}
    
    for filter_name, analysis in filter_analysis.items():
        if analysis.get('total_captures', 0) == 0:
            continue
        
        # Extract object name from sub-sessions or use default
        object_name = "NGC 7380"  # Default object
        sub_sessions = analysis.get('sub_sessions', [])
        if sub_sessions:
            # Try to get object name from first sub-session if available
            first_sub = sub_sessions[0]
            object_name = first_sub.get('object_name', 'NGC 7380')
        
        # Group by object
        if object_name not in objects_data:
            objects_data[object_name] = {}
        
        objects_data[object_name][filter_name] = analysis
    
    blocks = []
    
    # Sort objects by total captures across all filters
    object_totals = {}
    for obj_name, filters_data in objects_data.items():
        total_captures = sum(f.get('total_captures', 0) for f in filters_data.values())
        object_totals[obj_name] = total_captures
    
    sorted_objects = sorted(object_totals.items(), key=lambda x: x[1], reverse=True)
    
    for object_name, total_obj_captures in sorted_objects:
        if total_obj_captures == 0:
            continue
            
        # Build object block
        object_lines = []
        object_lines.append(f"🎯 **{object_name}**")
        
        filters_data = objects_data[object_name]
        
        # Sort filters within object by captures (most used first) 
        sorted_filters = sorted(filters_data.items(), 
                              key=lambda x: x[1].get('total_captures', 0), reverse=True)
        
        for filter_name, analysis in sorted_filters:
            total_captures = analysis.get('total_captures', 0)
            total_duration = analysis.get('total_duration_hours', 0)
            exposure_time = int(analysis.get('exposure_time', 0))
            total_sub_sessions = analysis.get('total_sub_sessions', 0)
            
            # Global guide stats
            global_guide = analysis.get('global_guide_stats', {})
            avg_distance = global_guide.get('avg_distance', 0)
            quality = global_guide.get('guide_quality', 'Unknown')
            
            # Quality emoji
            quality_emoji = {
                'Excellent': '🟢',
                'Good': '🟡', 
                'Average': '🟠',
                'Poor': '🔴',
                'No Data': '⚪'
            }
            emoji = quality_emoji.get(quality, '⚪')
            
            # Duration formatting (use exact format like "1h 10m")
            if total_duration >= 1:
                hours = int(total_duration)
                minutes = int((total_duration - hours) * 60)
                if minutes > 0:
                    duration_str = f"{hours}h {minutes}m"
                else:
                    duration_str = f"{hours}h"
            else:
                minutes = int(total_duration * 60)
                duration_str = f"{minutes}m"
            
            # Filter header with exposure format like "7x600s"
            exposure_format = f"{total_captures}×{exposure_time}s"
            object_lines.append(f"📌 {filter_name} Filter ({exposure_format}, {duration_str})")
            
            # Extract real HFR/Stars data from capture_summary
            filter_captures = []
            if capture_summary:
                for (obj, filt), captures in capture_summary.items():
                    if filt == filter_name:
                        filter_captures.extend(captures)
            
            # Calculate real statistics from capture data
            if filter_captures:
                # HFR statistics (display first if available)
                hfrs = [c['hfr'] for c in filter_captures if c.get('hfr') is not None and c['hfr'] > 0]
                if hfrs:
                    hfr_min = min(hfrs)
                    hfr_max = max(hfrs)
                    hfr_avg = np.mean(hfrs)
                    hfr_std = np.std(hfrs)
                    
                    object_lines.append(f"   🔧 HFR: {hfr_min:.2f} → {hfr_max:.2f} (avg {hfr_avg:.2f}, σ {hfr_std:.2f})")
                    object_lines.append(f"   📐 FWHM: {hfr_min*2.35:.2f} → {hfr_max*2.35:.2f} (avg {hfr_avg*2.35:.2f}, σ {hfr_std*2.35:.2f})")
                
                # Stars statistics
                stars = [c['stars'] for c in filter_captures if c.get('stars') is not None and c['stars'] > 0]
                if stars:
                    stars_min = min(stars)
                    stars_max = max(stars)
                    stars_avg = np.mean(stars)
                    stars_consistency = 1 - (np.std(stars) / max(np.mean(stars), 1))
                    
                    object_lines.append(f"   ⭐ Stars: {stars_min} → {stars_max} (avg {stars_avg:.0f}, consistency {stars_consistency:.2f})")
                
                # If no HFR data, provide technical explanation
                if not hfrs:
                    object_lines.append(f"   🔧 HFR: Data not available")
                    object_lines.append(f"   📐 FWHM: Data not available")
            
            # Global guide performance
            object_lines.append(f"   📈 Guide: {avg_distance:.2f}″ {emoji}{quality}")
            object_lines.append(f"   📋 Sub-sessions: {total_sub_sessions}")
            
            # Show detailed sub-sessions with all stats
            sub_sessions = analysis.get('sub_sessions', [])
            for sub in sub_sessions:
                sub_id = sub.get('sub_session_id', 0)
                start_time = sub.get('start_time_formatted', '??:??')
                end_time = sub.get('end_time_formatted', '??:??')
                capture_count = sub.get('capture_count', 0)
                sub_exposure = int(sub.get('exposure_time', 0))
                duration_minutes = sub.get('duration_minutes', 0)
                
                # Format duration for sub-session
                if duration_minutes >= 60:
                    hours = int(duration_minutes / 60)
                    mins = int(duration_minutes % 60)
                    if mins > 0:
                        sub_duration_str = f"{hours}h {mins}m"
                    else:
                        sub_duration_str = f"{hours}h"
                else:
                    sub_duration_str = f"{duration_minutes:.0f}m"
                
                # Sub-session header
                sub_format = f"{capture_count}×{sub_exposure}s"
                object_lines.append(f"     #{sub_id}: {start_time}→{end_time} ({sub_duration_str}) | {sub_format}")
                
                # Sub-session guide stats
                sub_guide = sub.get('guide_stats', {})
                sub_avg_distance = sub_guide.get('avg_distance', 0)
                sub_quality = sub_guide.get('guide_quality', 'No Data')
                guide_measurements = sub_guide.get('measurements', 0)
                
                if sub_avg_distance > 0:
                    sub_emoji = quality_emoji.get(sub_quality, '⚪')
                    object_lines.append(f"          📈 Guide: {sub_avg_distance:.2f}″ {sub_emoji}{sub_quality}")
                else:
                    object_lines.append(f"          📈 Guide: No data available")
                
                # Calculate real sub-session capture quality stats from individual captures
                sub_captures = sub.get('captures', [])
                if sub_captures:
                    # Calculate HFR statistics for this sub-session 
                    sub_hfrs = [c['hfr'] for c in sub_captures if c.get('hfr') is not None and c['hfr'] > 0.1]
                    if sub_hfrs:
                        sub_hfr_min = min(sub_hfrs)
                        sub_hfr_max = max(sub_hfrs)
                        sub_hfr_avg = np.mean(sub_hfrs)
                        
                        object_lines.append(f"          🔧 HFR: {sub_hfr_min:.2f} → {sub_hfr_max:.2f} (avg {sub_hfr_avg:.2f})")
                        object_lines.append(f"          📐 FWHM: {sub_hfr_min*1.2:.2f} → {sub_hfr_max*1.2:.2f} (avg {sub_hfr_avg*1.2:.2f})")
                    else:
                        object_lines.append(f"          🔧 HFR: No measurements in sub-session")
                        object_lines.append(f"          📐 FWHM: No measurements in sub-session")
                    
                    # Calculate Stars statistics for this sub-session
                    sub_stars = [c['stars'] for c in sub_captures if c.get('stars') is not None and c['stars'] > 0]
                    if sub_stars:
                        sub_stars_min = min(sub_stars)
                        sub_stars_max = max(sub_stars)
                        sub_stars_avg = np.mean(sub_stars)
                        sub_stars_consistency = 1 - (np.std(sub_stars) / max(np.mean(sub_stars), 1))
                        
                        object_lines.append(f"         ⭐ Stars: {sub_stars_min} → {sub_stars_max} (avg {sub_stars_avg:.0f}, consistency {sub_stars_consistency:.2f})")
                    else:
                        object_lines.append(f"         ⭐ Stars: Data not available")
                else:
                    object_lines.append(f"          🔧 HFR: No capture data")
                    object_lines.append(f"          📐 FWHM: No capture data")
                    object_lines.append(f"         ⭐ Stars: No capture data")
            
            # Add spacing between filters
            object_lines.append("")
        
        # Create block for this object (with all its filters)
        block_content = "\n".join(object_lines)
        blocks.append({
            'object_name': object_name,
            'content': block_content,
            'char_count': len(block_content),
            'priority': total_obj_captures,  # For sorting by total captures
            'filter_count': len(filters_data)
        })
    
    return blocks

def generate_filter_analysis_summary(filter_analysis: Dict[str, Any], capture_summary: Dict = None) -> str:
    """Generate comprehensive capture details with HFR, FWHM, Stars and Guide data."""
    blocks = generate_filter_analysis_blocks(filter_analysis, capture_summary)
    if not blocks:
        return ""
    
    lines = ["📊 **Capture Details**"]
    for block in blocks:
        lines.append("")
        lines.append(block['content'])
    
    return "\n".join(lines)

def split_filter_analysis_intelligently(filter_analysis: Dict[str, Any], header: str = "📊 **Capture Details**") -> List[str]:
    """Split filter analysis into multiple messages, cutting cleanly between objects/filters."""
    blocks = generate_filter_analysis_blocks(filter_analysis)
    if not blocks:
        return [f"{header}\n\nNo filter data available."]
    
    messages = []
    current_message_lines = [header, ""]
    current_char_count = len(header) + 2  # +2 for newlines
    
    for i, object_block in enumerate(blocks):
        object_content = object_block['content']
        object_char_count = len(object_content)
        
        # Calculate total if we add this object to current message
        potential_total = current_char_count + object_char_count + 2  # +2 for newlines
        
        # If adding this object would exceed Discord limit, finalize current message
        if potential_total > 1900 and len(current_message_lines) > 2:  # More than just header
            # Finalize current message
            messages.append('\n'.join(current_message_lines))
            
            # Start new message
            message_number = len(messages) + 1
            current_message_lines = [f"{header} ({message_number})", "", object_content]
            current_char_count = len(f"{header} ({message_number})") + 2 + object_char_count
        else:
            # Add object to current message
            if len(current_message_lines) > 2:  # Not first object in message
                current_message_lines.append("")  # Add spacing between objects
                current_char_count += 1
            
            current_message_lines.append(object_content)
            current_char_count += object_char_count
    
    # Add final message if it has content
    if len(current_message_lines) > 2:
        messages.append('\n'.join(current_message_lines))
    
    return messages if messages else [f"{header}\n\nNo filter data available."]

def _split_object_by_filters(object_block: Dict[str, Any], header: str, existing_messages_count: int) -> List[str]:
    """Split a large object block into multiple messages by separating filters."""
    object_name = object_block['object_name']
    object_content = object_block['content']
    
    # Parse the object content to separate by filters
    lines = object_content.split('\n')
    
    messages = []
    current_filter_lines = []
    current_char_count = 0
    
    # Find object header line
    object_header = ""
    filter_blocks = []
    current_filter_block = []
    
    in_filter = False
    
    for line in lines:
        if line.startswith('🎯 **'):
            object_header = line
            continue
        elif line.startswith('📌') and 'Filter' in line:
            # New filter starts
            if current_filter_block:
                # Save previous filter
                filter_blocks.append('\n'.join(current_filter_block))
            current_filter_block = [line]
            in_filter = True
        elif in_filter and line.strip():
            current_filter_block.append(line)
        elif not line.strip() and in_filter:
            # Empty line might be end of filter or just spacing
            current_filter_block.append(line)
    
    # Add last filter
    if current_filter_block:
        filter_blocks.append('\n'.join(current_filter_block))
    
    # Now split filters across messages
    current_message_lines = []
    if existing_messages_count == 0:
        current_message_lines = [header, "", object_header]
        current_char_count = len('\n'.join(current_message_lines))
    else:
        message_number = existing_messages_count + 1
        current_message_lines = [f"{header} ({message_number})", "", object_header]
        current_char_count = len('\n'.join(current_message_lines))
    
    for i, filter_block in enumerate(filter_blocks):
        filter_with_spacing = f"\n{filter_block}"
        filter_char_count = len(filter_with_spacing)
        
        # Check if adding this filter would exceed Discord limit
        if current_char_count + filter_char_count > 1900:
            # Finalize current message
            if len(current_message_lines) > 2:  # More than just header + object
                messages.append('\n'.join(current_message_lines))
            
            # Start new message
            message_number = existing_messages_count + len(messages) + 1
            current_message_lines = [f"{header} ({message_number})", "", f"🎯 **{object_name}** (continued)"]
            current_char_count = len('\n'.join(current_message_lines))
        
        # Add filter to current message
        current_message_lines.append("")
        current_message_lines.append(filter_block.strip())
        current_char_count += filter_char_count
    
    # Add final message
    if len(current_message_lines) > 2:
        messages.append('\n'.join(current_message_lines))
    
    return messages

def generate_filter_guide_summary(filter_guide_stats: Dict[str, Any]) -> str:
    """Generate guiding performance summary by filter - LEGACY COMPATIBILITY."""
    if not filter_guide_stats:
        return ""
    
    lines = ["🎯 **Guiding by Filter (Legacy)**"]
    
    # Sort filters by total measurements (most used first)
    sorted_filters = sorted(filter_guide_stats.items(), 
                          key=lambda x: x[1].get('total_measurements', 0), reverse=True)
    
    for filter_name, stats in sorted_filters:
        if stats.get('total_measurements', 0) == 0:
            continue
            
        avg_distance = stats.get('avg_distance', 0)
        quality = stats.get('guide_quality', 'Unknown')
        total_measurements = stats.get('total_measurements', 0)
        sessions_count = stats.get('total_sessions', 0)
        
        # Quality emoji
        quality_emoji = {
            'Excellent': '🟢',
            'Good': '🟡', 
            'Average': '🟠',
            'Poor': '🔴',
            'No Data': '⚪'
        }
        emoji = quality_emoji.get(quality, '⚪')
        
        lines.append(f"🔍 **{filter_name}**: {avg_distance:.2f}″ {emoji}{quality}")
        lines.append(f"   📊 {total_measurements} points, {sessions_count} sessions")
        
        # Add RMS if available and meaningful
        avg_rms = stats.get('avg_rms', 0)
        if avg_rms > 0:
            lines.append(f"   📈 RMS: {avg_rms:.2f}″")
    
    return "\n".join(lines)

def generate_detailed_filter_sessions(detailed_sessions: Dict[str, List[Dict]]) -> str:
    """Generate detailed session breakdown by filter - NEW FEATURE."""
    if not detailed_sessions:
        return ""
    
    lines = ["📁 **Session Details by Filter**"]
    
    # Sort filters by total capture count
    filter_totals = {}
    for filter_name, sessions in detailed_sessions.items():
        total_captures = sum(s.get('capture_count', 0) for s in sessions)
        filter_totals[filter_name] = total_captures
    
    sorted_filters = sorted(filter_totals.items(), key=lambda x: x[1], reverse=True)
    
    for filter_name, total_caps in sorted_filters:
        if total_caps == 0:
            continue
            
        sessions = detailed_sessions[filter_name]
        lines.append(f"")
        lines.append(f"🎯 **{filter_name} Filter** ({len(sessions)} sessions, {total_caps} captures):")
        
        # Sort sessions by capture count (longest first)
        sorted_sessions = sorted(sessions, key=lambda x: x.get('capture_count', 0), reverse=True)
        
        for i, session in enumerate(sorted_sessions):
            session_idx = session.get('session_index', 0)
            capture_count = session.get('capture_count', 0)
            duration_min = session.get('duration_minutes', 0)
            guide_points = session.get('guide_data_points', 0)
            
            # Format duration
            if duration_min >= 60:
                duration_str = f"{duration_min/60:.1f}h"
            else:
                duration_str = f"{duration_min:.0f}m"
            
            lines.append(f"  📋 Session {session_idx + 1}: {capture_count} captures, {duration_str}")
            
            # Add guide performance if available
            guide_stats = session.get('guide_stats', {})
            if guide_stats and guide_stats.get('avg_distance', 0) > 0:
                avg_distance = guide_stats['avg_distance']
                quality = guide_stats.get('guide_quality', 'Unknown')
                lines.append(f"     🎯 Guide: {avg_distance:.2f}″ ({quality}, {guide_points} pts)")
            elif guide_points == 0:
                lines.append(f"     📊 No guiding data")
    
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
    
    # Calculate filter-specific failure statistics
    filter_failures = _calculate_filter_failures(ekos_data)
    
    for (obj, filt), captures in capture_summary.items():
        if not captures:
            continue
        
        n_frames = len(captures)
        
        # Calculate statistics based on detail level
        hfrs = [c['hfr'] for c in captures if c.get('hfr') is not None]
        stars = [c['stars'] for c in captures if c.get('stars') is not None and c['stars'] > 0]
        exposures = [c['exposure'] for c in captures if c.get('exposure') is not None]
        
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
        
        # Detect problematic session (no valid HFR data and no/few stars detected)
        has_quality_data = len(hfrs) > 0 or len(stars) > 0
        
        if has_quality_data:
            # Normal session with quality data
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
        else:
            # Problematic session - show technical issues instead of useless stats
            all_stars = [c.get('stars', 0) for c in captures]
            all_hfrs = [c.get('hfr') for c in captures]
            none_hfr_count = sum(1 for hfr in all_hfrs if hfr is None)
            zero_stars_count = sum(1 for stars in all_stars if stars == 0)
            
            if none_hfr_count == len(captures):
                lines.append(f"   ⚠️ No HFR measurements (possible plate solving issues)")
            if zero_stars_count == len(captures):
                lines.append(f"   ⚠️ No stars detected (possible exposure/focus issues)")
            
            # Show filter-specific success rate if there were failed captures
            filter_key = f"{obj}_{filt}"
            filter_failed = filter_failures.get(filter_key, 0)
            if filter_failed > 0:
                success_rate = (n_frames / (n_frames + filter_failed)) * 100
                lines.append(f"   📊 Success rate: {success_rate:.1f}% ({filter_failed} failed)")
        
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

def _calculate_filter_failures(ekos_data: Dict[str, Any]) -> Dict[str, int]:
    """Calculate failure statistics by filter/object combination."""
    filter_failures = defaultdict(int)
    
    # Analyze issues by extracting context from the issue data
    issues_summary = ekos_data.get('issues_summary', [])
    sessions = ekos_data.get('sessions', [])
    
    # Extract failure context from sessions
    for session in sessions:
        for issue in session.get('issues', []):
            if issue.get('type') == 'capture_aborted':
                # Try to extract object/filter context from issue
                # Issues might have context like object or filter information
                obj_name = issue.get('object', 'Unknown')
                filter_name = issue.get('filter', 'Unknown')
                
                # If not directly available, try to infer from timestamp context
                if obj_name == 'Unknown' or filter_name == 'Unknown':
                    # Find nearest capture event to get context
                    issue_timestamp = issue.get('timestamp', 0)
                    nearest_capture = None
                    min_time_diff = float('inf')
                    
                    for capture in session.get('captures', []):
                        time_diff = abs(capture.get('timestamp', 0) - issue_timestamp)
                        if time_diff < min_time_diff:
                            min_time_diff = time_diff
                            nearest_capture = capture
                    
                    if nearest_capture:
                        obj_name = nearest_capture.get('object', obj_name)  
                        filter_name = nearest_capture.get('filter', filter_name)
                
                filter_key = f"{obj_name}_{filter_name}"
                filter_failures[filter_key] += 1
    
    # Fallback: if no specific context, distribute failures proportionally
    # This handles cases where issue context is not available
    if not filter_failures and issues_summary:
        capture_summary = ekos_data.get('capture_summary', {})
        total_aborted = len([i for i in issues_summary if i.get('type') == 'capture_aborted'])
        
        if total_aborted > 0 and capture_summary:
            # Distribute failures proportionally to filter usage
            total_captures = sum(len(captures) for captures in capture_summary.values())
            
            for (obj, filt), captures in capture_summary.items():
                filter_key = f"{obj}_{filt}"
                proportion = len(captures) / total_captures if total_captures > 0 else 0
                filter_failures[filter_key] = int(total_aborted * proportion)
    
    return dict(filter_failures)

def generate_fallback_summary(fits_results: Dict) -> str:
    """Generate fallback summary when Ekos data is not available."""
    # This is the original FITS-based summary for compatibility
    try:
        from analyzer import generate_discord_summary
        return generate_discord_summary(fits_results)
    except ImportError:
        return "No data available for analysis."
