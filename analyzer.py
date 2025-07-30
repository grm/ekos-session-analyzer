"""
FITS Analyzer Core Logic
"""
import os
import logging
from datetime import datetime, timedelta
from collections import defaultdict

import numpy as np
import sep
from astropy.io import fits
import requests

def is_fits_file(filename):
    """Check if the file has a .fits or .fit extension."""
    return filename.lower().endswith(('.fits', '.fit'))

def parse_date_obs(header):
    """Parse the DATE-OBS field from the FITS header as a datetime object."""
    try:
        return datetime.fromisoformat(header["DATE-OBS"].replace("Z", "+00:00"))
    except Exception:
        return None

def analyze_fits_file(path):
    """Analyze a single FITS file and extract relevant statistics."""
    try:
        with fits.open(path) as hdul:
            header = hdul[0].header
            data = hdul[0].data.astype(np.float32)
            date_obs = parse_date_obs(header)
            obj = header.get("OBJECT", "Unknown")
            filt = header.get("FILTER", "Unknown")

            # Background subtraction
            bkg = sep.Background(data)
            data_sub = data - bkg.back()
            objects = sep.extract(data_sub, 5, err=bkg.globalrms)

            n_stars = len(objects)
            if n_stars == 0:
                return None

            flux_radius = sep.flux_radius(data_sub, objects['x'], objects['y'],
                                         6.0 * np.ones(n_stars), 0.5, [0.5])[0]
            hfr = 2 * np.mean(flux_radius)
            a = objects['a']
            b = objects['b']
            eccentricity = np.mean(1 - (b / a))

            return {
                "object": obj,
                "filter": filt,
                "date_obs": date_obs,
                "n_stars": n_stars,
                "hfr": hfr,
                "eccentricity": eccentricity
            }
    except Exception as e:
        logging.warning(f"Error processing {path}: {e}")
        return None

def analyze_folder(folder, hours=24):
    """Recursively analyze all valid FITS files in the folder within the time window."""
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=hours)
    results = defaultdict(list)

    for root, _, files in os.walk(folder):
        for fname in files:
            if not is_fits_file(fname):
                continue
            fpath = os.path.join(root, fname)
            
            # First filter by file modification time (faster than opening FITS)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                if mtime < cutoff:
                    continue
            except (OSError, ValueError):
                continue  # skip files with invalid modification time
            
            # Then check DATE-OBS from FITS header for more precise filtering
            try:
                with fits.open(fpath) as hdul:
                    header = hdul[0].header
                    date_obs = parse_date_obs(header)
                    if not date_obs or date_obs < cutoff:
                        continue
            except Exception:
                continue  # skip unreadable files

            res = analyze_fits_file(fpath)
            if res:
                key = (res["object"], res["filter"])
                results[key].append(res)
    return results

def generate_discord_summary(results):
    """Generate a Discord-friendly summary from the aggregated results."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"**Nightly Imaging Summary**\n📅 {now}\n"]
    for (obj, filt), entries in results.items():
        n = len(entries)
        n_stars = [e["n_stars"] for e in entries]
        hfrs = [e["hfr"] for e in entries]
        eccs = [e["eccentricity"] for e in entries]
        lines.append(
            f"📌 {obj} - {filt} ({n} frames)\n"
            f"   ⭐ Stars: min {min(n_stars)} / max {max(n_stars)} / avg {np.mean(n_stars):.1f}  \n"
            f"   🔧 HFR:   min {min(hfrs):.2f} / max {max(hfrs):.2f} / avg {np.mean(hfrs):.2f}  \n"
            f"   🔷 Eccentricity:   min {min(eccs):.2f} / max {max(eccs):.2f} / avg {np.mean(eccs):.2f}\n"
        )
    return "\n".join(lines)

def send_discord_webhook(webhook_url, message):
    """Send the summary message to the specified Discord webhook."""
    try:
        resp = requests.post(webhook_url, json={"content": message})
        resp.raise_for_status()
    except Exception as e:
        logging.error(f"Failed to send Discord webhook: {e}")
        raise