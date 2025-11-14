from flask import Flask
import os
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

@app.route('/')
def home():
    return """
    <html>
        <head><title>HexaLegends Bot</title></head>
        <body>
            <h1>🤖 HexaLegends Telegram Bot</h1>
            <p>Status: 🟢 Web Server Running</p>
            <p><em>Note: Bot runs separately in main process</em></p>
            <p><a href="/health">Health Check</a></p>
        </body>
    </html>
    """

@app.route('/health')
def health():
    return {"status": "healthy", "service": "web-server"}

# Don't start the bot here - let it run in main process
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
