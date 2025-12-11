import logging
import os
import logging
import os
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
import config
from services.llm_service import LLMService
from services.x_service import XService
from services.automation_service import AutomationService
from apscheduler.schedulers.background import BackgroundScheduler
import re
from utils.calendar_utils import create_calendar, process_calendar_selection, CALENDAR_CALLBACK

# Define states for ConversationHandler
TOPIC, TONE, REVIEW = range(3)
# Define states for Automation Handler
AUTO_DATES, AUTO_COUNT, AUTO_THEMES = range(3, 6)
# Callback data prefix for themes
THEME_PREFIX = "THEME_"
DONE_ACTION = "DONE_THEMES"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

llm_service = LLMService()
x_service = XService()
automation_service = AutomationService()

# Scheduler Setup
scheduler = BackgroundScheduler()
# Run check_and_post every 30 minutes
scheduler.add_job(automation_service.check_and_post, 'interval', minutes=30)
scheduler.start()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Hi! Send me a topic or thought, and I'll generate a tweet for you.")
    return TOPIC

async def check_terminate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Checks if the user sent 'terminate' and resets the flow if so."""
    if update.message and update.message.text and update.message.text.strip().lower() == 'terminate':
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text="🛑 Operation terminated. Reseting to start... Send me a new topic."
        )
        # Clear context
        keys_to_clear = ['topic', 'tone', 'mode', 'tweet', 'tweet_a', 'tweet_b', 'media_paths', 'auto_start', 'auto_end', 'auto_count', 'selected_themes', 'cal_step']
        for key in keys_to_clear:
            context.user_data.pop(key, None)
            
        return True
    return False

async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check terminate
    if await check_terminate(update, context):
        return TOPIC

    user_topic = update.message.text
    context.user_data['topic'] = user_topic # Save topic
    # Reset media on new topic
    context.user_data['media_paths'] = []
    
    keyboard = [
        [InlineKeyboardButton("Human 🙋‍♂️", callback_data='Human'), InlineKeyboardButton("Professional 💼", callback_data='Professional')],
        [InlineKeyboardButton("Funny 😂", callback_data='Funny'), InlineKeyboardButton("Logical 🧠", callback_data='Logical')],
        [InlineKeyboardButton("Technical 💻", callback_data='Technical'), InlineKeyboardButton("Mathematical 🔢", callback_data='Mathematical')],
        [InlineKeyboardButton("🆚 A/B Options (Dual Tone)", callback_data='AB_TEST')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Topic: {user_topic}\n\nChoose a tone:", reply_markup=reply_markup)
    return TONE

async def handle_tone_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text input during TONE state (mainly for terminate)."""
    if await check_terminate(update, context):
        return TOPIC
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Please select a tone from the buttons above, or type 'terminate' to restart.")
    return TONE

async def handle_tone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_topic = context.user_data.get('topic')
    
    if data == 'AB_TEST':
        # Generate two variants
        tone_a = "Professional"
        tone_b = "Human" # Contrasting simple tone
        
        await query.edit_message_text(text=f"Generating A/B variants ({tone_a} vs {tone_b}) for: {user_topic}...")
        
        tweet_a = llm_service.generate_tweet(user_topic, tone=tone_a)
        tweet_b = llm_service.generate_tweet(user_topic, tone=tone_b)
        
        if not tweet_a or not tweet_b:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, 
                text="⚠️ Failed to generate one or both tweet variants. Please try again with a different topic."
            )
            return ConversationHandler.END
            
        context.user_data['tweet_a'] = tweet_a
        context.user_data['tweet_b'] = tweet_b
        context.user_data['mode'] = 'ab'
        
        msg = (
            f"🆚 **A/B Testing**\n\n"
            f"🅰️ **Option A ({tone_a}):**\n{tweet_a}\n\n"
            f"🅱️ **Option B ({tone_b}):**\n{tweet_b}\n\n"
            f"Reply 'A' to choose Option A, 'B' to choose Option B, or edit manually."
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')
        return REVIEW

    else:
        # Single tone
        tone = data
        context.user_data['tone'] = tone
        context.user_data['mode'] = 'single'
        
        await query.edit_message_text(text=f"Generating {tone} tweet for: {user_topic}...")
        
        generated_tweet = llm_service.generate_tweet(user_topic, tone=tone)
        
        if not generated_tweet:
            # Send message + return TOPIC to allow retry immediately
            await context.bot.send_message(
                chat_id=update.effective_chat.id, 
                text="⚠️ Failed to generate a valid tweet (length limit or content policy). Send me a new topic to try again."
            )
            return TOPIC # Changed from END to TOPIC for better flow

        context.user_data['tweet'] = generated_tweet
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=f"Here is the draft ({tone}):\n\n{generated_tweet}\n\nReply with 'send' to post, attach photos, or type a new version to update."
        )
        return REVIEW

