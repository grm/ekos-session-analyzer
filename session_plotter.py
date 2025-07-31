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
            'autofocus_events': []
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
        
        return temporal_data
    
    def _create_plot(self, temporal_data: Dict[str, Any]) -> tuple:
        """Create the multi-axis temporal plot."""
        fig, ax1 = plt.subplots(figsize=self.figure_size)
        
        # Setup time axis
        session_start = temporal_data['session_start']
        if not session_start:
            raise ValueError("No session start time available")
        
        # Create additional axes
        ax2 = ax1.twinx()  # For guiding error
        ax3 = ax1.twinx() # For temperature
        
        # Offset the third axis
        ax3.spines['right'].set_position(('outward', 60))
        
        # Plot HFR data (scatter plot colored by filter)
        hfr_data = temporal_data['hfr_data']
        if hfr_data:
            filters = set(point['filter'] for point in hfr_data)
            filter_colors = {
                'R': '#FF6B6B', 'G': '#51CF66', 'B': '#339AF0',
                'H': '#FF8CC8', 'O': '#69DB7C', 'S': '#FFD43B',
                'L': '#CED4DA', 'Unknown': '#868E96'
            }
            
            for filt in filters:
                filt_data = [p for p in hfr_data if p['filter'] == filt]
                times = [p['time'] for p in filt_data]
                hfrs = [p['hfr'] for p in filt_data]
                
                color = filter_colors.get(filt, '#FF6B6B')
                ax1.scatter(times, hfrs, c=color, alpha=0.7, s=50, label=f'{filt} filter', zorder=3)
        
        # Plot guiding error (line plot with smoothing)
        guiding_data = temporal_data['guiding_data']
        if guiding_data:
            times = [p['time'] for p in guiding_data]
            errors = [p['error'] for p in guiding_data]
            
            # Smooth the guiding data using moving average
            if len(errors) > 10:
                window = min(50, len(errors) // 10)  # Adaptive window size
                errors_smooth = np.convolve(errors, np.ones(window)/window, mode='same')
                ax2.plot(times, errors_smooth, color=self.colors['guiding'], 
                        linewidth=1.5, alpha=0.8, label='Guiding Error', zorder=2)
            else:
                ax2.plot(times, errors, color=self.colors['guiding'], 
                        linewidth=1.5, alpha=0.8, label='Guiding Error', zorder=2)
        
        # Plot temperature (line plot)
        temp_data = temporal_data['temperature_data']
        if temp_data:
            times = [p['time'] for p in temp_data]
            temps = [p['temperature'] for p in temp_data]
            ax3.plot(times, temps, color=self.colors['temperature'], 
                    linewidth=2, alpha=0.9, label='Temperature', zorder=1)
        
        # Mark autofocus events
        af_events = temporal_data['autofocus_events']
        if af_events:
            for event in af_events:
                ax1.axvline(x=event['time'], color=self.colors['autofocus'], 
                           linestyle='--', alpha=0.6, linewidth=1)
        
        # Formatting
        self._format_axes(ax1, ax2, ax3, temporal_data)
        self._add_legends(ax1, ax2, ax3)
        self._add_title_and_labels(fig, ax1, ax2, ax3, temporal_data)
        
        # Grid
        ax1.grid(True, alpha=0.3, color=self.colors['grid'])
        
        plt.tight_layout()
        
        return fig, (ax1, ax2, ax3)
    
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
