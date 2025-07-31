"""
Nightly Ekos Session Analyzer - CLI Entrypoint
Specialized for Ekos/KStars analyze file support
"""
import sys
import os
import argparse
import logging
from utils import load_config, setup_logging, send_discord_message, send_discord_message_with_image
from ekos_analyzer import EkosAnalyzer
from ekos_discord_formatter import generate_ekos_discord_summary, ADVANCED_METRICS_AVAILABLE

# Try to import plotting functionality
try:
    from session_plotter import SessionPlotter
    PLOTTING_AVAILABLE = True
except ImportError as e:
    PLOTTING_AVAILABLE = False
    logging.debug(f"Plotting not available: {e}")

def main():
    parser = argparse.ArgumentParser(description="Analyze Ekos sessions and send a Discord summary.")
    parser.add_argument("-c", "--config", required=True, help="Path to config YAML file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose (debug) output")
    parser.add_argument("--dry-run", action="store_true", help="Generate summary without sending to Discord")
    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)
    if not config:
        print("❌ Failed to load config.")
        sys.exit(1)

    # Setup logging with config or verbose flag
    log_level = config.get("log_level", "INFO")
    if args.verbose:
        log_level = "DEBUG"
    setup_logging(verbose=(log_level == "DEBUG"))

    # Get configuration values
    hours = config.get("hours", 24)
    analyze_dir = config.get("analyze_dir")
    webhook_url = config.get("webhook")
    
    if not webhook_url:
        print("❌ No webhook URL configured.")
        sys.exit(1)

    print("🔭 Analyzing Ekos/KStars sessions...")
    
    try:
        # Initialize Ekos analyzer with configured directory
        ekos_analyzer = EkosAnalyzer(analyze_dir=analyze_dir)
        ekos_results = ekos_analyzer.analyze_folder(hours=hours)
        
        if not ekos_results or not ekos_results.get('capture_summary'):
            print("🌙 No Ekos session data found in the given time window.")
            sys.exit(0)
        
        print(f"✅ Found Ekos data with {ekos_results.get('total_captures', 0)} captures")
        
        # Generate Discord summary using unified formatter
        # The formatter automatically detects available features and configuration
        summary = generate_ekos_discord_summary(ekos_results, config)
        
        # Inform user about the mode being used
        report_level = config.get('discord_report_level', 'standard')
        should_use_advanced = (report_level == 'detailed' or 
                              config.get('advanced_analytics', {}).get('enabled', False))
        
        analytics_mode = "advanced analytics" if (should_use_advanced and ADVANCED_METRICS_AVAILABLE) else "basic analytics"
        print(f"📊 Using {report_level} report with {analytics_mode}")
        
        print("\n" + "="*50)
        print("SUMMARY:")
        print("="*50)
        print(summary)
        print("="*50 + "\n")
        
        # Generate session plot if enabled and available
        plot_path = None
        plot_enabled = config.get('plotting', {}).get('enabled', True)  # Default enabled
        
        if plot_enabled and PLOTTING_AVAILABLE:
            try:
                print("📈 Generating session plot...")
                plotter = SessionPlotter(config)
                plot_path = plotter.generate_session_plot(ekos_results)
                
                if plot_path:
                    print(f"✅ Session plot generated: {plot_path}")
                else:
                    print("⚠️ Could not generate session plot")
                    
            except Exception as e:
                logging.error(f"Error generating plot: {e}")
                print(f"⚠️ Plot generation failed: {e}")
        elif not PLOTTING_AVAILABLE and plot_enabled:
            print("⚠️ Plotting requested but matplotlib not available")
        
        # Send to Discord (unless dry-run)
        if args.dry_run:
            print("🧪 DRY-RUN MODE: Summary generated but not sent to Discord.")
            if plot_path:
                print(f"🧪 Plot would be sent: {plot_path}")
        else:
            if plot_path:
                send_discord_message_with_image(webhook_url, summary, plot_path)
                print("✅ Summary and plot sent to Discord.")
            else:
                send_discord_message(webhook_url, summary)
                print("✅ Summary sent to Discord.")
        
        # Clean up plot file after sending/dry-run
        if plot_path and os.path.exists(plot_path):
            try:
                os.remove(plot_path)
                logging.debug(f"Cleaned up plot file: {plot_path}")
                if args.dry_run:
                    print(f"🧹 Plot file cleaned up: {plot_path}")
            except Exception as e:
                logging.warning(f"Could not remove plot file {plot_path}: {e}")
        
    except Exception as e:
        logging.error(f"Analysis failed: {e}")
        print(f"❌ Analysis failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