async def handle_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    if user_input:
        user_input = user_input.strip()
        if user_input.lower() == 'terminate':
             # Use the common check logic manually here since we need to return
             await context.bot.send_message(chat_id=update.effective_chat.id, text="🛑 Operation terminated. Send me a new topic.")
             return TOPIC

    # Check for Photo
    if update.message.photo:
        # Get the largest photo file
        photo_file = await update.message.photo[-1].get_file()
        file_path = f"temp_{photo_file.file_id}.jpg"
        await photo_file.download_to_drive(file_path)
        
        if 'media_paths' not in context.user_data:
            context.user_data['media_paths'] = []
        
        context.user_data['media_paths'].append(file_path)
        
        count = len(context.user_data['media_paths'])
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Photo attached! ({count} total). Reply 'send' to post or attach more.")
        return REVIEW
    
    # Handle Regeneration Request
    if user_input.lower() in ['change', 'retry', 'regenerate']:
        user_topic = context.user_data.get('topic')
        
        # Check if we are in A/B mode
        if context.user_data.get('mode') == 'ab':
            tone_a = "Professional"
            tone_b = "Human" 
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"🔄 Regenerating A/B variants for: {user_topic}...")
            
            tweet_a = llm_service.generate_tweet(user_topic, tone=tone_a)
            tweet_b = llm_service.generate_tweet(user_topic, tone=tone_b)
            
            if not tweet_a or not tweet_b:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="⚠️ Failed to regenerate. Please try again or edit manually.")
                return REVIEW
                
            context.user_data['tweet_a'] = tweet_a
            context.user_data['tweet_b'] = tweet_b
            
            msg = (
                f"🆚 **New A/B Variants**\n\n"
                f"🅰️ **Option A ({tone_a}):**\n{tweet_a}\n\n"
                f"🅱️ **Option B ({tone_b}):**\n{tweet_b}\n\n"
                f"Reply 'A', 'B' to choose, or 'change' again."
            )
            await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')
            return REVIEW
            
        else:
            # Single Tone Mode
            tone = context.user_data.get('tone', 'Professional')
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"🔄 Regenerating {tone} tweet...")
            
            new_tweet = llm_service.generate_tweet(user_topic, tone=tone)
            
            if not new_tweet:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="⚠️ Failed to regenerate. Please edit manually.")
                return REVIEW
                
            context.user_data['tweet'] = new_tweet
            await context.bot.send_message(
                chat_id=update.effective_chat.id, 
                text=f"🆕 **New Draft** ({tone}):\n\n{new_tweet}\n\nReply 'send' to post, 'change' to try again, or type your own version."
            )
            return REVIEW

    # Handle A/B Selection
    if context.user_data.get('mode') == 'ab':
        if user_input.upper() in ['A', 'OPTION A']:
            context.user_data['tweet'] = context.user_data['tweet_a']
            context.user_data['mode'] = 'single' # Switch to single to allow sending next
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Selected Option A. Reply 'send' to post it.")
            return REVIEW
        elif user_input.upper() in ['B', 'OPTION B']:
            context.user_data['tweet'] = context.user_data['tweet_b']
            context.user_data['mode'] = 'single'
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Selected Option B. Reply 'send' to post it.")
            return REVIEW

    if user_input.lower() == 'send':
        tweet_content = context.user_data.get('tweet')
        media_paths = context.user_data.get('media_paths', [])
        
        if tweet_content:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Posting to X...")
            
            success = x_service.post_tweet(tweet_content, media_paths=media_paths)
            
            # Cleanup temp files
            for path in media_paths:
                try:
                    os.remove(path)
                except Exception as e:
                    logging.error(f"Failed to delete temp file {path}: {e}")
            context.user_data['media_paths'] = [] # Reset

            if success:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="Posted successfully! \u2705")
            else:
                 await context.bot.send_message(chat_id=update.effective_chat.id, text="Failed to post. Check logs/credentials. \u274C")
        else:
             await context.bot.send_message(chat_id=update.effective_chat.id, text="No tweet to send. If A/B testing, select A or B first.")
        return ConversationHandler.END
    else:
        # User wants to update the tweet
        context.user_data['tweet'] = user_input
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Updated draft:\n\n{user_input}\n\nReply with 'send' to post, attach photos, or type a new version.")
        return REVIEW

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Operation cancelled.")
    return ConversationHandler.END

