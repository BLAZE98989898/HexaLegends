from flask import Flask
import os
import threading
import logging
import asyncio
import time

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def run_bot():
    """Run the Telegram bot in a separate thread with proper event loop"""
    try:
        logging.info("🤖 Starting Telegram Bot...")
        
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Import inside function to avoid circular imports
        from bot import AdvancedWelcomeSecurityBot
        
        BOT_TOKEN = os.getenv('BOT_TOKEN', "8228108336:AAF3OWn5-nYQjEZhNactyldXV9FW9kTtq9k")
        
        if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
            logging.error("❌ BOT_TOKEN not set!")
            return
        
        logging.info(f"✅ Using BOT_TOKEN: {BOT_TOKEN[:10]}...")
        bot = AdvancedWelcomeSecurityBot(BOT_TOKEN)
        
        # Run the bot in the event loop
        loop.run_until_complete(bot.run_async())
        
    except Exception as e:
        logging.error(f"❌ Bot error: {e}")
        import traceback
        logging.error(traceback.format_exc())

@app.route('/')
def home():
    return """
    <html>
        <head><title>HexaLegends Bot</title></head>
        <body>
            <h1>🤖 HexaLegends Telegram Bot</h1>
            <p>Status: 🟢 RUNNING</p>
            <p>Check your bot in Telegram - it should be working now!</p>
            <p><a href="/health">Health Check</a></p>
        </body>
    </html>
    """

@app.route('/health')
def health():
    return {"status": "healthy", "service": "telegram-bot"}

@app.route('/test')
def test():
    return "✅ Server is running!"

if __name__ == '__main__':
    # Start bot in a separate thread
    logging.info("🚀 Starting bot thread...")
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    logging.info("🌐 Starting Flask server...")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
