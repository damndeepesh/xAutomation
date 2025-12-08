import logging
import os
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
import config
from services.llm_service import LLMService
from services.x_service import XService

# Define states for ConversationHandler
TOPIC, TONE, REVIEW = range(3)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

llm_service = LLMService()
x_service = XService()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Hi! Send me a topic or thought, and I'll generate a tweet for you.")
    return TOPIC

async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        context.user_data['tweet'] = generated_tweet
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=f"Here is the draft ({tone}):\n\n{generated_tweet}\n\nReply with 'send' to post, attach photos, or type a new version to update."
        )
        return REVIEW

async def handle_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    user_input = update.message.text.strip()
    
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
        entry_points=[CommandHandler('start', start, filters=user_filter)],
        states={
            TOPIC: [MessageHandler(filters.TEXT & (~filters.COMMAND) & user_filter, handle_topic)],
            TONE: [CallbackQueryHandler(handle_tone)],
            REVIEW: [MessageHandler((filters.TEXT | filters.PHOTO) & (~filters.COMMAND) & user_filter, handle_review)],
        },
        fallbacks=[CommandHandler('cancel', cancel, filters=user_filter)]
    )

    application.add_handler(conv_handler)

    # Run the bot
    webhook_url = os.getenv("WEBHOOK_URL")
    
    if webhook_url:
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