async def automate_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = automation_service.get_status()
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text=f"🤖 **Away Mode Configuration**\n\nCurrent Status:\n{status}\n\n"
             "📆 **Select Start Date:**",
        reply_markup=create_calendar() # Show calendar for Start Date
    )
    context.user_data['cal_step'] = 'START' # Track which date we are picking
    return AUTO_DATES

async def handle_calendar_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Process selection
    selected_date, is_selected = process_calendar_selection(update, context)
    
    if is_selected:
        step = context.user_data.get('cal_step')
        
        if step == 'START':
            context.user_data['auto_start'] = selected_date
            context.user_data['cal_step'] = 'END'
            
            # Show next calendar
            await context.bot.send_message(
                chat_id=update.effective_chat.id, 
                text=f"✅ Start Date: {selected_date}\n\n📆 **Select End Date:**",
                reply_markup=create_calendar()
            )
            return AUTO_DATES
            
        elif step == 'END':
            context.user_data['auto_end'] = selected_date
            
            # Dates Done, move to Count
            await context.bot.send_message(
                chat_id=update.effective_chat.id, 
                text=f"✅ Dates set: {context.user_data['auto_start']} to {selected_date}.\n\nHow many tweets per day? (Enter a number, e.g., 2)"
            )
            return AUTO_COUNT
            
    return AUTO_DATES

async def check_terminate_auto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Special terminate check for automation flow that might need to return END."""
    # Logic similar to check_terminate but might need handled differently if we want to reset entire state
    return await check_terminate(update, context)

async def auto_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text input during AUTO dates (for terminate) and AUTO count."""
    if await check_terminate(update, context):
        return ConversationHandler.END # End the auto convo, but since we cleared data, user can /start
        
    # If we are in AUTO_COUNT state specifically
    # But since we need to distinguish, we might need separate handlers.
    # Actually, we can just look at state if we were inside the handler... but standard handlers are separate.
    return AUTO_DATES 

async def auto_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_terminate(update, context):
        return ConversationHandler.END

    text = update.message.text.strip()
    if text.isdigit():
        context.user_data['auto_count'] = int(text)
        
        # Predefined themes
        themes = ["AI News", "Python Tips", "Tech Humor", "Coding Life", "Motivation", "Startup Advice", "Deep Learning"]
        context.user_data['available_themes'] = themes
        context.user_data['selected_themes'] = []
        
        await show_theme_selection(update, context)
        return AUTO_THEMES
    
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Please enter a valid number.")
        return AUTO_COUNT

