import os
import re
import urllib.request
import urllib.parse

# M3U Source URL
PLAYLIST_URL = "https://premiumplugx.com/VIP/pluglist.php"
TARGET_FILE = "custom.m3u"

# Marker tag to distinguish script-managed channels from your personal custom channels
AUTO_TAG = "#AUTO-FETCHED"

# List of target channel names (normalized to lowercase for robust matching)
TARGET_CHANNELS = [
    "Sony SAB"
]

def fetch_m3u():
    """
    Fetches raw M3U text with custom IPTV user-agent headers 
    to bypass browser-only Telegram redirects.
    """
    headers = {
        # Mimic OTT Navigator / ExoPlayer standard user-agent string
        "User-Agent": "playTV/7.1.1 (Linux;Android 13) - ExoPlayerLib/2.18.7",
        "Accept": "*/*",
        "Connection": "keep-alive"
    }
    
    req = urllib.request.Request(PLAYLIST_URL, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            content = response.read().decode('utf-8', errors='ignore')
            return content
    except Exception as e:
        print(f"Error fetching playlist: {e}")
        return None

def parse_m3u_channels(m3u_text):
    """
    Parses raw M3U playlist, extracts entries matching target channels,
    and tags them with AUTO_TAG so the script can safely manage them.
    """
    lines = m3u_text.splitlines()
    matched_entries = []
    
    current_entry_lines = []
    current_channel_name = None
    
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
            
        if line_str.startswith("#EXTINF"):
            # Start tracking new entry and inject the AUTO_TAG marker line
            current_entry_lines = [AUTO_TAG, line_str]
            
            # Extract channel name from tvg-name="..." or title after comma
            match_tvg = re.search(r'tvg-name=["\']([^"\']+)["\']', line_str, re.IGNORECASE)
            if match_tvg:
                current_channel_name = match_tvg.group(1).strip()
            else:
                # Fallback to name after last comma
                comma_split = line_str.split(",")
                current_channel_name = comma_split[-1].strip() if len(comma_split) > 1 else ""
                
        elif line_str.startswith("#"):
            # Extra metadata/header tags belonging to the channel block (e.g., #KODIPROP)
            if current_entry_lines:
                current_entry_lines.append(line_str)
                
        else:
            # Stream URL line
            if current_entry_lines:
                current_entry_lines.append(line_str)
                
                # Check if current_channel_name matches target list
                if current_channel_name:
                    norm_name = current_channel_name.lower().strip()
                    if any(target in norm_name for target in TARGET_CHANNELS):
                        matched_entries.append("\n".join(current_entry_lines))
                
                # Reset tracking for next channel
                current_entry_lines = []
                current_channel_name = None
                
    return matched_entries

def update_custom_m3u(extracted_entries):
    """
    Replaces ONLY previous auto-fetched channels in custom.m3u.
    Your custom channels (even with identical names) are kept 100% untouched.
    """
    header = '#EXTM3U x-tvg-url="https://tsepg.code9.workers.dev/epg.xml.gz,https://tsepg.code9.workers.dev/jio.xml.gz"\n'
    
    retained_blocks = []
    
    if os.path.exists(TARGET_FILE):
        with open(TARGET_FILE, "r", encoding="utf-8") as f:
            existing_content = f.read()

        # Split content into distinct blocks using #EXTINF as the delimiter
        blocks = re.split(r'(?=#EXTINF)', existing_content)
        
        for block in blocks:
            clean_block = block.strip()
            if not clean_block or clean_block.startswith("#EXTM3U"):
                continue
            
            # Check if this block was created by our script (contains #AUTO-FETCHED tag)
            is_auto_fetched = AUTO_TAG in clean_block
            
            # Keep the block if it is NOT marked as an auto-fetched entry
            if not is_auto_fetched:
                retained_blocks.append(clean_block)

    # Combine fresh entries first, followed by your custom entries
    all_entries = extracted_entries + retained_blocks
    new_content = header + "\n" + "\n\n".join(all_entries) + "\n"

    with open(TARGET_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"Successfully updated {TARGET_FILE} with {len(extracted_entries)} fresh channels. Retained {len(retained_blocks)} custom channels.")

if __name__ == "__main__":
    raw_m3u = fetch_m3u()
    if raw_m3u:
        extracted = parse_m3u_channels(raw_m3u)
        update_custom_m3u(extracted)
    else:
        print("Failed to update playlist.")
