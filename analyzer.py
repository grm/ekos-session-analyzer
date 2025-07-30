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
                                         6.0 * np.ones(n_stars), 0.5)[0]
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
                    logging.debug(f"Skipping {fpath}: modification time {mtime} < cutoff {cutoff}")
                    continue
            except (OSError, ValueError):
                logging.debug(f"Skipping {fpath}: invalid modification time")
                continue  # skip files with invalid modification time
            
            # Then check DATE-OBS from FITS header for more precise filtering
            try:
                with fits.open(fpath) as hdul:
                    header = hdul[0].header
                    date_obs = parse_date_obs(header)
                    if not date_obs or date_obs < cutoff:
                        logging.debug(f"Skipping {fpath}: DATE-OBS {date_obs} < cutoff {cutoff}")
                        continue
            except Exception as e:
                logging.debug(f"Skipping {fpath}: error reading FITS header: {e}")
                continue  # skip unreadable files

            logging.debug(f"Analyzing {fpath}")
            res = analyze_fits_file(fpath)
            if res:
                key = (res["object"], res["filter"])
                results[key].append(res)
    return results

def generate_discord_summary(results):
    """Generate a Discord-friendly summary from the aggregated results."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"**Nightly Imaging Summary**\n📅 {now}\n"]
    
    # Generate global summary
    global_summary = generate_global_summary(results)
    lines.append(global_summary)
    lines.append("")  # Empty line for separation
    
    # Generate per-object summaries
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

def generate_global_summary(results):
    """Generate a global summary of the entire night's session."""
    if not results:
        return "🌙 No data available for this session."
    
    # Collect all data across all objects and filters
    all_entries = []
    total_frames = 0
    objects_count = len(results)
    
    for (obj, filt), entries in results.items():
        all_entries.extend(entries)
        total_frames += len(entries)
    
    if not all_entries:
        return "🌙 No valid data available for this session."
    
    # Calculate global statistics
    all_n_stars = [e["n_stars"] for e in all_entries]
    all_hfrs = [e["hfr"] for e in all_entries]
    all_eccs = [e["eccentricity"] for e in all_entries]
    
    # Calculate weighted averages (weighted by number of stars)
    total_stars = sum(all_n_stars)
    weighted_hfr = sum(hfr * stars for hfr, stars in zip(all_hfrs, all_n_stars)) / total_stars if total_stars > 0 else 0
    weighted_ecc = sum(ecc * stars for ecc, stars in zip(all_eccs, all_n_stars)) / total_stars if total_stars > 0 else 0
    
    # Get unique objects and filters
    unique_objects = set(e["object"] for e in all_entries)
    unique_filters = set(e["filter"] for e in all_entries)
    
    summary_lines = [
        f"🌙 **Global Session Summary**",
        f"📊 Total Frames: {total_frames}",
        f"🎯 Objects: {len(unique_objects)} ({', '.join(sorted(unique_objects))})",
        f"🔍 Filters: {len(unique_filters)} ({', '.join(sorted(unique_filters))})",
        f"⭐ Total Stars Detected: {total_stars:,}",
        f"",
        f"📈 **Overall Statistics**",
        f"   ⭐ Stars per frame: min {min(all_n_stars)} / max {max(all_n_stars)} / avg {np.mean(all_n_stars):.1f}",
        f"   🔧 HFR: min {min(all_hfrs):.2f} / max {max(all_hfrs):.2f} / avg {np.mean(all_hfrs):.2f} (weighted: {weighted_hfr:.2f})",
        f"   🔷 Eccentricity: min {min(all_eccs):.2f} / max {max(all_eccs):.2f} / avg {np.mean(all_eccs):.2f} (weighted: {weighted_ecc:.2f})",
        f""
    ]
    
    return "\n".join(summary_lines)

def send_discord_webhook(webhook_url, message):
    """Send the summary message to the specified Discord webhook."""
    try:
        resp = requests.post(webhook_url, json={"content": message})
        resp.raise_for_status()
    except Exception as e:
        logging.error(f"Failed to send Discord webhook: {e}")
        raise