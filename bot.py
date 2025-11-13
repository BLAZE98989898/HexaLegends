import os
import logging
import json
import sqlite3
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from telegram import (
    Update, User, Chat, ChatMember, ChatPermissions, 
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, CallbackQueryHandler, ChatMemberHandler,
    ConversationHandler
)
from telegram.constants import ParseMode

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
WELCOME_TEXT, WELCOME_MEDIA, WELCOME_BUTTONS, RULES_TEXT = range(4)

class AdvancedWelcomeSecurityBot:
    def __init__(self, token: str):
        self.token = token
        self.application = Application.builder().token(token).build()
        
        # Initialize database
        self.init_database()
        
        # Load data
        self.load_data()
        
        # Setup handlers
        self.setup_handlers()

    def init_database(self):
        """Initialize SQLite database for persistent storage"""
        try:
            self.conn = sqlite3.connect('bot_data.db', check_same_thread=False)
            self.cursor = self.conn.cursor()
            
            # Create tables
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS group_settings (
                    chat_id INTEGER PRIMARY KEY,
                    welcome_enabled BOOLEAN DEFAULT 1,
                    welcome_text TEXT,
                    welcome_media TEXT,
                    welcome_buttons TEXT,
                    rules_text TEXT,
                    max_warnings INTEGER DEFAULT 3,
                    security_level INTEGER DEFAULT 1,
                    antispam_enabled BOOLEAN DEFAULT 1,
                    captcha_enabled BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_warnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    chat_id INTEGER,
                    reason TEXT,
                    admin_id INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS banned_words (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER,
                    word TEXT,
                    action TEXT DEFAULT 'delete',
                    created_by INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            self.conn.commit()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")

    def load_data(self):
        """Load data from database into memory"""
        try:
            self.group_settings = {}
            self.user_warnings = {}
            self.user_captchas = {}
            self.banned_words = {}
            self.user_message_count = {}
            
            # Load group settings
            self.cursor.execute("SELECT * FROM group_settings")
            for row in self.cursor.fetchall():
                chat_id = row[0]
                self.group_settings[chat_id] = {
                    'welcome_enabled': bool(row[1]),
                    'welcome_text': row[2],
                    'welcome_media': json.loads(row[3]) if row[3] else None,
                    'welcome_buttons': json.loads(row[4]) if row[4] else None,
                    'rules_text': row[5],
                    'max_warnings': row[6] or 3,
                    'security_level': row[7] or 1,
                    'antispam_enabled': bool(row[8]),
                    'captcha_enabled': bool(row[9])
                }
            
            # Load banned words
            self.cursor.execute("SELECT chat_id, word, action FROM banned_words")
            for row in self.cursor.fetchall():
                chat_id = row[0]
                if chat_id not in self.banned_words:
                    self.banned_words[chat_id] = []
                self.banned_words[chat_id].append({'word': row[1], 'action': row[2]})
            
            logger.info("Data loaded successfully")
        except Exception as e:
            logger.error(f"Error loading data: {e}")

    def save_group_settings(self, chat_id: int):
        """Save group settings to database"""
        try:
            settings = self.group_settings.get(chat_id, {})
            self.cursor.execute('''
                INSERT OR REPLACE INTO group_settings 
                (chat_id, welcome_enabled, welcome_text, welcome_media, welcome_buttons, rules_text, max_warnings, security_level, antispam_enabled, captcha_enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                chat_id,
                settings.get('welcome_enabled', True),
                settings.get('welcome_text'),
                json.dumps(settings.get('welcome_media')) if settings.get('welcome_media') else None,
                json.dumps(settings.get('welcome_buttons')) if settings.get('welcome_buttons') else None,
                settings.get('rules_text'),
                settings.get('max_warnings', 3),
                settings.get('security_level', 1),
                settings.get('antispam_enabled', True),
                settings.get('captcha_enabled', False)
            ))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error saving group settings: {e}")

    def setup_handlers(self):
        """Setup all bot handlers"""
        try:
            # Welcome conversation handler
            welcome_conv = ConversationHandler(
                entry_points=[CommandHandler('setwelcome', self.setwelcome_command)],
                states={
                    WELCOME_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.set_welcome_text)],
                    WELCOME_MEDIA: [MessageHandler(filters.PHOTO | filters.VIDEO | filters.ANIMATION | filters.TEXT, self.set_welcome_media)],
                    WELCOME_BUTTONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.set_welcome_buttons)],
                },
                fallbacks=[CommandHandler('cancel', self.cancel_command)]
            )

            rules_conv = ConversationHandler(
                entry_points=[CommandHandler('setrules', self.setrules_command)],
                states={
                    RULES_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.set_rules_text)],
                },
                fallbacks=[CommandHandler('cancel', self.cancel_command)]
            )

            # Add handlers
            handlers = [
                welcome_conv,
                rules_conv,
                MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.welcome_handler),
                CommandHandler("start", self.start_command),
                CommandHandler("help", self.help_command),
                CommandHandler("welcome", self.welcome_preview_command),
                CommandHandler("rules", self.rules_command),
                CommandHandler("settings", self.settings_command),
                CommandHandler("security", self.security_command),
                CommandHandler("warn", self.warn_command),
                CommandHandler("ban", self.ban_command),
                CommandHandler("mute", self.mute_command),
                CommandHandler("unmute", self.unmute_command),
                CommandHandler("kick", self.kick_command),
                CommandHandler("unban", self.unban_command),
                CommandHandler("warnings", self.warnings_command),
                CommandHandler("clearwarns", self.clear_warnings_command),
                CommandHandler("antispam", self.antispam_command),
                CommandHandler("captcha", self.captcha_command),
                CommandHandler("addword", self.add_banned_word_command),
                CommandHandler("delword", self.del_banned_word_command),
                CommandHandler("listwords", self.list_banned_words_command),
                CommandHandler("report", self.report_command),
                CommandHandler("info", self.info_command),
                CommandHandler("stats", self.stats_command),
                CommandHandler("members", self.members_command),
                CommandHandler("testwelcome", self.testwelcome_command),
                CommandHandler("testcaptcha", self.testcaptcha_command),
                MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler),
                MessageHandler(filters.PHOTO | filters.VIDEO | filters.ANIMATION | filters.Document.ALL, self.media_handler),
                CallbackQueryHandler(self.button_handler, pattern="^welcome_"),
                CallbackQueryHandler(self.button_handler, pattern="^security_"),
                CallbackQueryHandler(self.button_handler, pattern="^captcha_"),
                CallbackQueryHandler(self.button_handler, pattern="^moderation_"),
            ]
            
            for handler in handlers:
                self.application.add_handler(handler)
            
            self.application.add_error_handler(self.error_handler)
            logger.info("All handlers setup successfully")
        except Exception as e:
            logger.error(f"Error setting up handlers: {e}")

    # ===== WELCOME SYSTEM =====
    async def welcome_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle new chat members - ALWAYS send welcome"""
        try:
            if update.message and update.message.new_chat_members:
                for user in update.message.new_chat_members:
                    if user.is_bot:
                        continue
                        
                    chat = update.effective_chat
                    settings = self.group_settings.get(chat.id, {})
                    
                    if not settings.get('welcome_enabled', True):
                        continue
                    
                    # ALWAYS send welcome message first
                    await self.send_welcome_message(chat, user, context)
                    
                    # Then check if CAPTCHA is needed
                    if settings.get('captcha_enabled'):
                        await self.send_captcha(chat, user, context)
                
            elif update.chat_member:
                chat = update.chat_member.chat
                new_status = update.chat_member.new_chat_member.status
                old_status = update.chat_member.old_chat_member.status
                
                if new_status in ['member', 'administrator'] and old_status in ['left', 'kicked']:
                    user = update.chat_member.new_chat_member.user
                    if not user.is_bot:
                        settings = self.group_settings.get(chat.id, {})
                        if settings.get('welcome_enabled', True):
                            # ALWAYS send welcome message first
                            await self.send_welcome_message(chat, user, context)
                            
                            # Then check if CAPTCHA is needed
                            if settings.get('captcha_enabled'):
                                await self.send_captcha(chat, user, context)
        except Exception as e:
            logger.error(f"Error in welcome handler: {e}")

    async def send_welcome_message(self, chat: Chat, user: User, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send welcome message"""
        try:
            settings = self.group_settings.get(chat.id, {})
            welcome_text = settings.get('welcome_text') or "Welcome {name} to {group}! 🎉"
            welcome_media = settings.get('welcome_media')
            welcome_buttons = settings.get('welcome_buttons')
            
            formatted_text = welcome_text.format(
                name=user.first_name,
                username=f"@{user.username}" if user.username else user.first_name,
                group=chat.title,
                mention=user.mention_html(),
                id=user.id
            )
            
            reply_markup = None
            if welcome_buttons:
                keyboard = []
                for btn_row in welcome_buttons:
                    row = []
                    for btn in btn_row:
                        row.append(InlineKeyboardButton(btn['text'], url=btn['url']))
                    keyboard.append(row)
                reply_markup = InlineKeyboardMarkup(keyboard)
            else:
                keyboard = [
                    [InlineKeyboardButton("📜 Rules", callback_data="welcome_rules")],
                    [InlineKeyboardButton("🔧 Help", callback_data="welcome_help")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
            
            if welcome_media:
                media_type = welcome_media['type']
                file_id = welcome_media['file_id']
                
                if media_type == 'photo':
                    await context.bot.send_photo(
                        chat_id=chat.id,
                        photo=file_id,
                        caption=formatted_text,
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.HTML
                    )
                elif media_type == 'video':
                    await context.bot.send_video(
                        chat_id=chat.id,
                        video=file_id,
                        caption=formatted_text,
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.HTML
                    )
                elif media_type == 'animation':
                    await context.bot.send_animation(
                        chat_id=chat.id,
                        animation=file_id,
                        caption=formatted_text,
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.HTML
                    )
            else:
                await context.bot.send_message(
                    chat_id=chat.id,
                    text=formatted_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
            
            logger.info(f"Welcome message sent for user {user.id} in chat {chat.id}")
        except Exception as e:
            logger.error(f"Error sending welcome: {e}")

    # ===== WELCOME CUSTOMIZATION =====
    async def setwelcome_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start welcome setup"""
        try:
            if not await self.is_admin(update, context):
                await update.message.reply_text("❌ You need to be admin to use this command.", parse_mode=ParseMode.HTML)
                return ConversationHandler.END
            
            await update.message.reply_text(
                "🎨 <b>Welcome Message Setup</b>\n\n"
                "Please send the welcome text. You can use:\n"
                "• <code>{name}</code> - User's first name\n"
                "• <code>{username}</code> - Username\n" 
                "• <code>{group}</code> - Group name\n"
                "• <code>{mention}</code> - User mention\n"
                "• <code>{id}</code> - User ID\n\n"
                "custom welcome test with mention\n\n"
                "Send /cancel to stop.",
                parse_mode=ParseMode.HTML
            )
            return WELCOME_TEXT
        except Exception as e:
            logger.error(f"Error in setwelcome command: {e}")
            return ConversationHandler.END

    async def set_welcome_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Set welcome text"""
        try:
            chat_id = update.message.chat_id
            welcome_text = update.message.text
            
            if chat_id not in self.group_settings:
                self.group_settings[chat_id] = {}
            
            self.group_settings[chat_id]['welcome_text'] = welcome_text
            self.save_group_settings(chat_id)
            
            await update.message.reply_text(
                "✅ <b>Welcome text set!</b>\n\n"
                "Now send a photo/video/GIF for welcome media or /skip to continue.",
                parse_mode=ParseMode.HTML
            )
            return WELCOME_MEDIA
        except Exception as e:
            logger.error(f"Error setting welcome text: {e}")
            await update.message.reply_text("❌ Error setting welcome text. Please try again.")
            return ConversationHandler.END

    async def set_welcome_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Set welcome media"""
        try:
            chat_id = update.message.chat_id
            
            if update.message.text and update.message.text.lower() == '/skip':
                await update.message.reply_text(
                    "📝 <b>No media set.</b>\n\n"
                    "Now setup welcome buttons:\n"
                    "<code>Button Text - https://example.com</code>\n"
                    "One per line. Multiple rows with |\n"
                    "Send /skip for no buttons",
                    parse_mode=ParseMode.HTML
                )
                return WELCOME_BUTTONS
            
            media_info = {}
            
            if update.message.photo:
                media_info = {'type': 'photo', 'file_id': update.message.photo[-1].file_id}
            elif update.message.video:
                media_info = {'type': 'video', 'file_id': update.message.video.file_id}
            elif update.message.animation:
                media_info = {'type': 'animation', 'file_id': update.message.animation.file_id}
            else:
                await update.message.reply_text("❌ Please send a valid photo, video, or GIF.")
                return WELCOME_MEDIA
            
            self.group_settings[chat_id]['welcome_media'] = media_info
            self.save_group_settings(chat_id)
            
            await update.message.reply_text(
                "✅ <b>Welcome media set!</b>\n\n"
                "Now setup welcome buttons:\n"
                "<code>Button Text - https://example.com</code>\n"
                "One per line. Multiple rows with |\n"
                "Send /skip for no buttons",
                parse_mode=ParseMode.HTML
            )
            return WELCOME_BUTTONS
        except Exception as e:
            logger.error(f"Error setting welcome media: {e}")
            await update.message.reply_text("❌ Error setting welcome media. Please try again.")
            return ConversationHandler.END

    async def set_welcome_buttons(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Set welcome buttons"""
        try:
            chat_id = update.message.chat_id
            
            if update.message.text.lower() == '/skip':
                self.group_settings[chat_id]['welcome_buttons'] = None
                await update.message.reply_text("✅ Welcome setup completed without buttons!")
            else:
                buttons_text = update.message.text
                button_rows = []
                
                rows = buttons_text.split('\n')
                for row in rows:
                    button_row = []
                    row_buttons = row.split(' | ')
                    for btn in row_buttons:
                        if ' - ' in btn:
                            text, url = btn.split(' - ', 1)
                            button_row.append({'text': text.strip(), 'url': url.strip()})
                    if button_row:
                        button_rows.append(button_row)
                
                self.group_settings[chat_id]['welcome_buttons'] = button_rows
                await update.message.reply_text("✅ Welcome setup completed with buttons!")
            
            self.save_group_settings(chat_id)
            return ConversationHandler.END
        except Exception as e:
            logger.error(f"Error setting welcome buttons: {e}")
            await update.message.reply_text("❌ Error setting welcome buttons. Please try again.")
            return ConversationHandler.END

    async def welcome_preview_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Preview welcome message"""
        try:
            chat_id = update.message.chat_id
            settings = self.group_settings.get(chat_id, {})
            
            if not settings.get('welcome_text'):
                await update.message.reply_text("❌ No welcome message set. Use /setwelcome to create one.")
                return
            
            user = update.effective_user
            welcome_text = settings.get('welcome_text', "Welcome {name} to {group}! 🎉")
            formatted_text = welcome_text.format(
                name=user.first_name,
                username=f"@{user.username}" if user.username else user.first_name,
                group=update.effective_chat.title,
                mention=user.mention_html(),
                id=user.id
            )
            
            welcome_media = settings.get('welcome_media')
            welcome_buttons = settings.get('welcome_buttons')
            
            reply_markup = None
            if welcome_buttons:
                keyboard = []
                for btn_row in welcome_buttons:
                    row = []
                    for btn in btn_row:
                        row.append(InlineKeyboardButton(btn['text'], url=btn['url']))
                    keyboard.append(row)
                reply_markup = InlineKeyboardMarkup(keyboard)
            
            if welcome_media:
                media_type = welcome_media['type']
                file_id = welcome_media['file_id']
                
                if media_type == 'photo':
                    await context.bot.send_photo(
                        chat_id=user.id,
                        photo=file_id,
                        caption=f"📸 <b>Welcome Preview:</b>\n\n{formatted_text}",
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.HTML
                    )
                elif media_type == 'video':
                    await context.bot.send_video(
                        chat_id=user.id,
                        video=file_id,
                        caption=f"🎥 <b>Welcome Preview:</b>\n\n{formatted_text}",
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.HTML
                    )
                elif media_type == 'animation':
                    await context.bot.send_animation(
                        chat_id=user.id,
                        animation=file_id,
                        caption=f"🎬 <b>Welcome Preview:</b>\n\n{formatted_text}",
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.HTML
                    )
            else:
                await context.bot.send_message(
                    chat_id=user.id,
                    text=f"👋 <b>Welcome Preview:</b>\n\n{formatted_text}",
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
            
            await update.message.reply_text("✅ Welcome preview sent to your private messages!")
            
        except Exception as e:
            logger.error(f"Error in welcome preview: {e}")
            await update.message.reply_text("❌ Couldn't send preview. Please start the bot in private chat.")

    # ===== TEST COMMANDS =====
    async def testwelcome_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Test welcome message"""
        try:
            if not await self.is_admin(update, context):
                await update.message.reply_text("❌ You need to be admin to use this command.", parse_mode=ParseMode.HTML)
                return
            
            chat = update.effective_chat
            user = update.effective_user
            await self.send_welcome_message(chat, user, context)
            await update.message.reply_text("✅ Test welcome message sent!")
        except Exception as e:
            logger.error(f"Error in testwelcome: {e}")
            await update.message.reply_text("❌ Error sending test welcome.")

    async def testcaptcha_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Test CAPTCHA system"""
        try:
            if not await self.is_admin(update, context):
                await update.message.reply_text("❌ You need to be admin to use this command.", parse_mode=ParseMode.HTML)
                return
            
            test_user = User(
                id=999888777,
                first_name="TestUser",
                is_bot=False,
                username="testuser"
            )
            
            chat = update.effective_chat
            await self.send_captcha(chat, test_user, context)
            await update.message.reply_text("✅ Test CAPTCHA sent!")
        except Exception as e:
            logger.error(f"Error in testcaptcha: {e}")
            await update.message.reply_text("❌ Error sending test CAPTCHA.")

    # ===== RULES SYSTEM =====
    async def setrules_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start rules setup"""
        try:
            if not await self.is_admin(update, context):
                await update.message.reply_text("❌ You need to be admin to use this command.", parse_mode=ParseMode.HTML)
                return ConversationHandler.END
            
            await update.message.reply_text(
                "📜 <b>Rules Setup</b>\n\n"
                "Please send the group rules:\n\n"
                "Send /cancel to stop.",
                parse_mode=ParseMode.HTML
            )
            return RULES_TEXT
        except Exception as e:
            logger.error(f"Error in setrules command: {e}")
            return ConversationHandler.END

    async def set_rules_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Set rules text"""
        try:
            chat_id = update.message.chat_id
            rules_text = update.message.text
            
            if chat_id not in self.group_settings:
                self.group_settings[chat_id] = {}
            
            self.group_settings[chat_id]['rules_text'] = rules_text
            self.save_group_settings(chat_id)
            
            await update.message.reply_text("✅ Rules set successfully!")
            return ConversationHandler.END
        except Exception as e:
            logger.error(f"Error setting rules: {e}")
            await update.message.reply_text("❌ Error setting rules. Please try again.")
            return ConversationHandler.END

    async def rules_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show group rules"""
        try:
            chat_id = update.message.chat_id
            rules_text = self.group_settings.get(chat_id, {}).get('rules_text')
            
            if not rules_text:
                rules_text = (
                    "📜 <b>Group Rules</b>\n\n"
                    "1. 🤝 <b>Respect all trainers</b>\n"
                    "2. 🚫 <b>No spam or off-topic posts</b>\n"
                    "3. ⚡ <b>Pokémon content only</b>\n"
                    "4. 🎮 <b>No cheating/hacking talks</b>\n"
                    "5. ⚠️ <b>Use spoiler tags for new content</b>\n"
                    "6. 💫 <b>Keep it family-friendly</b>\n"
                    "7. 🏆 <b>Battle & trade fairly</b>\n"
                    "8. 📝 <b>English only</b>\n"
                    "9. 👮 <b>Follow staff instructions</b>\n\n"
                    "⚠️ <b>Violations:</b> Warning → Mute → Ban\n"
                    "Let's build a great Pokémon community! 🌟"
                )
            
            await update.message.reply_text(rules_text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Error showing rules: {e}")
            await update.message.reply_text("❌ Error showing rules.")

    # ===== SECURITY SYSTEM =====
    async def antispam_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Toggle anti-spam"""
        try:
            if not await self.is_admin(update, context):
                await update.message.reply_text("❌ You need to be admin to use this command.", parse_mode=ParseMode.HTML)
                return
            
            chat_id = update.message.chat_id
            if chat_id not in self.group_settings:
                self.group_settings[chat_id] = {}
            
            current = self.group_settings[chat_id].get('antispam_enabled', True)
            self.group_settings[chat_id]['antispam_enabled'] = not current
            self.save_group_settings(chat_id)
            
            status = "enabled" if not current else "disabled"
            await update.message.reply_text(f"✅ Anti-spam protection {status}!")
        except Exception as e:
            logger.error(f"Error toggling antispam: {e}")
            await update.message.reply_text("❌ Error toggling anti-spam.")

    async def captcha_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Toggle CAPTCHA"""
        try:
            if not await self.is_admin(update, context):
                await update.message.reply_text("❌ You need to be admin to use this command.", parse_mode=ParseMode.HTML)
                return
            
            chat_id = update.message.chat_id
            if chat_id not in self.group_settings:
                self.group_settings[chat_id] = {}
            
            current = self.group_settings[chat_id].get('captcha_enabled', False)
            self.group_settings[chat_id]['captcha_enabled'] = not current
            self.save_group_settings(chat_id)
            
            status = "enabled" if not current else "disabled"
            await update.message.reply_text(f"✅ CAPTCHA verification {status}!")
        except Exception as e:
            logger.error(f"Error toggling CAPTCHA: {e}")
            await update.message.reply_text("❌ Error toggling CAPTCHA.")

    async def send_captcha(self, chat: Chat, user: User, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send CAPTCHA verification only"""
        try:
            num1 = random.randint(1, 10)
            num2 = random.randint(1, 10)
            operation = random.choice(['+', '-', '*'])
            
            if operation == '+':
                answer = num1 + num2
            elif operation == '-':
                answer = num1 - num2
            else:
                answer = num1 * num2
            
            captcha_text = (
                f"🔒 <b>CAPTCHA Verification for {user.mention_html()}</b>\n\n"
                f"Please solve: <code>{num1} {operation} {num2} = ?</code>\n\n"
                f"⏰ You have 5 minutes to solve this!\n"
                f"⚠️ <i>You need to solve this to continue chatting!</i>"
            )
            captcha_code = str(answer)
            
            key = f"{chat.id}_{user.id}"
            self.user_captchas[key] = {
                'code': captcha_code,
                'expires': datetime.now() + timedelta(minutes=5),
                'user_id': user.id,
                'chat_id': chat.id,
                'current_answer': ''
            }
            
            keyboard = [
                [InlineKeyboardButton("1", callback_data=f"captcha_{user.id}_1"),
                InlineKeyboardButton("2", callback_data=f"captcha_{user.id}_2"),
                InlineKeyboardButton("3", callback_data=f"captcha_{user.id}_3")],
                [InlineKeyboardButton("4", callback_data=f"captcha_{user.id}_4"),
                InlineKeyboardButton("5", callback_data=f"captcha_{user.id}_5"),
                InlineKeyboardButton("6", callback_data=f"captcha_{user.id}_6")],
                [InlineKeyboardButton("7", callback_data=f"captcha_{user.id}_7"),
                InlineKeyboardButton("8", callback_data=f"captcha_{user.id}_8"),
                InlineKeyboardButton("9", callback_data=f"captcha_{user.id}_9")],
                [InlineKeyboardButton("0", callback_data=f"captcha_{user.id}_0"),
                InlineKeyboardButton("Submit", callback_data=f"captcha_{user.id}_submit")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            captcha_msg = await context.bot.send_message(
                chat_id=chat.id,
                text=captcha_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            
            self.user_captchas[key]['message_id'] = captcha_msg.message_id
            logger.info(f"CAPTCHA sent for user {user.id}: {num1}{operation}{num2}={answer}")
            
        except Exception as e:
            logger.error(f"Error sending CAPTCHA: {e}")

    async def handle_captcha_answer(self, query, user_id, answer, context):
        """Handle CAPTCHA answer"""
        try:
            chat_id = query.message.chat.id
            key = f"{chat_id}_{user_id}"
            
            captcha_data = self.user_captchas.get(key)
            
            if not captcha_data:
                await query.answer("❌ CAPTCHA expired or not found!", show_alert=True)
                return
            
            if datetime.now() > captcha_data['expires']:
                await query.answer("❌ CAPTCHA expired! Please wait for admin help.", show_alert=True)
                del self.user_captchas[key]
                return
            
            if answer == "submit":
                user_answer = captcha_data.get('current_answer', '')
                if user_answer == captcha_data['code']:
                    # CAPTCHA solved successfully - DON'T send welcome again
                    await query.edit_message_text(
                        "✅ <b>CAPTCHA verified! You can now chat in the group! 🎉</b>", 
                        parse_mode=ParseMode.HTML
                    )
                    
                    # Delete CAPTCHA message after 5 seconds
                    await context.application.job_queue.run_once(
                        self.delete_message,
                        5,
                        data=chat_id,
                        name=f"delete_{query.message.message_id}"
                    )
                    
                    # Welcome was already sent when user joined, so no need to send again
                    del self.user_captchas[key]
                else:
                    await query.answer("❌ Wrong answer! Try again.", show_alert=True)
                return
            
            # Handle number button presses (keep existing code)
            captcha_data['current_answer'] += answer
            
            keyboard = [
                [InlineKeyboardButton("1", callback_data=f"captcha_{user_id}_1"),
                InlineKeyboardButton("2", callback_data=f"captcha_{user_id}_2"),
                InlineKeyboardButton("3", callback_data=f"captcha_{user_id}_3")],
                [InlineKeyboardButton("4", callback_data=f"captcha_{user_id}_4"),
                InlineKeyboardButton("5", callback_data=f"captcha_{user_id}_5"),
                InlineKeyboardButton("6", callback_data=f"captcha_{user_id}_6")],
                [InlineKeyboardButton("7", callback_data=f"captcha_{user_id}_7"),
                InlineKeyboardButton("8", callback_data=f"captcha_{user_id}_8"),
                InlineKeyboardButton("9", callback_data=f"captcha_{user_id}_9")],
                [InlineKeyboardButton("0", callback_data=f"captcha_{user_id}_0"),
                InlineKeyboardButton(f"Submit: {captcha_data['current_answer']}", callback_data=f"captcha_{user_id}_submit")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            original_text = query.message.text
            await query.edit_message_text(
                text=original_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            
            await query.answer(f"Entered: {captcha_data['current_answer']}")
        except Exception as e:
            logger.error(f"Error handling CAPTCHA answer: {e}")

    # ===== MODERATION SYSTEM =====
    async def warn_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Warn a user"""
        try:
            if not await self.is_admin(update, context):
                await update.message.reply_text("❌ You need to be admin to use this command.", parse_mode=ParseMode.HTML)
                return
            
            if not context.args:
                await update.message.reply_text("Usage: <code>/warn @username reason</code>", parse_mode=ParseMode.HTML)
                return
            
            target_user = await self.extract_user(update, context)
            if not target_user:
                await update.message.reply_text("❌ User not found.")
                return
            
            reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "No reason provided"
            chat_id = update.message.chat_id
            
            self.cursor.execute(
                "INSERT INTO user_warnings (user_id, chat_id, reason, admin_id) VALUES (?, ?, ?, ?)",
                (target_user.id, chat_id, reason, update.effective_user.id)
            )
            self.conn.commit()
            
            self.cursor.execute(
                "SELECT COUNT(*) FROM user_warnings WHERE user_id = ? AND chat_id = ?",
                (target_user.id, chat_id)
            )
            warning_count = self.cursor.fetchone()[0]
            
            max_warnings = self.group_settings.get(chat_id, {}).get('max_warnings', 3)
            
            warning_msg = (
                f"⚠️ <b>Warning {warning_count}/{max_warnings}</b>\n"
                f"👤 User: {target_user.mention_html()}\n"
                f"📝 Reason: {reason}\n"
                f"🛡️ By: {update.effective_user.mention_html()}"
            )
            
            await update.message.reply_text(warning_msg, parse_mode=ParseMode.HTML)
            
            if warning_count >= max_warnings:
                await self.ban_user_automatically(chat_id, target_user.id, context, "Maximum warnings reached")
        except Exception as e:
            logger.error(f"Error warning user: {e}")
            await update.message.reply_text("❌ Error warning user.")

    async def ban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Ban a user"""
        try:
            if not await self.is_admin(update, context):
                await update.message.reply_text("❌ You need to be admin to use this command.", parse_mode=ParseMode.HTML)
                return
            
            target_user = await self.extract_user(update, context)
            if not target_user:
                await update.message.reply_text("❌ User not found.")
                return
            
            reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "No reason provided"
            
            await context.bot.ban_chat_member(
                chat_id=update.message.chat_id,
                user_id=target_user.id
            )
            
            ban_msg = (
                f"🔨 <b>User Banned</b>\n"
                f"👤 User: {target_user.mention_html()}\n"
                f"📝 Reason: {reason}\n"
                f"🛡️ By: {update.effective_user.mention_html()}"
            )
            
            await update.message.reply_text(ban_msg, parse_mode=ParseMode.HTML)
            
        except Exception as e:
            logger.error(f"Error banning user: {e}")
            await update.message.reply_text("❌ Error banning user.")

    async def mute_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Mute a user"""
        try:
            if not await self.is_admin(update, context):
                await update.message.reply_text("❌ You need to be admin to use this command.", parse_mode=ParseMode.HTML)
                return
            
            target_user = await self.extract_user(update, context)
            if not target_user:
                await update.message.reply_text("❌ User not found.")
                return
            
            permissions = ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False
            )
            
            await context.bot.restrict_chat_member(
                chat_id=update.message.chat_id,
                user_id=target_user.id,
                permissions=permissions
            )
            
            mute_msg = f"🔇 User {target_user.mention_html()} has been muted."
            await update.message.reply_text(mute_msg, parse_mode=ParseMode.HTML)
            
        except Exception as e:
            logger.error(f"Error muting user: {e}")
            await update.message.reply_text("❌ Error muting user.")

    async def unmute_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Unmute a user"""
        try:
            if not await self.is_admin(update, context):
                await update.message.reply_text("❌ You need to be admin to use this command.", parse_mode=ParseMode.HTML)
                return
            
            target_user = await self.extract_user(update, context)
            if not target_user:
                await update.message.reply_text("❌ User not found.")
                return
            
            permissions = ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_change_info=False,
                can_invite_users=True,
                can_pin_messages=False
            )
            
            await context.bot.restrict_chat_member(
                chat_id=update.message.chat_id,
                user_id=target_user.id,
                permissions=permissions
            )
            
            await update.message.reply_text(f"🔊 User {target_user.mention_html()} has been unmuted.", parse_mode=ParseMode.HTML)
            
        except Exception as e:
            logger.error(f"Error unmuting user: {e}")
            await update.message.reply_text("❌ Error unmuting user.")

    async def kick_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Kick a user"""
        try:
            if not await self.is_admin(update, context):
                await update.message.reply_text("❌ You need to be admin to use this command.", parse_mode=ParseMode.HTML)
                return
            
            target_user = await self.extract_user(update, context)
            if not target_user:
                await update.message.reply_text("❌ User not found.")
                return
            
            await context.bot.ban_chat_member(
                chat_id=update.message.chat_id,
                user_id=target_user.id,
                until_date=datetime.now() + timedelta(seconds=30)
            )
            
            await update.message.reply_text(f"👢 User {target_user.mention_html()} has been kicked.", parse_mode=ParseMode.HTML)
            
        except Exception as e:
            logger.error(f"Error kicking user: {e}")
            await update.message.reply_text("❌ Error kicking user.")

    async def unban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Unban a user"""
        try:
            if not await self.is_admin(update, context):
                await update.message.reply_text("❌ You need to be admin to use this command.", parse_mode=ParseMode.HTML)
                return
            
            target_user = await self.extract_user(update, context)
            if not target_user:
                await update.message.reply_text("❌ User not found.")
                return
            
            await context.bot.unban_chat_member(
                chat_id=update.message.chat_id,
                user_id=target_user.id
            )
            
            await update.message.reply_text(f"✅ User {target_user.mention_html()} has been unbanned.", parse_mode=ParseMode.HTML)
            
        except Exception as e:
            logger.error(f"Error unbanning user: {e}")
            await update.message.reply_text("❌ Error unbanning user.")

    async def warnings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Check user warnings"""
        try:
            target_user = await self.extract_user(update, context)
            if not target_user:
                await update.message.reply_text("❌ User not found.")
                return
            
            chat_id = update.message.chat_id
            
            self.cursor.execute(
                "SELECT reason, timestamp FROM user_warnings WHERE user_id = ? AND chat_id = ? ORDER BY timestamp DESC",
                (target_user.id, chat_id)
            )
            warnings = self.cursor.fetchall()
            
            if not warnings:
                await update.message.reply_text(f"✅ User {target_user.mention_html()} has no warnings.", parse_mode=ParseMode.HTML)
                return
            
            warning_list = "\n".join([f"• {w[0]} ({w[1]})" for w in warnings])
            await update.message.reply_text(
                f"⚠️ <b>Warnings for {target_user.mention_html()} ({len(warnings)}):</b>\n\n{warning_list}",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Error checking warnings: {e}")
            await update.message.reply_text("❌ Error checking warnings.")

    async def clear_warnings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Clear user warnings"""
        try:
            if not await self.is_admin(update, context):
                await update.message.reply_text("❌ You need to be admin to use this command.", parse_mode=ParseMode.HTML)
                return
            
            target_user = await self.extract_user(update, context)
            if not target_user:
                await update.message.reply_text("❌ User not found.")
                return
            
            chat_id = update.message.chat_id
            
            self.cursor.execute(
                "DELETE FROM user_warnings WHERE user_id = ? AND chat_id = ?",
                (target_user.id, chat_id)
            )
            self.conn.commit()
            
            await update.message.reply_text(f"✅ Warnings cleared for {target_user.mention_html()}.", parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Error clearing warnings: {e}")
            await update.message.reply_text("❌ Error clearing warnings.")

    # ===== BANNED WORDS SYSTEM =====
    async def add_banned_word_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Add banned word"""
        try:
            if not await self.is_admin(update, context):
                await update.message.reply_text("❌ You need to be admin to use this command.", parse_mode=ParseMode.HTML)
                return
            
            if not context.args:
                await update.message.reply_text("Usage: <code>/addword word [delete|warn|mute]</code>", parse_mode=ParseMode.HTML)
                return
            
            word = context.args[0].lower()
            action = context.args[1] if len(context.args) > 1 else "delete"
            
            if action not in ['delete', 'warn', 'mute']:
                await update.message.reply_text("❌ Action must be: delete, warn, or mute")
                return
            
            chat_id = update.message.chat_id
            
            self.cursor.execute(
                "INSERT INTO banned_words (chat_id, word, action, created_by) VALUES (?, ?, ?, ?)",
                (chat_id, word, action, update.effective_user.id)
            )
            self.conn.commit()
            
            if chat_id not in self.banned_words:
                self.banned_words[chat_id] = []
            self.banned_words[chat_id].append({'word': word, 'action': action})
            
            await update.message.reply_text(f"✅ Banned word added: '<code>{word}</code>' with action: <code>{action}</code>", parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Error adding banned word: {e}")
            await update.message.reply_text("❌ Error adding banned word.")

    async def del_banned_word_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Remove banned word"""
        try:
            if not await self.is_admin(update, context):
                await update.message.reply_text("❌ You need to be admin to use this command.", parse_mode=ParseMode.HTML)
                return
            
            if not context.args:
                await update.message.reply_text("Usage: <code>/delword word</code>", parse_mode=ParseMode.HTML)
                return
            
            word = context.args[0].lower()
            chat_id = update.message.chat_id
            
            self.cursor.execute(
                "DELETE FROM banned_words WHERE chat_id = ? AND word = ?",
                (chat_id, word)
            )
            self.conn.commit()
            
            if chat_id in self.banned_words:
                self.banned_words[chat_id] = [w for w in self.banned_words[chat_id] if w['word'] != word]
            
            await update.message.reply_text(f"✅ Banned word removed: '<code>{word}</code>'", parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Error removing banned word: {e}")
            await update.message.reply_text("❌ Error removing banned word.")

    async def list_banned_words_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """List banned words"""
        try:
            if not await self.is_admin(update, context):
                await update.message.reply_text("❌ You need to be admin to use this command.", parse_mode=ParseMode.HTML)
                return
            
            chat_id = update.message.chat_id
            words = self.banned_words.get(chat_id, [])
            
            if not words:
                await update.message.reply_text("📝 No banned words set for this group.")
                return
            
            word_list = "\n".join([f"• <code>{w['word']}</code> ({w['action']})" for w in words])
            await update.message.reply_text(f"🚫 <b>Banned Words:</b>\n\n{word_list}", parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Error listing banned words: {e}")
            await update.message.reply_text("❌ Error listing banned words.")

    # ===== MESSAGE HANDLERS =====
    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages"""
        try:
            chat_id = update.message.chat_id
            text = update.message.text or update.message.caption or ""
            
            if self.group_settings.get(chat_id, {}).get('antispam_enabled', True):
                await self.anti_spam_check(update, context)
            
            await self.banned_words_check(update, context, text.lower())
        except Exception as e:
            logger.error(f"Error in message handler: {e}")

    async def media_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle media messages"""
        try:
            chat_id = update.message.chat_id
            if self.group_settings.get(chat_id, {}).get('antispam_enabled', True):
                await self.anti_spam_check(update, context)
        except Exception as e:
            logger.error(f"Error in media handler: {e}")

    async def anti_spam_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Check for spam"""
        try:
            user_id = update.effective_user.id
            chat_id = update.effective_chat.id
            
            if user_id not in self.user_message_count:
                self.user_message_count[user_id] = {'count': 0, 'last_time': datetime.now()}
            
            user_data = self.user_message_count[user_id]
            current_time = datetime.now()
            
            if (current_time - user_data['last_time']).seconds > 10:
                user_data['count'] = 0
            
            user_data['count'] += 1
            user_data['last_time'] = current_time
            
            if user_data['count'] > 5:
                await context.bot.delete_message(chat_id, update.message.message_id)
                warning_msg = await context.bot.send_message(
                    chat_id,
                    f"⚠️ {update.effective_user.mention_html()} - Please don't spam!",
                    parse_mode=ParseMode.HTML
                )
                
                await context.application.job_queue.run_once(
                    self.delete_message,
                    5,
                    data=warning_msg.chat_id,
                    name=f"delete_{warning_msg.message_id}"
                )
        except Exception as e:
            logger.error(f"Error in anti-spam: {e}")

    async def banned_words_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
        """Check for banned words"""
        try:
            chat_id = update.effective_chat.id
            words = self.banned_words.get(chat_id, [])
            
            for banned_word in words:
                if banned_word['word'] in text:
                    action = banned_word['action']
                    
                    await context.bot.delete_message(chat_id, update.message.message_id)
                    
                    if action == "warn":
                        self.cursor.execute(
                            "INSERT INTO user_warnings (user_id, chat_id, reason, admin_id) VALUES (?, ?, ?, ?)",
                            (update.effective_user.id, chat_id, f"Used banned word: {banned_word['word']}", context.bot.id)
                        )
                        self.conn.commit()
                        
                        await context.bot.send_message(
                            chat_id,
                            f"⚠️ {update.effective_user.mention_html()} - Warning for using banned word!",
                            parse_mode=ParseMode.HTML
                        )
                        
                    elif action == "mute":
                        permissions = ChatPermissions(can_send_messages=False)
                        await context.bot.restrict_chat_member(
                            chat_id=chat_id,
                            user_id=update.effective_user.id,
                            permissions=permissions,
                            until_date=datetime.now() + timedelta(hours=1)
                        )
                        
                        await context.bot.send_message(
                            chat_id,
                            f"🔇 {update.effective_user.mention_html()} - Muted for 1 hour for using banned word!",
                            parse_mode=ParseMode.HTML
                        )
                    break
        except Exception as e:
            logger.error(f"Error handling banned word: {e}")

    # ===== UTILITY METHODS =====
    async def is_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Check if user is admin"""
        try:
            user = update.effective_user
            chat = update.effective_chat
            
            # Add your admin IDs here
            if user.id in [6468620868]:
                return True
            
            chat_member = await context.bot.get_chat_member(chat.id, user.id)
            return chat_member.status in ['administrator', 'creator']
        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
            return False

    async def extract_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[User]:
        """Extract user from command"""
        try:
            if not context.args:
                return None
            
            if update.message.reply_to_message:
                return update.message.reply_to_message.from_user
            
            target = context.args[0]
            
            if target.startswith('@'):
                target = target[1:]
            
            try:
                user_id = int(target)
                return await context.bot.get_chat(user_id)
            except ValueError:
                return None
        except Exception as e:
            logger.error(f"Error extracting user: {e}")
            return None

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle inline keyboard button presses"""
        try:
            query = update.callback_query
            await query.answer()
            
            data = query.data
            
            if data.startswith("welcome_"):
                if data == "welcome_rules":
                    await self.rules_command(update, context)
                elif data == "welcome_help":
                    await self.help_command(update, context)
            
            elif data.startswith("captcha_"):
                parts = data.split('_')
                if len(parts) >= 3:
                    user_id = int(parts[1])
                    answer = parts[2]
                    await self.handle_captcha_answer(query, user_id, answer, context)
            
            elif data.startswith("security_"):
                if data == "security_antispam":
                    await self.antispam_command(update, context)
                elif data == "security_captcha":
                    await self.captcha_command(update, context)
                elif data == "security_words":
                    await self.list_banned_words_command(update, context)
        except Exception as e:
            logger.error(f"Error in button handler: {e}")

    async def delete_message(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Delete a message"""
        try:
            await context.bot.delete_message(context.job.data, context.job.name.replace('delete_', ''))
        except Exception as e:
            logger.error(f"Error deleting message: {e}")

    async def ban_user_automatically(self, chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE, reason: str) -> None:
        """Auto-ban user"""
        try:
            await context.bot.ban_chat_member(chat_id, user_id)
            
            self.cursor.execute(
                "DELETE FROM user_warnings WHERE user_id = ? AND chat_id = ?",
                (user_id, chat_id)
            )
            self.conn.commit()
            
            await context.bot.send_message(
                chat_id,
                f"🔨 <b>User auto-banned for:</b> {reason}",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Error auto-banning user: {e}")

    # ===== BASIC COMMANDS =====
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start command"""
        try:
            user = update.effective_user
            start_text = (
                f"👋 <b>Hello {user.mention_html()}!</b>\n\n"
                "I'm an advanced security and welcome bot for Telegram groups.\n\n"
                "🔧 <b>Main Features:</b>\n"
                "• Custom welcome messages with media\n"
                "• Advanced security system\n"
                "• Moderation tools\n"
                "• Anti-spam protection\n"
                "• CAPTCHA verification\n"
                "• Banned words filter\n\n"
                "Use /help to see all commands!"
            )
            
            await update.message.reply_text(start_text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Error in start command: {e}")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Help command"""
        try:
            help_text = (
                "🛠️ <b>Bot Commands</b>\n\n"
                "👥 <b>For Everyone:</b>\n"
                "/start - Start the bot\n"
                "/help - Show this help\n"
                "/rules - Group rules\n"
                "/report - Report a user\n"
                "/welcome - Preview welcome message\n\n"
                "🎨 <b>Welcome System (Admins):</b>\n"
                "/setwelcome - Setup welcome message\n"
                "/setrules - Set group rules\n\n"
                "🛡️ <b>Security (Admins):</b>\n"
                "/security - Security settings\n"
                "/antispam - Toggle anti-spam\n"
                "/captcha - Toggle CAPTCHA\n"
                "/addword - Add banned word\n"
                "/delword - Remove banned word\n"
                "/listwords - List banned words\n\n"
                "🔧 <b>Moderation (Admins):</b>\n"
                "/warn - Warn a user\n"
                "/mute - Mute a user\n"
                "/ban - Ban a user\n"
                "/kick - Kick a user\n"
                "/unmute - Unmute a user\n"
                "/unban - Unban a user\n"
                "/warnings - Check user warnings\n"
                "/clearwarns - Clear user warnings\n"
                "/settings - Bot settings\n"
                "/stats - Group statistics\n"
            )
            
            await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Error in help command: {e}")

    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show settings"""
        try:
            if not await self.is_admin(update, context):
                await update.message.reply_text("❌ You need to be admin to use this command.", parse_mode=ParseMode.HTML)
                return
            
            chat_id = update.message.chat_id
            settings = self.group_settings.get(chat_id, {})
            
            settings_text = (
                "⚙️ <b>Bot Settings</b>\n\n"
                f"Welcome Enabled: {'✅' if settings.get('welcome_enabled', True) else '❌'}\n"
                f"Anti-Spam: {'✅' if settings.get('antispam_enabled', True) else '❌'}\n"
                f"CAPTCHA: {'✅' if settings.get('captcha_enabled', False) else '❌'}\n"
                f"Max Warnings: {settings.get('max_warnings', 3)}\n"
                f"Security Level: {settings.get('security_level', 1)}\n\n"
                f"Banned Words: {len(self.banned_words.get(chat_id, []))}\n"
            )
            
            await update.message.reply_text(settings_text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Error in settings command: {e}")

    async def security_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Security settings"""
        try:
            if not await self.is_admin(update, context):
                await update.message.reply_text("❌ You need to be admin to use this command.", parse_mode=ParseMode.HTML)
                return
            
            chat_id = update.message.chat_id
            settings = self.group_settings.get(chat_id, {})
            
            security_text = (
                "🛡️ <b>Security Settings</b>\n\n"
                f"Anti-Spam: {'✅ ON' if settings.get('antispam_enabled', True) else '❌ OFF'}\n"
                f"CAPTCHA: {'✅ ON' if settings.get('captcha_enabled', False) else '❌ OFF'}\n"
                f"Max Warnings: {settings.get('max_warnings', 3)}\n\n"
                "<b>Commands:</b>\n"
                "/antispam - Toggle anti-spam\n"
                "/captcha - Toggle CAPTCHA\n"
                "/addword - Add banned word\n"
                "/listwords - Show banned words"
            )
            
            await update.message.reply_text(security_text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Error in security command: {e}")

    async def report_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Report a user"""
        try:
            if not context.args:
                await update.message.reply_text("Usage: <code>/report @username reason</code>", parse_mode=ParseMode.HTML)
                return
            
            target_user = await self.extract_user(update, context)
            if not target_user:
                await update.message.reply_text("❌ User not found.")
                return
            
            reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "No reason provided"
            
            report_msg = (
                f"🚨 <b>User Report</b>\n"
                f"👤 Reported User: {target_user.mention_html()}\n"
                f"📝 Reason: {reason}\n"
                f"🛡️ Reported by: {update.effective_user.mention_html()}\n"
                f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            await update.message.reply_text("✅ Report sent to admins.")
            logger.info(f"User report: {report_msg}")
        except Exception as e:
            logger.error(f"Error in report command: {e}")
            await update.message.reply_text("❌ Error sending report.")

    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """User info"""
        try:
            target_user = await self.extract_user(update, context) or update.effective_user
            
            info_text = (
                f"👤 <b>User Info</b>\n\n"
                f"🆔 ID: <code>{target_user.id}</code>\n"
                f"📛 Name: {target_user.first_name}\n"
                f"👥 Username: @{target_user.username if target_user.username else 'N/A'}\n"
                f"📅 Language: {target_user.language_code if target_user.language_code else 'N/A'}\n"
            )
            
            await update.message.reply_text(info_text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Error in info command: {e}")
            await update.message.reply_text("❌ Error getting user info.")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Group statistics"""
        try:
            chat_id = update.message.chat_id
            
            self.cursor.execute("SELECT COUNT(*) FROM user_warnings WHERE chat_id = ?", (chat_id,))
            total_warnings = self.cursor.fetchone()[0]
            
            self.cursor.execute("SELECT COUNT(DISTINCT user_id) FROM user_warnings WHERE chat_id = ?", (chat_id,))
            warned_users = self.cursor.fetchone()[0]
            
            stats_text = (
                f"📊 <b>Group Statistics</b>\n\n"
                f"⚠️ Total Warnings: {total_warnings}\n"
                f"👥 Warned Users: {warned_users}\n"
                f"🚫 Banned Words: {len(self.banned_words.get(chat_id, []))}\n"
                f"🛡️ Security Level: {self.group_settings.get(chat_id, {}).get('security_level', 1)}"
            )
            
            await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Error in stats command: {e}")
            await update.message.reply_text("❌ Error getting statistics.")

    async def members_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Group members count"""
        try:
            chat = update.effective_chat
            members_count = await context.bot.get_chat_members_count(chat.id)
            await update.message.reply_text(f"👥 <b>Group Members:</b> {members_count}", parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Error in members command: {e}")
            await update.message.reply_text("❌ Could not get members count.")

    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel conversation"""
        try:
            await update.message.reply_text("❌ Setup cancelled.")
            return ConversationHandler.END
        except Exception as e:
            logger.error(f"Error in cancel command: {e}")
            return ConversationHandler.END

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors"""
        try:
            logger.error(f"Exception while handling update: {context.error}")
            
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ An error occurred. Please try again later.",
                    parse_mode=ParseMode.HTML
                )
        except Exception as e:
            logger.error(f"Error in error handler: {e}")

    def run(self):
        """Start the bot"""
        try:
            logger.info("Starting Advanced Welcome Security Bot...")
            self.application.run_polling(allowed_updates=Update.ALL_TYPES)
        except Exception as e:
            logger.error(f"Error running bot: {e}")

# Main execution
# Add this at the VERY END of your bot.py file:
if __name__ == '__main__':
    import os
    BOT_TOKEN = os.getenv('BOT_TOKEN') or "8228108336:AAF3OWn5-nYQjEZhNactyldXV9FW9kTtq9k"
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Please set your BOT_TOKEN environment variable!")
    else:
        bot = AdvancedWelcomeSecurityBot(BOT_TOKEN)
        bot.run()
