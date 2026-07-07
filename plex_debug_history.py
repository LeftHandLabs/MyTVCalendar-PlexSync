import os
import json
import requests

CONFIG_FILE = "mytvcalendar_config.json"
PLEX_URL = "http://localhost:32400"

def run_diagnostics():
    print("=== PLEX HISTORY DIAGNOSTIC TOOL ===")
    
    # 1. Check Config File existence
    if not os.path.exists(CONFIG_FILE):
        print(f"[FAIL] Configuration file '{CONFIG_FILE}' not found in this directory.")
        return
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            plex_token = config.get("plex_token")
            guid = config.get("guid")
    except Exception as e:
        print(f"[FAIL] Could not parse config file: {e}")
        return

    print(f"[OK] Configuration loaded.")
    print(f"  -> Device GUID: {guid}")
    print(f"  -> Plex Token: {'Found (Masked)' if plex_token else 'MISSING'}")
    
    if not plex_token:
        print("[FAIL] Cannot proceed without a valid Plex Token. Please run the main link process first.")
        return

    # 2. Test Core Server Connectivity
    print("\n--- Testing Core Server Connection ---")
    identity_headers = {
        "Accept": "application/json",
        "X-Plex-Token": plex_token
    }
    try:
        res = requests.get(f"{PLEX_URL}/identity", headers=identity_headers, timeout=10)
        print(f"Server Identity Status: {res.status_code}")
        if res.status_code == 200:
            print(f"[OK] Successfully connected to Plex Server.")
        elif res.status_code == 401:
            print("[FAIL] Plex rejected your token (401 Unauthorized).")
            return
        else:
            print(f"[WARN] Unexpected status code checking identity: {res.status_code}")
    except Exception as e:
        print(f"[FAIL] Could not reach Plex at {PLEX_URL}: {e}")
        return

    # 3. Test Endpoint A: Modern Clean History Endpoint
    print("\n--- Testing Endpoint A: /status/sessions/history/all ---")
    url_a = f"{PLEX_URL}/status/sessions/history/all?type=2"
    
    # Passing parsing limits and token structural controls directly into headers
    headers_a = {
        "Accept": "application/json",
        "X-Plex-Token": plex_token,
        "X-Plex-Container-Start": "0",
        "X-Plex-Container-Size": "50"
    }
    
    try:
        res_a = requests.get(url_a, headers=headers_a, timeout=15)
        print(f"HTTP Status Code: {res_a.status_code}")
        print(f"Content-Type: {res_a.headers.get('Content-Type')}")
        
        if res_a.status_code == 200:
            try:
                data = res_a.json()
                items = data.get("MediaContainer", {}).get("Metadata", [])
                print(f"[RESULT] Endpoint A returned {len(items)} history items.")
                if len(items) > 0:
                    print("\n[+] Sample Data Found! Extracting first object layout:")
                    sample = items[0]
                    print(f"  Series:  {sample.get('grandparentTitle')}")
                    print(f"  Season:  {sample.get('parentIndex')}")
                    print(f"  Episode: {sample.get('index')}")
                    print(f"  Viewed:  {sample.get('viewedAt')}")
                else:
                    print("\n[!] IMPORTANT: Server responded successfully, but returned an empty list (0 items).")
                    print("    This confirms your friend is likely running this on a managed user profile")
                    print("    or a secondary account instead of the main Plex Server Administrator account.")
            except Exception as json_err:
                print(f"[FAIL] Content returned by Endpoint A was not valid JSON: {json_err}")
                print(f"Raw Response Snippet: {res_a.text[:300]}")
        else:
            print(f"[FAIL] Endpoint A returned bad status code: {res_a.status_code}")
            print(f"Response snippet: {res_a.text[:300]}")
    except Exception as e:
        print(f"[FAIL] Connection error on Endpoint A: {e}")

if __name__ == "__main__":
    run_diagnostics()
