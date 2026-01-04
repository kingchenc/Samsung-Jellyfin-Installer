# WGT YouTube Patcher

Fixes **YouTube Error 153** on Samsung Tizen TVs by patching the Jellyfin Tizen WGT.

## The Problem

YouTube trailers fail on Samsung Tizen TVs with "Error 153" because YouTube now requires valid `Origin` or `Referer` HTTP headers. Since Tizen apps run via the `file://` protocol, these headers are missing.

## Available Patch Methods

### 1. Patrick's Method (Recommended)
Adds `origin` and `host` parameters to the YouTube playerVars configuration:
```javascript
playerVars: {
    origin: 'https://www.youtube.com',
    host: 'https://www.youtube.com'
}
```

### 2. Webserver/Proxy Method
- Injects a wrapper that intercepts YouTube API calls
- Adds `<meta name="referrer" content="origin">` to index.html
- Patches YT.Player constructor to add origin/host

### 3. Patrick + Webserver Combined
Applies both Patrick's and Webserver methods together.

### 4. YouTube NoCookie Domain
Replaces all `youtube.com` URLs with `youtube-nocookie.com`:
- Privacy-enhanced domain with different header requirements
- Patches embed URLs, iframe API, and origin references
- Scans all JS files in the WGT

### 5. Referrer Policy Fix
Adds comprehensive referrer policy headers:
- `<meta name="referrer" content="strict-origin-when-cross-origin">`
- Patches all iframes with `referrerpolicy` attribute
- Intercepts `document.createElement('iframe')` for future iframes

### 6. ALL-IN-ONE (Maximum Compatibility)
Applies ALL patches combined:
- Patrick's origin/host patch
- Webserver YT.Player wrapper
- NoCookie domain replacement
- Referrer policy fix

**Try this if nothing else works!**

## Usage

### GUI (Recommended)
```bash
python wgt_patcher_gui.py
```
Or double-click `run_patcher.bat` on Windows.

### Features
- Download latest WGT from GitHub releases
- Select specific WGT version from dropdown
- Use local WGT files without downloading
- Fast patching directly in ZIP (no extraction)
- Supports webpack-bundled WGTs (like GrayFix)

### Folder Structure
```
Youtube-Error-Patcher/
├── downloads/
│   ├── original/           # Downloaded/local WGT files
│   ├── patched_patrick/    # Patrick's method
│   ├── patched_webserver/  # Webserver method
│   ├── patched_combined/   # Patrick + Webserver
│   ├── patched_nocookie/   # NoCookie domain
│   ├── patched_referrer/   # Referrer policy
│   └── patched_allinone/   # ALL methods combined
├── wgt_patcher_gui.py      # Main GUI application
├── run_patcher.bat         # Windows launcher
├── requirements.txt        # Python requirements
└── README.md
```

## Requirements

- Python 3.8+
- tkinter (included with Python on most systems)

No external packages required!

## Related Issues

- [Samsung-Jellyfin-Installer #215](https://github.com/PatrickSt1991/Samsung-Jellyfin-Installer/issues/215)
- [jellyfin-tizen #374](https://github.com/jellyfin/jellyfin-tizen/issues/374)
- [YouTube Error 153 Analysis](https://til.simonwillison.net/youtube/fixing-153-embed)
