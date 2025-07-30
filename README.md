# FITS Session Analyzer

A Python CLI application that analyzes FITS files from astronomical imaging sessions and sends automated summaries to Discord.

## Features

- 🔍 **Recursive FITS file discovery** in specified directories
- 📊 **Automatic star detection and analysis** using SEP (Source Extraction and Photometry)
- ⏰ **Time-based filtering** (configurable time window)
- 📈 **Statistical aggregation** by object and filter combinations
- 📱 **Discord integration** with formatted summaries
- 🛡️ **Robust error handling** for corrupted or invalid files

## Installation

### Prerequisites

- Python ≥ 3.9
- pipenv

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd astro-session-analyser
```

2. Install dependencies:
```bash
pipenv install
```

## Configuration

Create a configuration file (e.g., `config.yml`) with the following structure:

```yaml
folder: "/path/to/your/fits/files"
webhook: "https://discord.com/api/webhooks/your-webhook-url"
hours: 24
```

### Configuration Options

- `folder`: Root directory to recursively search for FITS files
- `webhook`: Discord webhook URL for sending summaries
- `hours`: Time window in hours (default: 24) - only files newer than `now - hours` will be analyzed

## Usage

Run the analyzer with your configuration file:

```bash
pipenv run python nightly_summary.py --config config.yml
```

### Example Output

```
**Nightly Imaging Summary**
📅 2025-01-15 06:00 UTC

📌 M31 - Luminance (5 frames)
   ⭐ Stars: min 1247 / max 1356 / avg 1298.4  
   🔧 HFR:   min 2.13 / max 2.22 / avg 2.19  
   🔷 Eccentricity:   min 0.31 / max 0.37 / avg 0.33

📌 NGC 7000 - Ha (3 frames)
   ⭐ Stars: min 891 / max 945 / avg 918.7  
   🔧 HFR:   min 1.95 / max 2.01 / avg 1.98  
   🔷 Eccentricity:   min 0.28 / max 0.32 / avg 0.30
```

## How It Works

### 1. File Discovery
- Recursively searches the specified folder for `.fits` and `.fit` files
- Validates file extensions before attempting to read

### 2. Time Filtering
- Extracts `DATE-OBS` from FITS headers
- Only processes files within the configured time window

### 3. Analysis Pipeline
For each valid FITS file:
- Loads image data as float32
- Performs background subtraction using SEP
- Detects stars using source extraction
- Calculates:
  - Number of detected stars
  - Half-Flux Radius (HFR) = 2 × flux_radius
  - Average eccentricity = 1 - (b/a)

### 4. Aggregation
- Groups results by (OBJECT + FILTER) combinations
- Calculates min/max/average statistics for each group

### 5. Discord Integration
- Formats results into a readable summary
- Sends to the configured Discord webhook

## Dependencies

- `astropy`: FITS file handling
- `sep`: Source extraction and photometry
- `numpy`: Numerical computations
- `requests`: HTTP requests for Discord webhook
- `pyyaml`: YAML configuration parsing

## Error Handling

The application gracefully handles:
- Corrupted or invalid FITS files
- Missing or malformed headers
- Network errors when sending to Discord
- Files without valid `DATE-OBS` fields
- Empty or invalid image data

## Development

### Project Structure

```
astro-session-analyser/
├── README.md
├── Pipfile
├── config_example.yml
├── nightly_summary.py      # CLI entry point
├── analyzer.py             # Core analysis logic
└── utils.py                # Configuration and logging utilities
```

### Adding Features

The modular design makes it easy to extend:
- Add new analysis metrics in `analyzer.py`
- Modify output formatting in `generate_discord_summary()`
- Add new configuration options in `utils.py`

## Troubleshooting

### Common Issues

1. **No files found**: Check the `folder` path in your config
2. **Discord webhook fails**: Verify the webhook URL is correct and active
3. **Memory errors**: Large FITS files may require more RAM
4. **Import errors**: Ensure all dependencies are installed with `pipenv install`

### Debug Mode

Enable detailed logging by modifying the logging level in `utils.py`:

```python
logging.basicConfig(level=logging.DEBUG, ...)
```

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here] 