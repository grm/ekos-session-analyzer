"""
Nightly FITS Session Analyzer - CLI Entrypoint
"""
import sys
import argparse
from utils import load_config, setup_logging
from analyzer import analyze_folder, generate_discord_summary, send_discord_webhook

def main():
    parser = argparse.ArgumentParser(description="Analyze FITS files and send a Discord summary.")
    parser.add_argument("-c", "--config", required=True, help="Path to config YAML file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose (debug) output")
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)
    config = load_config(args.config)
    if not config:
        print("❌ Failed to load config.")
        sys.exit(1)

    results = analyze_folder(
        folder=config["folder"],
        hours=config.get("hours", 24)
    )
    if not results:
        print("🌙 No valid FITS files found in the given time window. No summary sent to Discord.")
        sys.exit(0)

    summary = generate_discord_summary(results)
    print(summary)
    try:
        send_discord_webhook(config["webhook"], summary)
        print("✅ Summary sent to Discord.")
    except Exception as e:
        print(f"❌ Failed to send Discord webhook: {e}")

if __name__ == "__main__":
    main()