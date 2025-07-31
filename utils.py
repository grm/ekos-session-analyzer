"""
Utils for config loading, logging and Discord messaging
"""
import yaml
import logging
import requests
import os

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

def send_discord_message_with_image(webhook_url, message, image_path=None):
    """Send a message to Discord via webhook with optional image attachment."""
    try:
        payload = {"content": message}
        files = {}
        
        if image_path and os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                files['file'] = (os.path.basename(image_path), f.read(), 'image/png')
        
        if files:
            # Send with file attachment
            response = requests.post(webhook_url, data=payload, files=files)
        else:
            # Send text only
            response = requests.post(webhook_url, json=payload)
        
        response.raise_for_status()
        logging.debug(f"Discord message with image sent successfully")
        
    except Exception as e:
        logging.error(f"Error sending Discord message: {e}")
        # Fallback to text-only message
        send_discord_message(webhook_url, message)
