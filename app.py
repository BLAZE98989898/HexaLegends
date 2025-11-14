from flask import Flask
import os
import logging
import threading
import time

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_bot():
    """Run the Telegram bot in main thread"""
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
        bot.run()
        
    except Exception as e:
        logger.error(f"❌ Bot error: {e}")
        import traceback
        logger.error(traceback.format_exc())

@app.route('/')
def home():
    return """
    <html>
        <head><title>HexaLegends Bot</title></head>
        <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
            <h1>🤖 HexaLegends Telegram Bot</h1>
            <div style="font-size: 24px; font-weight: bold; margin: 20px 0;">Status: 🟢 RUNNING</div>
            <p>Bot is running in background!</p>
            <p><a href="/health">Health Check</a> | <a href="/ping">Ping</a></p>
        </body>
    </html>
    """

@app.route('/health')
def health():
    return {
        "status": "healthy",
        "service": "hexalegends-bot",
        "timestamp": time.time()
    }

@app.route('/ping')
def ping():
    return "pong"

if __name__ == '__main__':
    # Start bot in background thread (not process)
    logger.info("🚀 Starting bot in background thread...")
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    logger.info("🌐 Starting Flask web server...")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
