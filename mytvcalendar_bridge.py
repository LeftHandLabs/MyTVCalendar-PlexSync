import os
import json
import time
import uuid
import requests
import urllib.parse

# --- CONFIGURATION ---
PLEX_URL = "http://172.20.30.50:32400"
CONFIG_FILE = "mytvcalendar_config.json"
MYTVCALENDAR_API = "https://mytvcalendar.com/api/plex-plugin"

PLEX_APP_HEADERS = {
    "X-Plex-Client-Identifier": "",  # Filled dynamically
    "X-Plex-Product": "MyTVCalendar Plex Bridge",
    "X-Plex-Version": "1.2.0",
    "X-Plex-Device": "Server Daemon",
    "X-Plex-Platform": "Python",
    "Accept": "application/json"
}

class MyTVCalendarBridge:
    def __init__(self):
        self.guid = None
        self.plex_token = None
        self.is_linked = False
        self.historical_synced = False
        self.active_sessions = {}
        
        self.load_or_create_config()
        PLEX_APP_HEADERS["X-Plex-Client-Identifier"] = self.guid

    def load_or_create_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    self.guid = config.get("guid")
                    self.plex_token = config.get("plex_token")
                    self.historical_synced = config.get("historical_synced", False)
                    print(f"[*] Config loaded. GUID: {self.guid}")
            except Exception as e:
                print(f"[!] Error reading config file: {e}")

        if not self.guid:
            self.guid = str(uuid.uuid4())
            self.save_config()
            print(f"[*] Generated new permanent device GUID: {self.guid}")

    def save_config(self):
        config = {
            "guid": self.guid,
            "plex_token": self.plex_token,
            "historical_synced": self.historical_synced
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)

    # --- PHASE 1: DYNAMIC PLEX PIN-BASED AUTHENTICATION ---

    def authenticate_plex(self):
        if self.plex_token:
            return

        print("\n=== STEP 1: LINK TO PLEX ===")
        try:
            # Request PIN generation layout from Plex API v2
            pin_res = requests.post("https://plex.tv/api/v2/pins?strong=true", headers=PLEX_APP_HEADERS, json={}, timeout=10)
            if pin_res.status_code != 201:
                raise Exception(f"Failed to fetch PIN from Plex (Status {pin_res.status_code})")
            
            pin_data = pin_res.json()
            pin_id = pin_data.get("id")
            code = pin_data.get("code")

            # Check if Plex gave us the short 4-char code or the long 25-char hash
            if code and len(str(code)) <= 6:
                print(f"\n[!] ACTION REQUIRED: Go to https://plex.tv/link")
                print(f"[!] Enter Code: {code}")
            else:
                # If it's a long token, generate the official direct login link
                encoded_prod = urllib.parse.quote(PLEX_APP_HEADERS["X-Plex-Product"])
                auth_url = f"https://app.plex.tv/auth#?clientID={self.guid}&code={code}&context%5Bdevice%5D%5Bproduct%5D={encoded_prod}"
                print(f"\n[!] ACTION REQUIRED: Open this link in your browser to authorize:")
                print(f"--> {auth_url}")

            print("\n[*] Waiting for verification from Plex (polling)...")

            # Poll until authorized
            while True:
                time.sleep(5)
                check_res = requests.get(f"https://plex.tv/api/v2/pins/{pin_id}", headers=PLEX_APP_HEADERS, timeout=10)
                if check_res.status_code == 200:
                    check_data = check_res.json()
                    token = check_data.get("authToken")
                    if token:
                        self.plex_token = token
                        self.save_config()
                        print("[+] Successfully linked to your Plex Account!")
                        break
                else:
                    print("[!] Issue communicating with Plex authentication API. Retrying...")

        except Exception as e:
            print(f"[!] Error authenticating with Plex: {e}")
            time.sleep(10)
            self.authenticate_plex()

    # --- PHASE 2: MYTVCALENDAR AUTHENTICATION ---

    def check_link_status(self):
        url = f"{MYTVCALENDAR_API}/status"
        payload = {"guid": self.guid}
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == 1:
                    if not self.is_linked:
                        print("\n[+] Device successfully linked to MyTVCalendar!")
                    self.is_linked = True
                    return True
                else:
                    self.is_linked = False
                    link_code = data.get("link_code")
                    print(f"\r[!] ACTION REQUIRED: Go to https://mytvcalendar.com/plex-plugin and enter code: {link_code}", end="", flush=True)
                    return False
            return False
        except Exception as e:
            print(f"\n[!] Error checking MyTVCalendar status: {e}")
            return False

    def wait_for_mytvcalendar_pairing(self):
        if self.is_linked:
            return
        print("\n=== STEP 2: LINK TO MYTVCALENDAR ===")
        while not self.check_link_status():
            time.sleep(5)

    # --- PHASE 3: ONE-TIME HISTORICAL WATCH HISTORY SYNC ---

    def sync_historical_watches(self):
        if self.historical_synced:
            return

        print("\n=== STEP 3: SYNCING HISTORICAL WATCH HISTORY ===")
        # Updated to the official universal history endpoint
        url = f"{PLEX_URL}/status/sessions/history/all?librarySectionID=2&X-Plex-Container-Start=0"
        
        try:
            headers = {
                "Accept": "application/json",
                "X-Plex-Token": self.plex_token
            }
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 401:
                print("[!] Plex Token invalid or expired. Resetting authentication.")
                self.plex_token = None
                self.save_config()
                return
            elif response.status_code != 200:
                print(f"[!] Plex API returned error status: {response.status_code}")
                return

            # This endpoint reliably yields standard native JSON format
            history_data = response.json()
            items = history_data.get("MediaContainer", {}).get("Metadata", [])
            print(f"[*] Found {len(items)} history records. Syncing with MyTVCalendar...")

            success_count = 0
            for item in items:
                # Extract structured naming elements
                grandparent_title = item.get("grandparentTitle") # Series Title
                parent_index = item.get("parentIndex")          # Season Index
                index = item.get("index")                       # Episode Index

                if grandparent_title and parent_index is not None and index is not None:
                    payload = {
                        "guid": self.guid,
                        "action": "watched",
                        "seriesName": grandparent_title,
                        "seasonNumber": int(parent_index),
                        "episodeNumber": int(index),
                        "tmdbId": None,
                        "tvdbId": None
                    }
                    if self.send_watched_event(payload, historical=True):
                        success_count += 1
                    time.sleep(0.2) # Throttle to prevent API congestion
            
            print(f"[+] Sync finished. Uploaded {success_count} legacy entries.")
            self.historical_synced = True
            self.save_config()

        except Exception as e:
            print(f"[!] Error during historical sync execution: {e}")

    # --- PHASE 4: LIVE MONITORING & DISPATCH ---

    def send_watched_event(self, payload, historical=False):
        url = f"{MYTVCALENDAR_API}/event"
        prefix = "[Historical]" if historical else "[Live]"
        try:
            res = requests.post(url, json=payload, timeout=10)
            if res.status_code == 200:
                if not historical:
                    print(f"\n{prefix} Scrobbled: {payload['seriesName']} S{payload['seasonNumber']}E{payload['episodeNumber']}")
                return True
            elif res.status_code == 403:
                print(f"\n{prefix} Device configuration unlinked from MyTVCalendar.")
                self.is_linked = False
                return False
            return False
        except Exception:
            return False

    def monitor_plex_sessions(self):
        url = f"{PLEX_URL}/status/sessions?X-Plex-Token={self.plex_token}"
        headers = {"Accept": "application/json"}
        
        try:
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 401:
                print("\n[!] Plex Token rejected. Forcing re-auth loop...")
                self.plex_token = None
                self.save_config()
                return

            current_sessions = response.json().get("MediaContainer", {}).get("Metadata", [])
            active_session_ids = []

            for session in current_sessions:
                if session.get("type") != "episode":
                    continue

                session_id = session.get("sessionKey")
                if not session_id:
                    continue
                
                active_session_ids.append(session_id)
                view_offset = session.get("viewOffset", 0)
                duration = session.get("duration", 0)

                if duration > 0:
                    progress = view_offset / duration
                    
                    if session_id not in self.active_sessions:
                        self.active_sessions[session_id] = {"sent": False}
                    
                    if progress >= 0.9 and not self.active_sessions[session_id]["sent"]:
                        payload = {
                            "guid": self.guid,
                            "action": "watched",
                            "seriesName": session.get("grandparentTitle"),
                            "seasonNumber": int(session.get("parentIndex", 1)),
                            "episodeNumber": int(session.get("index", 1)),
                            "tmdbId": None,
                            "tvdbId": None
                        }
                        if self.send_watched_event(payload):
                            self.active_sessions[session_id]["sent"] = True

            for old_id in list(self.active_sessions.keys()):
                if old_id not in active_session_ids:
                    del self.active_sessions[old_id]

        except Exception:
            pass

    def run(self):
        while True:
            if not self.plex_token:
                self.authenticate_plex()

            if not self.is_linked:
                self.wait_for_mytvcalendar_pairing()
                
            if self.plex_token and self.is_linked and not self.historical_synced:
                self.sync_historical_watches()
                print("\n[*] Onboarding complete. Live background monitoring started successfully.")
                
            if self.plex_token and self.is_linked:
                self.monitor_plex_sessions()
                time.sleep(10)

if __name__ == "__main__":
    bridge = MyTVCalendarBridge()
    bridge.run()
