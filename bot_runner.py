import os
import sys
import logging

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def run_bot():
    try:
        from bot import AdvancedWelcomeSecurityBot
        
        # Get bot token from environment variable
        BOT_TOKEN = os.getenv('BOT_TOKEN')
        
        if not BOT_TOKEN:
            print("❌ BOT_TOKEN environment variable not set!")
            return
        
        print("🤖 Starting Telegram Bot...")
        bot = AdvancedWelcomeSecurityBot(BOT_TOKEN)
        bot.run()
        
    except Exception as e:
        print(f"❌ Error running bot: {e}")
        logging.error(f"Bot error: {e}")

if __name__ == '__main__':
    run_bot()
