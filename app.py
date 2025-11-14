from flask import Flask
import os
import logging
import multiprocessing
import time

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Global to track bot process
bot_process = None

def run_bot():
    """Run the Telegram bot (this will be in a separate process)"""
    try:
        # Import inside function to avoid issues
        from bot import AdvancedWelcomeSecurityBot
        
        BOT_TOKEN = os.getenv('BOT_TOKEN', "8228108336:AAF3OWn5-nYQjEZhNactyldXV9FW9kTtq9k")
        
        if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
            logging.error("❌ BOT_TOKEN not set!")
            return
        
        logging.info(f"🤖 Starting Telegram Bot with token: {BOT_TOKEN[:10]}...")
        bot = AdvancedWelcomeSecurityBot(BOT_TOKEN)
        
        # This will run in the main thread of the separate process
        bot.run()
        
    except Exception as e:
        logging.error(f"❌ Bot error: {e}")
        import traceback
        logging.error(traceback.format_exc())

@app.route('/')
def home():
    global bot_process
    status = "RUNNING 🟢" if bot_process and bot_process.is_alive() else "STOPPED 🔴"
    return f"""
    <html>
        <head>
            <title>HexaLegends Bot</title>
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                .status {{ font-size: 24px; font-weight: bold; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h1>🤖 HexaLegends Telegram Bot</h1>
            <div class="status">Status: {status}</div>
            <p>Your bot should be working now!</p>
            <p><a href="/health">Health Check</a></p>
        </body>
    </html>
    """

@app.route('/health')
def health():
    global bot_process
    return {
        "status": "healthy",
        "bot_running": bot_process and bot_process.is_alive(),
        "service": "telegram-bot"
    }

if __name__ == '__main__':
    # Start bot in a separate PROCESS (not thread)
    logging.info("🚀 Starting Telegram Bot in separate process...")
    bot_process = multiprocessing.Process(target=run_bot, daemon=True)
    bot_process.start()
    
    # Give the bot process a moment to start
    time.sleep(3)
    
    if bot_process and bot_process.is_alive():
        logging.info("✅ Bot process started successfully")
    else:
        logging.error("❌ Bot process failed to start")
    
    # Start Flask app
    logging.info("🌐 Starting Flask web server...")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
