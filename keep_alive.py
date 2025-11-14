import requests
import time
import threading
import os

def ping_bot():
    """Ping the bot URL to keep it awake"""
    try:
        url = os.getenv('RENDER_URL', 'https://hexalegends.onrender.com')
        response = requests.get(f"{url}/health")
        print(f"✅ Pinged bot: {response.status_code}")
    except Exception as e:
        print(f"❌ Ping failed: {e}")

def start_pinging():
    """Start periodic pinging"""
    while True:
        ping_bot()
        time.sleep(600)  # Ping every 10 minutes

if __name__ == '__main__':
    print("🚀 Starting keep-alive pinger...")
    ping_thread = threading.Thread(target=start_pinging, daemon=True)
    ping_thread.start()
    
    # Keep main thread alive
    while True:
        time.sleep(1)
