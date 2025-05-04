# -*- coding: utf-8 -*-
import requests
import os
import json
import datetime
from googleapiclient.discovery import build
from http.server import BaseHTTPRequestHandler

# --- Configuration ---
# Bilibili User ID from URL: https://space.bilibili.com/491306902 -> 491306902
BILIBILI_USER_ID = "491306902"
# YouTube Channel ID from URL: https://www.youtube.com/channel/UC_5lJHgnMP_lb_VpIiXV0hQ -> UC_5lJHgnMP_lb_VpIiXV0hQ
YOUTUBE_CHANNEL_ID = "UC_5lJHgnMP_lb_VpIiXV0hQ"

# --- Environment Variables (Set in Vercel Project Settings) ---
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
KV_REST_API_URL = os.environ.get("KV_REST_API_URL") # e.g., https://<region>-<id>.kv.vercel-storage.com
KV_REST_API_TOKEN = os.environ.get("KV_REST_API_TOKEN") # Vercel KV Read-Write Token
KV_KEY_NAME = "follower_counts" # Key to store data under in Vercel KV

# --- Helper Functions ---
def get_bilibili_followers(user_id):
    """Fetches Bilibili follower count using the public API."""
    url = f"https://api.bilibili.com/x/relation/stat?vmid={user_id}"
    try:
        response = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://space.bilibili.com",
            "Referer": f"https://space.bilibili.com/{user_id}/",
        }, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("code") == 0:
            return data.get("data", {}).get("follower")
        else:
            print(f"Bilibili API error: {data.get("message")}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Bilibili data: {e}")
        return None
    except json.JSONDecodeError:
        print("Error decoding Bilibili JSON response")
        return None

def get_youtube_subscribers(channel_id, api_key):
    """Fetches YouTube subscriber count using the YouTube Data API v3."""
    if not api_key:
        print("YouTube API Key not configured. Please set the YOUTUBE_API_KEY environment variable.")
        return None

    try:
        youtube = build("youtube", "v3", developerKey=api_key)
        request = youtube.channels().list(
            part="statistics",
            id=channel_id
        )
        response = request.execute()

        if response.get("items"):
            statistics = response["items"][0].get("statistics", {})
            return int(statistics.get("subscriberCount", 0)) if statistics.get("hiddenSubscriberCount") == False else "hidden"
        else:
            print("YouTube channel not found or API error.")
            return None
    except Exception as e:
        print(f"Error fetching YouTube data: {e}")
        return None

def store_in_vercel_kv(key, value):
    """Stores data in Vercel KV using the REST API."""
    if not KV_REST_API_URL or not KV_REST_API_TOKEN:
        print("Vercel KV URL or Token not configured. Cannot store data.")
        return False

    headers = {
        "Authorization": f"Bearer {KV_REST_API_TOKEN}"
    }
    try:
        # Use the SET command for KV
        response = requests.post(f"{KV_REST_API_URL}/set/{key}", headers=headers, json=value, timeout=10)
        response.raise_for_status()
        result = response.json()
        if result.get("result") == "OK":
            print(f"Successfully stored data in Vercel KV under key: {key}")
            return True
        else:
            print(f"Error storing data in Vercel KV: {result}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Error communicating with Vercel KV API: {e}")
        return False
    except json.JSONDecodeError:
        print("Error decoding Vercel KV API response")
        return False

# --- Vercel Serverless Function Handler ---
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        print("Function triggered...")

        # Check for required environment variables
        if not YOUTUBE_API_KEY or not KV_REST_API_URL or not KV_REST_API_TOKEN:
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Missing required environment variables (YOUTUBE_API_KEY, KV_REST_API_URL, KV_REST_API_TOKEN)"}).encode("utf-8"))
            print("Error: Missing environment variables.")
            return

        # Fetch data
        print("Fetching follower counts...")
        bilibili_followers = get_bilibili_followers(BILIBILI_USER_ID)
        youtube_subscribers = get_youtube_subscribers(YOUTUBE_CHANNEL_ID, YOUTUBE_API_KEY)

        timestamp = datetime.datetime.utcnow().isoformat() + "Z"

        result_data = {
            "bilibili": {
                "user_id": BILIBILI_USER_ID,
                "followers": bilibili_followers,
            },
            "youtube": {
                "channel_id": YOUTUBE_CHANNEL_ID,
                "subscribers": youtube_subscribers
            },
            "last_updated_utc": timestamp
        }

        print(f"Fetched data: {json.dumps(result_data)}")

        # Store data in Vercel KV
        print(f"Storing data in Vercel KV under key: {KV_KEY_NAME}...")
        success = store_in_vercel_kv(KV_KEY_NAME, result_data)

        # Send response
        if success:
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "data_stored": result_data}).encode("utf-8"))
            print("Function finished successfully.")
        else:
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": "Failed to store data in Vercel KV"}).encode("utf-8"))
            print("Function finished with errors (KV storage failed).")

        return

# --- Main execution block for local testing (optional) ---
# To test locally: 
# 1. Set environment variables: YOUTUBE_API_KEY, KV_REST_API_URL, KV_REST_API_TOKEN
# 2. Run: python api/index.py 
# 3. This won't run the server, but executes the core logic for testing.
if __name__ == "__main__":
    print("Running local test...")
    if not YOUTUBE_API_KEY or not KV_REST_API_URL or not KV_REST_API_TOKEN:
        print("Error: Missing environment variables for local test.")
        print("Please set YOUTUBE_API_KEY, KV_REST_API_URL, KV_REST_API_TOKEN")
    else:
        bilibili_followers = get_bilibili_followers(BILIBILI_USER_ID)
        youtube_subscribers = get_youtube_subscribers(YOUTUBE_CHANNEL_ID, YOUTUBE_API_KEY)
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        result_data = {
            "bilibili": {"user_id": BILIBILI_USER_ID, "followers": bilibili_followers},
            "youtube": {"channel_id": YOUTUBE_CHANNEL_ID, "subscribers": youtube_subscribers},
            "last_updated_utc": timestamp
        }
        print(f"Fetched data: {json.dumps(result_data, indent=2)}")
        store_in_vercel_kv(KV_KEY_NAME, result_data)
    print("Local test finished.")


