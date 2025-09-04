"""
Session Plotter for Ekos Astrophotography Analysis
Generates temporal plots showing HFR, guiding, and temperature evolution
"""
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import numpy as np
import logging
from typing import Dict, List, Any, Optional
import os
from pathlib import Path

class SessionPlotter:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.plot_config = self.config.get('plotting', {})
        
        # Get pixel scale configuration for accurate guide quality zones
        imaging_setup = self.config.get('imaging_setup', {})
        self.pixel_scale_arcsec = imaging_setup.get('pixel_scale_arcsec')
        self.guide_quality_thresholds = self.config.get('alert_thresholds', {}).get('guide_quality', {
            'excellent_px': 0.5,
            'good_px': 1.0,
            'average_px': 1.5
        })
        
        # Default plot settings
        self.figure_size = self.plot_config.get('figure_size', (12, 8))
        self.dpi = self.plot_config.get('dpi', 100)
        self.style = self.plot_config.get('style', 'dark_background')
        
        # Colors for different metrics
        self.colors = {
            'hfr': '#FF6B6B',           # Red for HFR
            'guiding': '#4ECDC4',       # Teal for guiding
            'temperature': '#FFE66D',   # Yellow for temperature
            'autofocus': '#95E1D3',     # Light green for autofocus events
            'grid': '#333333'           # Dark gray for grid
        }
        
    def generate_session_plot(self, session_data: Dict[str, Any], output_path: str = None) -> Optional[str]:
        """
        Generate a temporal plot of the astrophotography session.
        Returns the path to the generated image file.
        """
        try:
            # Set matplotlib style
            if self.style == 'dark_background':
                plt.style.use('dark_background')
            
            # Extract temporal data
            temporal_data = self._extract_temporal_data(session_data)
            
            if not temporal_data:
                logging.warning("No temporal data available for plotting")
                return None
            
            # Create the plot
            fig, axes = self._create_plot(temporal_data)
            
            # Save the plot
            if output_path is None:
                output_path = self._get_default_output_path()
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Save with optimized settings for Discord
            fig.savefig(
                output_path,
                dpi=self.dpi,
                bbox_inches='tight',
                facecolor='#2F3136' if self.style == 'dark_background' else 'white',
                edgecolor='none',
                format='png'
            )
            
            plt.close(fig)
            logging.info(f"Session plot saved to: {output_path}")
            
            return output_path
            
        except Exception as e:
            logging.error(f"Error generating session plot: {e}")
            return None
    
    def _extract_temporal_data(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and organize temporal data from session."""
        temporal_data = {
            'session_start': None,
            'hfr_data': [],
            'guiding_data': [],
            'temperature_data': [],
            'autofocus_events': [],
            'capture_events': []
        }
        
        sessions = session_data.get('sessions', [])
        if not sessions:
            return temporal_data
        
        # Process each session
        for session in sessions:
            session_start_str = session.get('session_start')
            if not session_start_str:
                continue
            
            # Parse session start time
            try:
                if '.' in session_start_str:
                    session_start_str = session_start_str.split('.')[0]
                session_start = datetime.strptime(session_start_str, '%Y-%m-%d %H:%M:%S')
                temporal_data['session_start'] = session_start
            except ValueError:
                logging.debug(f"Could not parse session start: {session_start_str}")
                continue
            
            # Extract HFR data from completed captures
            for capture in session.get('captures', []):
                if capture.get('event') == 'complete' and capture.get('hfr'):
                    timestamp = capture.get('timestamp', 0)
                    capture_time = session_start + timedelta(seconds=timestamp)
                    temporal_data['hfr_data'].append({
                        'time': capture_time,
                        'hfr': capture['hfr'],
                        'filter': capture.get('filter', 'Unknown')
                    })
            
            # Extract guiding data
            for guide_stat in session.get('guide_stats', []):
                timestamp = guide_stat.get('timestamp', 0)
                guide_time = session_start + timedelta(seconds=timestamp)
                # Calculate real distance from dx,dy
                dx = guide_stat.get('dx', 0)
                dy = guide_stat.get('dy', 0)
                distance = (dx**2 + dy**2)**0.5
                temporal_data['guiding_data'].append({
                    'time': guide_time,
                    'error': distance,
                    'dx': dx,
                    'dy': dy
                })
            
            # Extract temperature data
            for temp_reading in session.get('temperature_readings', []):
                timestamp = temp_reading.get('timestamp', 0)
                temp_time = session_start + timedelta(seconds=timestamp)
                temporal_data['temperature_data'].append({
                    'time': temp_time,
                    'temperature': temp_reading['temperature']
                })
            
            # Extract autofocus events
            for af_session in session.get('autofocus_sessions', []):
                if af_session.get('event') == 'complete':
                    timestamp = af_session.get('timestamp', 0)
                    af_time = session_start + timedelta(seconds=timestamp)
                    temporal_data['autofocus_events'].append({
                        'time': af_time,
                        'filter': af_session.get('filter', 'Unknown'),
                        'temperature': af_session.get('temperature')
                    })
            
            # Extract ALL capture events (for sessions without HFR data)
            for capture in session.get('captures', []):
                timestamp = capture.get('timestamp', 0)
                capture_time = session_start + timedelta(seconds=timestamp)
                temporal_data['capture_events'].append({
                    'time': capture_time,
                    'filter': capture.get('filter', 'Unknown'),
                    'status': capture.get('event', 'unknown'),  # complete, starting, etc.
                    'exposure': capture.get('exposure', 0)
                })
            
            # Also add aborted captures from issues
            for issue in session.get('issues', []):
                if issue.get('type') == 'capture_aborted':
                    timestamp = issue.get('timestamp', 0)
                    issue_time = session_start + timedelta(seconds=timestamp)
                    temporal_data['capture_events'].append({
                        'time': issue_time,
                        'filter': 'Unknown',  # Issues don't typically have filter info
                        'status': 'aborted',
                        'exposure': issue.get('exposure', 0)
                    })
        
        return temporal_data
    
    def _create_plot(self, temporal_data: Dict[str, Any]) -> tuple:
        """Create the multi-panel temporal plot with logical organization."""
        session_start = temporal_data['session_start']
        if not session_start:
            raise ValueError("No session start time available")
        
        # Determine the number of subplots needed based on available data
        hfr_data = temporal_data['hfr_data']
        guiding_data = temporal_data['guiding_data']
        temp_data = temporal_data['temperature_data']
        
        # Create subplot configuration
        subplot_count = 0
        if hfr_data: subplot_count += 1
        if guiding_data: subplot_count += 1
        if temp_data: subplot_count += 1
        
        if subplot_count == 0:
            subplot_count = 1  # At least show capture events
        
        # Create subplots with logical vertical arrangement
        fig, axes = plt.subplots(subplot_count, 1, figsize=(12, 3 * subplot_count), 
                                sharex=True)
        
        if subplot_count == 1:
            axes = [axes]  # Ensure axes is always a list
        
        current_ax = 0
        
        # Plot 1: HFR Evolution (most important for image quality)
        if hfr_data:
            ax_hfr = axes[current_ax]
            self._plot_hfr_data(ax_hfr, hfr_data)
            current_ax += 1
        
        # Plot 2: Guiding Performance (second most important)
        if guiding_data:
            ax_guide = axes[current_ax]
            self._plot_guiding_data(ax_guide, guiding_data)
            current_ax += 1
        
        # Plot 3: Temperature Evolution (environmental conditions)
        if temp_data:
            ax_temp = axes[current_ax]
            self._plot_temperature_data(ax_temp, temp_data)
            current_ax += 1
        
        # Mark autofocus events on all plots
        af_events = temporal_data['autofocus_events']
        if af_events and current_ax > 0:
            for i in range(current_ax):
                for event in af_events:
                    axes[i].axvline(x=event['time'], color=self.colors['autofocus'], 
                                   linestyle='--', alpha=0.6, linewidth=1)
        
        # Format all axes
        self._format_time_axis(axes[-1])  # Only bottom axis gets time labels
        for i, ax in enumerate(axes):
            ax.grid(True, alpha=0.3, color=self.colors['grid'])
        
        # Add overall title and session info
        self._add_session_title(fig, temporal_data)
        
        plt.tight_layout()
        plt.subplots_adjust(hspace=0.3)  # Add space between subplots
        
        return fig, axes
    
    def _plot_hfr_data(self, ax, hfr_data):
        """Plot HFR evolution by filter."""
        # Group by filter
        filters = set(point['filter'] for point in hfr_data)
        filter_colors = {
            'R': '#FF6B6B', 'G': '#51CF66', 'B': '#339AF0',
            'H': '#FF8CC8', 'O': '#69DB7C', 'S': '#FFD43B',
            'L': '#CED4DA', 'Unknown': '#868E96'
        }
        
        for filt in sorted(filters):
            filt_data = [p for p in hfr_data if p['filter'] == filt]
            times = [p['time'] for p in filt_data]
            hfrs = [p['hfr'] for p in filt_data]
            
            color = filter_colors.get(filt, '#868E96')
            
            # Plot as both scatter and line for better visibility
            ax.scatter(times, hfrs, c=color, alpha=0.8, s=60, zorder=3)
            if len(times) > 1:
                ax.plot(times, hfrs, c=color, alpha=0.5, linewidth=1, label=f'{filt} filter')
        
        ax.set_ylabel('HFR (pixels)', fontsize=11, color=self.colors['hfr'])
        ax.set_title('🔧 Image Quality (HFR) Evolution', fontsize=12, pad=10)
        ax.tick_params(axis='y', labelcolor=self.colors['hfr'])
        
        # Add HFR statistics
        if hfr_data:
            hfr_values = [p['hfr'] for p in hfr_data]
            hfr_min, hfr_max, hfr_avg = min(hfr_values), max(hfr_values), np.mean(hfr_values)
            ax.text(0.02, 0.95, f'Min: {hfr_min:.2f} | Max: {hfr_max:.2f} | Avg: {hfr_avg:.2f}', 
                   transform=ax.transAxes, verticalalignment='top', fontsize=9, 
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7))
        
        ax.legend(loc='upper right', framealpha=0.9)
    
    def _plot_guiding_data(self, ax, guiding_data):
        """Plot guiding performance evolution."""
        times = [p['time'] for p in guiding_data]
        errors = [p['error'] for p in guiding_data]
        
        # Plot raw data as light scatter
        ax.scatter(times, errors, c=self.colors['guiding'], alpha=0.3, s=10, zorder=1)
        
        # Plot smoothed trend line
        if len(errors) > 20:
            window = min(50, len(errors) // 10)
            errors_smooth = np.convolve(errors, np.ones(window)/window, mode='same')
            ax.plot(times, errors_smooth, color=self.colors['guiding'], 
                   linewidth=2, alpha=0.9, label='Smoothed trend', zorder=2)
        
        # Add quality zones (pixel-scale-based if available)
        if self.pixel_scale_arcsec and self.pixel_scale_arcsec > 0:
            # Convert pixel thresholds to arcsecond thresholds for plotting
            excellent_arcsec = self.guide_quality_thresholds['excellent_px'] * self.pixel_scale_arcsec
            good_arcsec = self.guide_quality_thresholds['good_px'] * self.pixel_scale_arcsec
            average_arcsec = self.guide_quality_thresholds['average_px'] * self.pixel_scale_arcsec
            
            ax.axhspan(0, excellent_arcsec, alpha=0.1, color='green', 
                      label=f'Excellent (<{self.guide_quality_thresholds["excellent_px"]:.1f}px)')
            ax.axhspan(excellent_arcsec, good_arcsec, alpha=0.1, color='yellow', 
                      label=f'Good (<{self.guide_quality_thresholds["good_px"]:.1f}px)')
            ax.axhspan(good_arcsec, average_arcsec, alpha=0.1, color='orange', 
                      label=f'Average (<{self.guide_quality_thresholds["average_px"]:.1f}px)')
        else:
            # Fallback to legacy arcsecond-based zones
            ax.axhspan(0, 1.0, alpha=0.1, color='green', label='Excellent (<1″)')
            ax.axhspan(1.0, 2.0, alpha=0.1, color='yellow', label='Good (1-2″)')
            ax.axhspan(2.0, 3.0, alpha=0.1, color='orange', label='Average (2-3″)')
        
        ax.set_ylabel('Guiding Error (arcsec)', fontsize=11, color=self.colors['guiding'])
        ax.set_title('📈 Guiding Performance Evolution', fontsize=12, pad=10)
        ax.tick_params(axis='y', labelcolor=self.colors['guiding'])
        
        # Add guiding statistics
        if guiding_data:
            errors_filtered = [e for e in errors if e <= 10.0]  # Remove outliers
            if errors_filtered:
                guide_min, guide_max, guide_avg = min(errors_filtered), max(errors_filtered), np.mean(errors_filtered)
                ax.text(0.02, 0.95, f'Min: {guide_min:.2f}″ | Max: {guide_max:.2f}″ | Avg: {guide_avg:.2f}″', 
                       transform=ax.transAxes, verticalalignment='top', fontsize=9,
                       bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7))
        
        # Set reasonable Y-axis limit (exclude extreme outliers)
        if errors:
            errors_p95 = np.percentile(errors, 95)  # 95th percentile
            ax.set_ylim(0, min(errors_p95 * 1.2, 5.0))  # Cap at 5 arcsec for readability
        
        ax.legend(loc='upper right', framealpha=0.9, fontsize=9)
    
    def _calculate_guide_quality_from_distance(self, avg_distance_arcsec: float) -> str:
        """
        Calculate guide quality rating using pixel-scale-based thresholds.
        Same logic as in EkosAnalyzer for consistency.
        """
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
            if avg_distance_arcsec < 1.0:
                return "Excellent"
            elif avg_distance_arcsec < 2.0:
                return "Good"
            elif avg_distance_arcsec < 3.0:
                return "Average"
            else:
                return "Poor"
    
    def _plot_temperature_data(self, ax, temp_data):
        """Plot temperature evolution."""
        times = [p['time'] for p in temp_data]
        temps = [p['temperature'] for p in temp_data]
        
        # Plot temperature as area plot for better visibility
        ax.plot(times, temps, color=self.colors['temperature'], 
               linewidth=2, alpha=0.9, label='Temperature')
        ax.fill_between(times, temps, alpha=0.2, color=self.colors['temperature'])
        
        ax.set_ylabel('Temperature (°C)', fontsize=11, color=self.colors['temperature'])
        ax.set_title('🌡️ Temperature Evolution', fontsize=12, pad=10)
        ax.tick_params(axis='y', labelcolor=self.colors['temperature'])
        
        # Add temperature statistics
        if temp_data:
            temp_min, temp_max, temp_avg = min(temps), max(temps), np.mean(temps)
            temp_range = temp_max - temp_min
            ax.text(0.02, 0.95, f'Range: {temp_range:.1f}°C | Min: {temp_min:.1f}°C | Max: {temp_max:.1f}°C', 
                   transform=ax.transAxes, verticalalignment='top', fontsize=9,
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7))
        
        ax.legend(loc='upper right', framealpha=0.9)
    
    def _format_time_axis(self, ax):
        """Format the time axis (only for bottom subplot)."""
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
        ax.xaxis.set_minor_locator(mdates.MinuteLocator(interval=30))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        ax.set_xlabel('Time', fontsize=11)
    
    def _add_session_title(self, fig, temporal_data):
        """Add overall session title and summary."""
        session_start = temporal_data['session_start']
        session_date = session_start.strftime('%Y-%m-%d')
        
        # Calculate session duration
        all_times = []
        for data_type in ['hfr_data', 'guiding_data', 'temperature_data']:
            if temporal_data.get(data_type):
                all_times.extend([p['time'] for p in temporal_data[data_type]])
        
        if all_times:
            session_duration = (max(all_times) - min(all_times)).total_seconds() / 3600
            duration_str = f"({session_duration:.1f}h)"
        else:
            duration_str = ""
        
        fig.suptitle(f'📡 Astrophotography Session Analysis - {session_date} {duration_str}', 
                    fontsize=14, fontweight='bold', y=0.98)
        
        # Add performance summary at the bottom
        summary_parts = []
        
        if temporal_data['hfr_data']:
            hfr_values = [p['hfr'] for p in temporal_data['hfr_data']]
            hfr_avg = np.mean(hfr_values)
            summary_parts.append(f'🔧 HFR: {hfr_avg:.2f}px')
        
        if temporal_data['guiding_data']:
            errors = [p['error'] for p in temporal_data['guiding_data']]
            errors_filtered = [e for e in errors if e <= 10.0]
            if errors_filtered:
                guide_avg = np.mean(errors_filtered)
                # Use pixel-scale-based quality assessment
                guide_quality = self._calculate_guide_quality_from_distance(guide_avg)
                summary_parts.append(f'📈 Guide: {guide_avg:.2f}″ ({guide_quality})')
        
        if temporal_data['temperature_data']:
            temps = [p['temperature'] for p in temporal_data['temperature_data']]
            temp_range = max(temps) - min(temps)
            stability = "Stable" if temp_range < 2 else "Variable"
            summary_parts.append(f'🌡️ Temp: {stability} (Δ{temp_range:.1f}°C)')
        
        if temporal_data['autofocus_events']:
            af_count = len(temporal_data['autofocus_events'])
            summary_parts.append(f'🎯 Autofocus: {af_count} sessions')
        
        if summary_parts:
            fig.text(0.5, 0.02, ' | '.join(summary_parts), ha='center', 
                    fontsize=10, alpha=0.8)
    
    def _format_axes(self, ax1, ax2, ax3, temporal_data):
        """Format the axes with appropriate ranges and ticks."""
        # Time axis formatting
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax1.xaxis.set_major_locator(mdates.HourLocator(interval=1))
        ax1.xaxis.set_minor_locator(mdates.MinuteLocator(interval=30))
        
        # Rotate time labels
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
        
        # Set colors for y-axis labels
        ax1.tick_params(axis='y', labelcolor=self.colors['hfr'])
        ax2.tick_params(axis='y', labelcolor=self.colors['guiding'])
        ax3.tick_params(axis='y', labelcolor=self.colors['temperature'])
        
        # Set y-axis label colors
        ax1.yaxis.label.set_color(self.colors['hfr'])
        ax2.yaxis.label.set_color(self.colors['guiding'])
        ax3.yaxis.label.set_color(self.colors['temperature'])
        
        # Set appropriate ranges
        if temporal_data['hfr_data']:
            hfr_values = [p['hfr'] for p in temporal_data['hfr_data']]
            ax1.set_ylim(min(hfr_values) * 0.9, max(hfr_values) * 1.1)
        
        if temporal_data['guiding_data']:
            guide_values = [p['error'] for p in temporal_data['guiding_data']]
            ax2.set_ylim(0, max(guide_values) * 1.2)
        
        if temporal_data['temperature_data']:
            temp_values = [p['temperature'] for p in temporal_data['temperature_data']]
            temp_range = max(temp_values) - min(temp_values)
            ax3.set_ylim(min(temp_values) - temp_range * 0.1, 
                        max(temp_values) + temp_range * 0.1)
    
    def _add_legends(self, ax1, ax2, ax3):
        """Add legends for each axis."""
        # Combine all legends
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        lines3, labels3 = ax3.get_legend_handles_labels()
        
        if lines1 or lines2 or lines3:
            ax1.legend(lines1 + lines2 + lines3, labels1 + labels2 + labels3, 
                      loc='upper left', framealpha=0.9)
    
    def _add_title_and_labels(self, fig, ax1, ax2, ax3, temporal_data):
        """Add title and axis labels."""
        session_start = temporal_data['session_start']
        session_date = session_start.strftime('%Y-%m-%d')
        
        fig.suptitle(f'Astrophotography Session Analysis - {session_date}', 
                    fontsize=14, fontweight='bold')
        
        ax1.set_xlabel('Time', fontsize=12)
        ax1.set_ylabel('HFR (pixels)', fontsize=12)
        ax2.set_ylabel('Guiding Error (arcsec)', fontsize=12)
        ax3.set_ylabel('Temperature (°C)', fontsize=12)
        
        # Add summary text
        if temporal_data['hfr_data']:
            hfr_values = [p['hfr'] for p in temporal_data['hfr_data']]
            hfr_min = min(hfr_values)
            hfr_max = max(hfr_values)
            hfr_avg = sum(hfr_values) / len(hfr_values)
            
            summary_text = f'HFR: {hfr_min:.2f} → {hfr_max:.2f} (avg {hfr_avg:.2f})'
            
            if temporal_data['guiding_data']:
                guide_values = [p['error'] for p in temporal_data['guiding_data']]
                guide_avg = sum(guide_values) / len(guide_values)
                summary_text += f' | Guide: {guide_avg:.2f}″'
            
            if temporal_data['temperature_data']:
                temp_values = [p['temperature'] for p in temporal_data['temperature_data']]
                temp_min = min(temp_values)
                temp_max = max(temp_values)
                summary_text += f' | Temp: {temp_min:.1f}→{temp_max:.1f}°C'
            
            fig.text(0.5, 0.02, summary_text, ha='center', fontsize=10, alpha=0.8)
    
    def _get_default_output_path(self) -> str:
        """Get default output path for the plot."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = self.plot_config.get('output_dir', './plots')
        return os.path.join(output_dir, f'session_analysis_{timestamp}.png')
