import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode

# Import configuration
from config import (
    BOT_TOKEN, ANIME_NAME, ANIME_DESCRIPTION, ANIME_CODE, 
    ANIME_IMAGE, ANIME_VIDEO, ANIME_EPISODE_NUMBER, 
    ANIME_EPISODE_URL, SEARCH_QUERY
)

# Import handlers
from handlers import (
    start, help_command, search_anime_command, search_anime_query,
    list_animes, list_animes_command, show_anime_details, 
    show_episode, vip_info, vip_command, cancel_conversation
)

# Import admin functions
from admin import (
    admin_panel, admin_command, start_add_anime, add_anime_name,
    add_anime_description, add_anime_code, add_anime_image, 
    add_anime_video, show_delete_anime_list, delete_anime,
    show_add_episode_list, add_episode_number, add_episode_url,
    show_manage_vip, toggle_vip_status
)

# Import database functions
from database import is_admin

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button clicks."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "search":
        await search_anime_command(update, context)
    elif query.data == "anime_list":
        await list_animes(update, context)
    elif query.data == "vip_info":
        await vip_info(update, context)
    elif query.data == "admin_panel":
        if is_admin(query.from_user.id):
            await admin_panel(update, context)
        else:
            await query.edit_message_text("Sizda admin huquqlari yo'q!")
    elif query.data.startswith("anime_"):
        anime_id = query.data.split("_")[1]
        await show_anime_details(update, context, anime_id)
    elif query.data.startswith("episode_"):
        parts = query.data.split("_")
        anime_id = parts[1]
        episode_num = int(parts[2])
        await show_episode(update, context, anime_id, episode_num)
    elif query.data == "add_anime":
        if is_admin(query.from_user.id):
            return await start_add_anime(update, context)
    elif query.data == "delete_anime":
        if is_admin(query.from_user.id):
            await show_delete_anime_list(update, context)
    elif query.data.startswith("delete_confirm_"):
        if is_admin(query.from_user.id):
            anime_id = query.data.split("_")[2]
            await delete_anime(update, context, anime_id)
    elif query.data == "add_episode":
        if is_admin(query.from_user.id):
            await show_add_episode_list(update, context)
    elif query.data.startswith("add_episode_to_"):
        if is_admin(query.from_user.id):
            anime_id = query.data.split("_")[3]
            context.user_data["current_anime_id"] = anime_id
            await query.edit_message_text(
                "Yangi epizod raqamini kiriting:",
                parse_mode=ParseMode.HTML
            )
            return ANIME_EPISODE_NUMBER
    elif query.data == "manage_vip":
        if is_admin(query.from_user.id):
            await show_manage_vip(update, context)
    elif query.data.startswith("toggle_vip_"):
        if is_admin(query.from_user.id):
            user_id = int(query.data.split("_")[2])
            await toggle_vip_status(update, context, user_id)
    elif query.data == "back_to_main":
        keyboard = [
            [InlineKeyboardButton("🔍 Anime qidirish", callback_data="search")],
            [InlineKeyboardButton("📋 Animelar ro'yxati", callback_data="anime_list")],
            [InlineKeyboardButton("👑 VIP", callback_data="vip_info")]
        ]
        
        if is_admin(query.from_user.id):
            keyboard.append([InlineKeyboardButton("⚙️ Admin panel", callback_data="admin_panel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"Assalomu alaykum, {query.from_user.first_name}! Anime ko'rish botiga xush kelibsiz!",
            reply_markup=reply_markup
        )
    elif query.data == "back_to_admin":
        await admin_panel(update, context)
    elif query.data.startswith("page_"):
        page = int(query.data.split("_")[1])
        await list_animes(update, context, page)

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Set bot instance for database module
    from database import set_bot
    set_bot(application.bot)
    
    # Add conversation handlers
    add_anime_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_anime, pattern="^add_anime$")],
        states={
            ANIME_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_anime_name)],
            ANIME_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_anime_description)],
            ANIME_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_anime_code)],
            ANIME_IMAGE: [MessageHandler(filters.PHOTO | filters.TEXT, add_anime_image)],
            ANIME_VIDEO: [MessageHandler(filters.VIDEO | filters.TEXT, add_anime_video)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        per_message=False
    )
    
    # Add search conversation handler
    search_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(search_anime_command, pattern="^search$"),
            CommandHandler("search", search_anime_command)
        ],
        states={
            SEARCH_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_anime_query)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        per_message=False
    )
    
    # Epizod qo'shish uchun handler
    episode_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, add_episode_number)
    application.add_handler(episode_handler, group=1)
    
    # Video qo'shish uchun handler
    video_handler = MessageHandler(filters.VIDEO, add_episode_url)
    application.add_handler(video_handler, group=2)
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("list", list_animes_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("vip", vip_command))
    
    # Add conversation handlers
    application.add_handler(add_anime_conv_handler)
    application.add_handler(search_conv_handler)
    
    # Add callback query handler for button clicks
    application.add_handler(CallbackQueryHandler(button_click))
    
    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main()