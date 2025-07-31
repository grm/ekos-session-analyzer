"""
Utils for config loading, logging and Discord messaging
"""
import yaml
import logging
import requests

def load_config(path):
    """Load YAML config file from the given path."""
    try:
        with open(path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logging.error(f"Error loading config: {e}")
        return None

def setup_logging(verbose=False):
    """Set up logging. If verbose is True, set level to DEBUG, else INFO."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

def send_discord_message(webhook_url, message):
    """Send a message to Discord via webhook."""
    payload = {"content": message}
    response = requests.post(webhook_url, json=payload)
    response.raise_for_status()
    logging.debug(f"Discord message sent successfully")
