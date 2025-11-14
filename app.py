from flask import Flask, request
import os
import threading
import logging
import time

app = Flask(__name__)

# Global variable to track bot status
bot_instance = None
bot_thread = None
bot_running = False

def run_bot():
    global bot_instance, bot_running
    try:
        logging.info("🤖 Starting Telegram Bot...")
        BOT_TOKEN = os.getenv('BOT_TOKEN')
        
        if not BOT_TOKEN or BOT_TOKEN == "8228108336:AAF3OWn5-nYQjEZhNactyldXV9FW9kTtq9k":
            logging.error("❌ BOT_TOKEN not set!")
            return
        
        from bot import AdvancedWelcomeSecurityBot
        bot_instance = AdvancedWelcomeSecurityBot(BOT_TOKEN)
        bot_running = True
        logging.info("✅ Bot started successfully")
        bot_instance.run()
        
    except Exception as e:
        logging.error(f"❌ Bot error: {e}")
        bot_running = False

@app.route('/')
def home():
    status = "running" if bot_running else "stopped"
    return f"""
    <html>
        <head>
            <title>HexaLegends Bot</title>
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                .status {{ font-size: 24px; font-weight: bold; margin: 20px 0; }}
                .running {{ color: green; }}
                .stopped {{ color: red; }}
            </style>
        </head>
        <body>
            <h1>🤖 HexaLegends Telegram Bot</h1>
            <div class="status {status}">Status: {status.upper()}</div>
            <p>Bot is {'🟢 RUNNING' if bot_running else '🔴 STOPPED'}</p>
            <div>
                <a href="/start" style="margin: 10px; padding: 10px; background: green; color: white; text-decoration: none;">START BOT</a>
                <a href="/health" style="margin: 10px; padding: 10px; background: blue; color: white; text-decoration: none;">HEALTH CHECK</a>
            </div>
        </body>
    </html>
    """

@app.route('/health')
def health():
    return {
        "status": "healthy" if bot_running else "unhealthy",
        "bot_running": bot_running,
        "timestamp": time.time()
    }

@app.route('/start')
def start_bot():
    global bot_thread, bot_running
    
    if bot_running:
        return "⚠️ Bot is already running"
    
    if bot_thread and bot_thread.is_alive():
        return "⚠️ Bot thread is already running"
    
    try:
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        
        # Wait a moment to check if bot started
        time.sleep(2)
        
        if bot_running:
            return "🚀 Bot started successfully! <a href='/'>Go Home</a>"
        else:
            return "❌ Bot failed to start. Check logs."
            
    except Exception as e:
        return f"❌ Error starting bot: {e}"

@app.route('/logs')
def show_logs():
    # Simple log viewer
    try:
        import subprocess
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        processes = result.stdout
        return f"<pre>Current Processes:\n{processes}</pre>"
    except:
        return "Logs unavailable"

if __name__ == '__main__':
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Start bot automatically when app starts
    logging.info("🚀 Starting HexaLegends Bot...")
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Start Flask app
    logging.info("🌐 Starting Flask web server...")
    app.run(host='0.0.0.0', port=5000, debug=False)
