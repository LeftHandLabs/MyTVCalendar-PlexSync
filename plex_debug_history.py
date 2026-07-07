import os
import json
import requests

CONFIG_FILE = "mytvcalendar_config.json"
PLEX_URL = "http://localhost:32400"

def run_diagnostics():
    print("=== PLEX HISTORY DIAGNOSTIC TOOL ===")
    
    # 1. Check Config File
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

    headers = {
        "Accept": "application/json",
        "X-Plex-Token": plex_token
    }

    # 2. Test Core Server Connectivity
    print("\n--- Testing Core Server Connection ---")
    try:
        res = requests.get(f"{PLEX_URL}/identity", headers=headers, timeout=10)
        print(f"Server Identity Status: {res.status_code}")
        if res.status_code == 200:
            print(f"[OK] Successfully connected to Plex Server.")
            print(f"  -> Server Info: {res.text.strip()[:150]}...")
        elif res.status_code == 401:
            print("[FAIL] Plex rejected your token (401 Unauthorized).")
            return
        else:
            print(f"[WARN] Unexpected status code checking identity: {res.status_code}")
    except Exception as e:
        print(f"[FAIL] Could not reach Plex at {PLEX_URL}: {e}")
        return

    # 3. Test Endpoint A: Modern History Endpoint
    print("\n--- Testing Endpoint A: /status/sessions/history/all ---")
    url_a = f"{PLEX_URL}/status/sessions/history/all?type=2"
    try:
        res_a = requests.get(url_a, headers=headers, timeout=15)
        print(f"HTTP Status Code: {res_a.status_code}")
        print(f"Content-Type: {res_a.headers.get('Content-Type')}")
        
        if res_a.status_code == 200:
            try:
                data = res_a.json()
                items = data.get("MediaContainer", {}).get("Metadata", [])
                print(f"[RESULT] Endpoint A returned {len(items)} history items.")
                if len(items) > 0:
                    print("  -> Sample Item Data structure:")
                    print(json.dumps(items[0], indent=2)[:300] + "\n...")
            except Exception as json_err:
                print(f"[FAIL] Content returned by Endpoint A was not valid JSON: {json_err}")
                print(f"Raw Snippet: {res_a.text[:300]}")
        else:
            print(f"[FAIL] Endpoint A returned non-200 code: {res_a.status_code}")
            print(f"Response snippet: {res_a.text[:300]}")
    except Exception as e:
        print(f"[FAIL] Connection error on Endpoint A: {e}")

    # 4. Test Endpoint B: Legacy History Endpoint
    print("\n--- Testing Endpoint B: /library/sections/all/history ---")
    url_b = f"{PLEX_URL}/library/sections/all/history?type=2"
    try:
        res_b = requests.get(url_b, headers=headers, timeout=15)
        print(f"HTTP Status Code: {res_b.status_code}")
        print(f"Content-Type: {res_b.headers.get('Content-Type')}")
        
        if res_b.status_code == 200:
            try:
                data = res_b.json()
                items = data.get("MediaContainer", {}).get("Metadata", [])
                print(f"[RESULT] Endpoint B returned {len(items)} history items.")
            except Exception:
                if "xml" in res_b.text or res_b.text.strip().startswith("<"):
                    print("[RESULT] Endpoint B bypassed JSON format and returned XML data.")
                    print(f"Raw XML Snippet: {res_b.text[:300]}")
                else:
                    print("[FAIL] Endpoint B returned unparseable text format.")
                    print(f"Raw Snippet: {res_b.text[:300]}")
        else:
            print(f"[FAIL] Endpoint B returned non-200 code: {res_b.status_code}")
    except Exception as e:
        print(f"[FAIL] Connection error on Endpoint B: {e}")

if __name__ == "__main__":
    run_diagnostics()