async def show_theme_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    themes = context.user_data.get('available_themes', [])
    selected = context.user_data.get('selected_themes', [])
    
    keyboard = []
    row = []
    for theme in themes:
        is_selected = theme in selected
        label = f"{'✅ ' if is_selected else ''}{theme}"
        row.append(InlineKeyboardButton(label, callback_data=f"{THEME_PREFIX}{theme}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("Done ✅", callback_data=DONE_ACTION)])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "Select themes (pick at least 1):"
    if selected:
        text += f"\n\nSelected: {', '.join(selected)}"
        
    if update.callback_query:
        await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup)

async def handle_theme_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == DONE_ACTION:
        selected = context.user_data.get('selected_themes', [])
        if not selected:
            await query.answer("Please select at least one theme!", show_alert=True)
            return AUTO_THEMES
        
        # Start Automation
        automation_service.start_automation(
            context.user_data['auto_start'],
            context.user_data['auto_end'],
            context.user_data['auto_count'],
            selected
        )
        await query.edit_message_text(text=f"✅ Automation Confirmed!\nThemes: {', '.join(selected)}")
        return ConversationHandler.END
        
    elif data.startswith(THEME_PREFIX):
        theme = data[len(THEME_PREFIX):]
        selected = context.user_data.get('selected_themes', [])
        
        if theme in selected:
            selected.remove(theme)
        else:
            selected.append(theme)
            
        context.user_data['selected_themes'] = selected
        await show_theme_selection(update, context)
        return AUTO_THEMES

if __name__ == '__main__':
    if not config.TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found in .env")
        exit(1)

    application = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()

    # Define user filter
    user_filter = filters.ALL
    if config.ALLOWED_TELEGRAM_USER_ID:
        try:
            user_id = int(config.ALLOWED_TELEGRAM_USER_ID)
            user_filter = filters.User(user_id=user_id)
            print(f"Restricting access to user ID: {user_id}")
        except ValueError:
            print("Error: ALLOWED_TELEGRAM_USER_ID is not a valid integer. Allowed checks disabled.")

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start, filters=user_filter),
            # Allow starting directly with a topic text
            MessageHandler(filters.TEXT & (~filters.COMMAND) & user_filter, handle_topic)
        ],
        states={
            TOPIC: [MessageHandler(filters.TEXT & (~filters.COMMAND) & user_filter, handle_topic)],
            TONE: [
                CallbackQueryHandler(handle_tone),
                MessageHandler(filters.TEXT & (~filters.COMMAND) & user_filter, handle_tone_input)
            ],
            REVIEW: [MessageHandler((filters.TEXT | filters.PHOTO) & (~filters.COMMAND) & user_filter, handle_review)],
        },
        fallbacks=[CommandHandler('cancel', cancel, filters=user_filter)]
    )

    auto_handler = ConversationHandler(
        entry_points=[CommandHandler('away', automate_start, filters=user_filter)],
        states={
            AUTO_DATES: [
                CallbackQueryHandler(handle_calendar_date, pattern=f"^{CALENDAR_CALLBACK}"),
                MessageHandler(filters.TEXT & (~filters.COMMAND) & user_filter, auto_count) # Reuse auto_count check logic or need specific terminate
            ],
            AUTO_COUNT: [MessageHandler(filters.TEXT & (~filters.COMMAND) & user_filter, auto_count)],
            AUTO_THEMES: [CallbackQueryHandler(handle_theme_selection)],
        },
        fallbacks=[CommandHandler('cancel', cancel, filters=user_filter)]
    )


    application.add_handler(auto_handler)
    application.add_handler(conv_handler)


    # Run the bot
    webhook_url = os.getenv("WEBHOOK_URL")
    
    # Check for polling args (support typos like -pooling)
    is_polling = any(arg in sys.argv for arg in ["--polling", "-polling", "-p", "polling"])
    
    if webhook_url and not is_polling:
        port = int(os.getenv("PORT", "8443"))
        logging.info(f"Starting in WEBHOOK mode on port {port}...")
        
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=config.TELEGRAM_BOT_TOKEN,
            webhook_url=f"{webhook_url}/{config.TELEGRAM_BOT_TOKEN}"
        )
    else:
        logging.info("Starting in POLLING mode...")
        application.run_polling()
