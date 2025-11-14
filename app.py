from flask import Flask
import os
import logging
import threading
import time
import requests

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variable to track if bot is running
bot_running = False

def run_bot():
    """Run the Telegram bot - SIMPLE VERSION"""
    global bot_running
    try:
        logger.info("🤖 Starting Telegram Bot...")
        
        # Import inside function
        from bot import AdvancedWelcomeSecurityBot
        
        BOT_TOKEN = os.getenv('BOT_TOKEN', "8228108336:AAF3OWn5-nYQjEZhNactyldXV9FW9kTtq9k")
        
        if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
            logger.error("❌ BOT_TOKEN not set!")
            return
        
        logger.info(f"✅ Using BOT_TOKEN: {BOT_TOKEN[:10]}...")
        bot = AdvancedWelcomeSecurityBot(BOT_TOKEN)
        bot_running = True
        bot.run()
        
    except Exception as e:
        logger.error(f"❌ Bot error: {e}")
        bot_running = False

def keep_alive():
    """Ping the service to keep it awake"""
    while True:
        try:
            # Get the Render URL
            render_url = os.getenv('RENDER_EXTERNAL_URL')
            if render_url:
                requests.get(f"{render_url}/health", timeout=10)
                logger.info("✅ Pinged to stay awake")
        except Exception as e:
            logger.error(f"❌ Ping failed: {e}")
        time.sleep(300)  # Ping every 5 minutes

@app.route('/')
def home():
    status = "🟢 RUNNING" if bot_running else "🔴 STOPPED"
    return f"""
    <html>
        <head><title>HexaLegends Bot</title></head>
        <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
            <h1>🤖 HexaLegends Telegram Bot</h1>
            <div style="font-size: 24px; font-weight: bold; margin: 20px 0;">Status: {status}</div>
            <p>Service is running and bot should be working!</p>
            <p><a href="/health">Health Check</a></p>
        </body>
    </html>
    """

@app.route('/health')
def health():
    return {
        "status": "healthy",
        "bot_running": bot_running,
        "service": "hexalegends-bot",
        "timestamp": time.time()
    }

if __name__ == '__main__':
    # Start keep-alive in background thread
    keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
    keep_alive_thread.start()
    
    # Start bot in main thread (this will block)
    logger.info("🚀 Starting bot in main thread...")
    run_bot()
