# Installation Guide

This guide provides detailed instructions for installing the Invader Tracker integration in your Home Assistant setup.

## Prerequisites

Before installing, ensure you have:

- **Home Assistant** version 2024.1.0 or later
- **Administrator access** to your Home Assistant instance
- **Network connectivity** for external API access
- Your **Flash Invader UID** (if using Flash Invader features)

## Installation Methods

### Method 1: HACS (Recommended)

HACS (Home Assistant Community Store) is the easiest way to install community integrations.

#### Step 1: Install HACS

If you don't have HACS installed yet:

1. Visit [hacs.xyz](https://hacs.xyz/)
2. Follow the installation instructions for your setup (Docker, Home Assistant OS, manual, etc.)
3. Restart Home Assistant after HACS installation

#### Step 2: Add Custom Repository

1. Open Home Assistant and go to **Settings** → **Devices & Services**
2. Click the **HACS** button in the top right
3. Click **Integrations** in the left sidebar
4. Click the three-dot menu **⋯** in the top right
5. Select **Custom repositories**
6. Paste the URL: `https://github.com/Timothee-Rolland/HA-Invader-Tracker`
7. Select category: **Integration**
8. Click **CREATE**

#### Step 3: Install the Integration

1. Search for "Invader Tracker" in HACS
2. Click on the result
3. Click **INSTALL**
4. Restart Home Assistant

### Method 2: Manual Installation

For manual installation or if HACS is not available:

#### Step 1: Download

1. Go to [GitHub Releases](https://github.com/Timothee-Rolland/HA-Invader-Tracker/releases)
2. Download the latest `invader_tracker.zip`
3. Extract the archive

#### Step 2: Copy Files

1. Locate your Home Assistant `config` directory
2. Create directory: `config/custom_components/invader_tracker/`
3. Copy all files from the extracted archive into this directory

Your directory structure should look like:

```
config/
├── custom_components/
│   └── invader_tracker/
│       ├── __init__.py
│       ├── api/
│       ├── binary_sensor.py
│       ├── config_flow.py
│       ├── const.py
│       ├── coordinator.py
│       ├── exceptions.py
│       ├── manifest.json
│       ├── models.py
│       ├── processor.py
│       ├── sensor.py
│       ├── store.py
│       ├── strings.json
│       └── translations/
├── configuration.yaml
└── ...
```

#### Step 3: Restart Home Assistant

1. Go to **Settings** → **System** → **Restart**
2. Restart Home Assistant
3. Wait for it to come back online (~5-10 minutes)

### Verifying Installation

After installation, verify it was successful:

1. Go to **Settings** → **Devices & Services**
2. Click **+ Create Integration** or search for "Invader Tracker"
3. If you see "Invader Tracker" in the search results, installation was successful!

## Configuration

### Initial Setup

1. Go to **Settings** → **Devices & Services**
2. Click **+ Create Integration**
3. Search for and select **Invader Tracker**

### Step 1: Enter Your UID

You'll be prompted to enter your Flash Invader UID.

**What is a UID?**
- A unique identifier for your Flash Invader account
- Format: `XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX` (UUID v4)
- Used to fetch your personal flashed invaders

**How to find your UID:**

**Method A: Network Inspection (Recommended)**

1. Install a network proxy tool:
   - **iOS:** [Stream](https://www.streamapp.io/)
   - **Android:** [Fiddler](https://www.telerik.com/fiddler/fiddler-everywhere) or similar

2. Configure your phone to use the proxy

3. Open the Flash Invader app and refresh your gallery

4. Inspect network requests:
   - Look for requests to `api.space-invaders.com`
   - Find the `uid` query parameter in the URL
   - Copy the full UUID value

**Method B: Browser DevTools**

1. Open Flash Invader on web (if available)
2. Press F12 to open Developer Tools
3. Go to **Network** tab
4. Refresh the page
5. Look for API requests and find the `uid` parameter

**⚠️ Security Warning:**
Never share your UID publicly. It grants access to your Flash Invader account. If compromised, change it immediately in the Flash Invader app settings.

### Step 2: Enter Your Awazleon API Key (Optional)

After validating your UID, you'll be asked for an **Awazleon API key**:

- The key enables full invader data per city (status, points, install date) from [awazleon.space](https://www.awazleon.space/)
- **Leave it blank** to skip — the integration will still work using your Flash Invader personal data and the invader-spotter.art news feed, but city-level invader counts will be unavailable
- To obtain a key: request it at **[www.awazleon.space](https://www.awazleon.space/)** or via the **Space Invaders Discord server**
- You can add or change the key later via **Settings → Devices & Services → Invader Tracker → Configure**

### Step 3: Select Cities

After the API key step, you'll see a list of available cities (fetched from awazleon.space if a key was provided):

1. Select the cities you want to track (use Ctrl/Cmd for multiple selections)
2. You can change this later in integration options

**Recommendations:**
- Start with 1-2 cities for testing
- You can add more later without reconfiguring

### Step 3: Configure Update Intervals

Optional but recommended:

| Setting | Default | Range | Notes |
|---------|---------|-------|-------|
| **Scrape Interval** | 24 hours | 1-720 hours | How often to check invader-spotter.art for changes |
| **API Interval** | 1 hour | 1-24 hours | How often to check your Flash Invader data |
| **News Days** | 30 days | 7-365 days | How many days of news to track |

**Recommended Profiles:**

**Daily Hunters**
```
Scrape: 6-12 hours
API: 1 hour  
News: 30 days
```

**Casual Hunters**
```
Scrape: 24 hours
API: 6 hours
News: 30 days
```

**Weekly Check-ins**
```
Scrape: 168 hours (7 days)
API: 12 hours
News: 60 days
```

**Minimal Bandwidth**
```
Scrape: 720 hours (30 days)
API: 24 hours
News: 7 days
```

## Post-Installation

### Verify Configuration

1. Go to **Settings** → **Devices & Services**
2. You should see "Invader Tracker" in the list
3. Click on it to see discovered devices (one per city)
4. Each device has multiple sensors

### Check Entities

For each city, you'll see these sensors:

- `sensor.invader_*_total` - Total invaders
- `sensor.invader_*_flashed` - Invaders you've flashed
- `sensor.invader_*_unflashed` - Available targets
- `sensor.invader_*_unflashed_gone` - Missed opportunities
- `sensor.invader_*_new` - New/reactivated
- `sensor.invader_*_to_flash` - Invader IDs to flash (text list)
- `binary_sensor.invader_*_has_new` - New alert trigger

### Enable Debug Logging

To help troubleshoot, enable debug logging:

1. Open **Settings** → **System** → **Logs** section
2. In the log viewer, look for messages from `custom_components.invader_tracker`

Or add to `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.invader_tracker: debug
```

### Create First Automation

Create a simple notification automation to test:

1. Go to **Settings** → **Automations & Scenes**
2. Click **Create Automation**
3. Select "State" trigger
4. Choose `binary_sensor.invader_paris_has_new` (or your city)
5. Set trigger condition: "to" = "on"
6. Add notification action
7. Save and test!

## Troubleshooting Installation

### Integration Not Found in Search

**Solution:**
1. Hard refresh your browser (Ctrl+Shift+R or Cmd+Shift+R)
2. Restart Home Assistant via Settings → System → Restart
3. Check logs for errors in Developer Tools

### "UID Format Invalid" Error

**Solution:**
1. Verify UID format: `XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`
2. Check for extra spaces (copy carefully)
3. Ensure you have the UID, not the username

### "Cannot Connect" During Setup

**Solution:**
1. Verify internet connectivity
2. Check if invader-spotter.art is online
3. Check firewall/proxy settings
4. Try again after a few minutes

### "No Cities Found" Error

**Solution:**
1. Verify your Awazleon API key is entered and valid — without it, no city list can be fetched
2. Request a key at [www.awazleon.space](https://www.awazleon.space/) or via the Space Invaders Discord
3. Verify internet connectivity
4. Try again — awazleon.space may be temporarily down
5. Check GitHub issues for known problems

## Update Installation

### Updating from HACS

1. Open **HACS**
2. Go to **Integrations**
3. Find "Invader Tracker"
4. If an update is available, click **UPDATE**
5. Restart Home Assistant when prompted

### Updating Manual Installation

1. Download the latest version from GitHub Releases
2. Extract the archive
3. Copy files, overwriting existing ones
4. Restart Home Assistant
5. Configuration is preserved automatically

## Uninstallation

### HACS Uninstall

1. Open **HACS**
2. Find "Invader Tracker"
3. Click the three-dot menu
4. Select **Remove**
5. Restart Home Assistant

### Manual Uninstall

1. Delete `config/custom_components/invader_tracker/` directory
2. Restart Home Assistant
3. Go to **Settings** → **Devices & Services**
4. Find "Invader Tracker" entries and remove them

## Getting Help

If you encounter issues:

1. **Check logs:** **Settings** → **System** → **Logs**
2. **Review documentation:** See [README.md](../README.md)
3. **Open an issue:** [GitHub Issues](https://github.com/Timothee-Rolland/HA-Invader-Tracker/issues)
4. **Ask community:** [Home Assistant Forums](https://community.home-assistant.io/)

Include in your issue:
- Home Assistant version
- Integration version
- Error messages from logs
- Steps to reproduce

---

**Happy hunting! 🚀🎨**
