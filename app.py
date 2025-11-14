from flask import Flask
import os
import logging
import multiprocessing
import time
import sys

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Global to track bot process
bot_process = None
bot_restart_count = 0
MAX_RESTARTS = 5

def run_bot():
    """Run the Telegram bot (this will be in a separate process)"""
    try:
        # Add current directory to Python path
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        
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
        logging.error(f"❌ Bot process error: {e}")
        import traceback
        logging.error(traceback.format_exc())

def restart_bot():
    """Restart the bot process if it dies"""
    global bot_process, bot_restart_count
    
    if bot_process and bot_process.is_alive():
        return True
        
    if bot_restart_count >= MAX_RESTARTS:
        logging.error("🚨 Max restart attempts reached. Bot will not restart.")
        return False
        
    logging.info("🔄 Restarting bot process...")
    bot_process = multiprocessing.Process(target=run_bot, daemon=True)
    bot_process.start()
    bot_restart_count += 1
    
    # Wait to see if it starts successfully
    time.sleep(5)
    return bot_process.is_alive()

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
            <p>Restart Count: {bot_restart_count}</p>
            <p><a href="/health">Health Check</a> | <a href="/restart">Restart Bot</a></p>
        </body>
    </html>
    """

@app.route('/health')
def health():
    global bot_process
    # Try to restart if dead
    if not (bot_process and bot_process.is_alive()):
        restart_bot()
    
    return {
        "status": "healthy" if bot_process and bot_process.is_alive() else "unhealthy",
        "bot_running": bot_process and bot_process.is_alive(),
        "restart_count": bot_restart_count,
        "service": "telegram-bot"
    }

@app.route('/restart')
def restart():
    global bot_restart_count
    bot_restart_count = 0  # Reset counter
    if restart_bot():
        return "✅ Bot restart initiated!"
    else:
        return "❌ Bot restart failed!"

# Auto-restart checker
def check_bot_health():
    """Periodically check and restart bot if needed"""
    while True:
        if not (bot_process and bot_process.is_alive()):
            logging.warning("⚠️ Bot process died, attempting restart...")
            restart_bot()
        time.sleep(30)  # Check every 30 seconds

if __name__ == '__main__':
    # Start bot in a separate PROCESS (not thread)
    logging.info("🚀 Starting Telegram Bot in separate process...")
    bot_process = multiprocessing.Process(target=run_bot, daemon=True)
    bot_process.start()
    
    # Give the bot process a moment to start
    time.sleep(5)
    
    if bot_process and bot_process.is_alive():
        logging.info("✅ Bot process started successfully")
    else:
        logging.error("❌ Bot process failed to start")
    
    # Start health checker in background
    health_thread = multiprocessing.Process(target=check_bot_health, daemon=True)
    health_thread.start()
    
    # Start Flask app
    logging.info("🌐 Starting Flask web server...")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
