from flask import Flask
import os
import logging
import subprocess
import threading
import time

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_bot_subprocess():
    """Run bot as subprocess and auto-restart"""
    while True:
        try:
            logger.info("🤖 Starting bot subprocess...")
            # Run bot.py as a separate process
            process = subprocess.run(
                ['python', 'bot.py'],
                capture_output=True,
                text=True
            )
            
            if process.stdout:
                logger.info(f"Bot output: {process.stdout}")
            if process.stderr:
                logger.error(f"Bot errors: {process.stderr}")
                
            logger.warning("⚠️ Bot process ended, restarting in 10 seconds...")
            time.sleep(10)
            
        except Exception as e:
            logger.error(f"❌ Subprocess error: {e}")
            time.sleep(30)

@app.route('/')
def home():
    return """
    <html>
        <head><title>HexaLegends Bot</title></head>
        <body style="text-align: center; padding: 50px;">
            <h1>🤖 HexaLegends Bot</h1>
            <p>Status: 🟢 RUNNING</p>
            <p>Bot runs in background with auto-restart</p>
        </body>
    </html>
    """

@app.route('/health')
def health():
    return "✅ Healthy"

if __name__ == '__main__':
    # Start bot in background thread
    bot_thread = threading.Thread(target=run_bot_subprocess, daemon=True)
    bot_thread.start()
    
    # Start Flask
    app.run(host='0.0.0.0', port=5000, debug=False)
