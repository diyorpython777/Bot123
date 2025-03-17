from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
import logging
from config import ANIME_NAME, ANIME_DESCRIPTION, ANIME_CODE, ANIME_IMAGE, ANIME_VIDEO, ANIME_EPISODE_NUMBER, ANIME_EPISODE_URL
from database import (
    is_admin, load_data, generate_anime_id, add_anime_to_db, 
    delete_anime_from_db, add_episode_to_anime, load_users, 
    toggle_user_vip
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show admin panel."""
    query = update.callback_query
    
    if not is_admin(query.from_user.id):
        await query.edit_message_text("Sizda admin huquqlari yo'q!")
        return
    
    keyboard = [
        [InlineKeyboardButton("➕ Anime qo'shish", callback_data="add_anime")],
        [InlineKeyboardButton("🗑️ Anime o'chirish", callback_data="delete_anime")],
        [InlineKeyboardButton("🎬 Epizod qo'shish", callback_data="add_episode")],
        [InlineKeyboardButton("👑 VIP boshqarish", callback_data="manage_vip")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Admin panel:",
        reply_markup=reply_markup
    )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Command handler for /admin."""
    if is_admin(update.effective_user.id):
        keyboard = [
            [InlineKeyboardButton("⚙️ Admin panel", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Admin buyruqlari:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("Sizda admin huquqlari yo'q!")

async def start_add_anime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the process of adding a new anime."""
    query = update.callback_query
    
    await query.edit_message_text(
        "Yangi anime qo'shish.\n\nAnime nomini kiriting:",
        parse_mode=ParseMode.HTML
    )
    
    return ANIME_NAME

async def add_anime_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process anime name input."""
    context.user_data["anime_name"] = update.message.text.strip()
    
    await update.message.reply_text(
        "Anime tavsifini kiriting:",
        parse_mode=ParseMode.HTML
    )
    
    return ANIME_DESCRIPTION

async def add_anime_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process anime description input."""
    context.user_data["anime_description"] = update.message.text.strip()
    
    await update.message.reply_text(
        "Anime kodini kiriting (masalan: naruto, onepiece):",
        parse_mode=ParseMode.HTML
    )
    
    return ANIME_CODE

async def add_anime_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process anime code input."""
    context.user_data["anime_code"] = update.message.text.strip().lower()
    
    await update.message.reply_text(
        "Anime rasmini yuklang:",
        parse_mode=ParseMode.HTML
    )
    
    return ANIME_IMAGE

async def add_anime_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process anime image input."""
    # Check if message contains photo
    if update.message.photo:
        # Get the largest photo (best quality)
        photo = update.message.photo[-1]
        context.user_data["anime_image_id"] = photo.file_id
        
        await update.message.reply_text(
            "Anime videosini yuklang (yoki o'tkazib yuborish uchun '-' kiriting):",
            parse_mode=ParseMode.HTML
        )
        
        return ANIME_VIDEO
    else:
        await update.message.reply_text(
            "Iltimos, rasm yuklang:",
            parse_mode=ParseMode.HTML
        )
        return ANIME_IMAGE

async def add_anime_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process anime video input and save the anime."""
    # Check if message contains video or is skip command
    if update.message.video:
        context.user_data["anime_video_id"] = update.message.video.file_id
    elif update.message.text == "-":
        context.user_data["anime_video_id"] = ""
    else:
        await update.message.reply_text(
            "Iltimos, video yuklang yoki o'tkazib yuborish uchun '-' kiriting:",
            parse_mode=ParseMode.HTML
        )
        return ANIME_VIDEO
    
    # Generate a new anime ID
    anime_id = generate_anime_id()
    
    # Create new anime entry
    new_anime = {
        "id": anime_id,
        "name": context.user_data["anime_name"],
        "description": context.user_data["anime_description"],
        "code": context.user_data["anime_code"],
        "image_id": context.user_data["anime_image_id"],
        "video_id": context.user_data.get("anime_video_id", ""),
        "vip": False,
        "episodes": []
    }
    
    # Save to data
    add_anime_to_db(new_anime)
    
    # Clear user data
    context.user_data.clear()
    
    # Send confirmation
    keyboard = [
        [InlineKeyboardButton("➕ Epizod qo'shish", callback_data=f"add_episode_to_{anime_id}")],
        [InlineKeyboardButton("🔙 Admin panelga qaytish", callback_data="back_to_admin")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Anime muvaffaqiyatli qo'shildi!\nID: {anime_id}",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    
    return ConversationHandler.END

async def show_delete_anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of animes for deletion."""
    query = update.callback_query
    data = load_data()
    
    if not data["animes"]:
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Animelar ro'yxati bo'sh.",
            reply_markup=reply_markup
        )
        return
    
    keyboard = []
    for anime in data["animes"]:
        keyboard.append([InlineKeyboardButton(f"🗑️ {anime['name']} ({anime['id']})", callback_data=f"delete_confirm_{anime['id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "O'chirish uchun animeni tanlang:",
        reply_markup=reply_markup
    )

async def delete_anime(update: Update, context: ContextTypes.DEFAULT_TYPE, anime_id: str) -> None:
    """Delete an anime."""
    query = update.callback_query
    
    # Delete the anime
    delete_anime_from_db(anime_id)
    
    keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"Anime muvaffaqiyatli o'chirildi!",
        reply_markup=reply_markup
    )

async def show_add_episode_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of animes for adding episodes."""
    query = update.callback_query
    data = load_data()
    
    if not data["animes"]:
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Animelar ro'yxati bo'sh.",
            reply_markup=reply_markup
        )
        return
    
    keyboard = []
    for anime in data["animes"]:
        keyboard.append([InlineKeyboardButton(f"{anime['name']} ({anime['id']})", callback_data=f"add_episode_to_{anime['id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Epizod qo'shish uchun animeni tanlang:",
        reply_markup=reply_markup
    )

async def add_episode_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process episode number input."""
    # Agar user_data bo'sh bo'lsa, demak bu tugma orqali emas, to'g'ridan-to'g'ri xabar orqali kelgan
    if not context.user_data.get("current_anime_id"):
        return ConversationHandler.END
    
    try:
        episode_number = int(update.message.text.strip())
        if episode_number <= 0:
            raise ValueError("Episode number must be positive")
        
        context.user_data["episode_number"] = episode_number
        
        await update.message.reply_text(
            "Epizod videosini yuklang:",
            parse_mode=ParseMode.HTML
        )
        
        return ANIME_EPISODE_URL
    except ValueError:
        await update.message.reply_text(
            "Noto'g'ri raqam. Iltimos, musbat son kiriting:",
            parse_mode=ParseMode.HTML
        )
        return ANIME_EPISODE_NUMBER

async def add_episode_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process episode video input and save the episode."""
    # Agar user_data bo'sh bo'lsa, demak bu tugma orqali emas, to'g'ridan-to'g'ri xabar orqali kelgan
    if not context.user_data.get("current_anime_id") or not context.user_data.get("episode_number"):
        return ConversationHandler.END
    
    if not update.message.video:
        await update.message.reply_text(
            "Iltimos, video yuklang:",
            parse_mode=ParseMode.HTML
        )
        return ANIME_EPISODE_URL
    
    video_id = update.message.video.file_id
    anime_id = context.user_data["current_anime_id"]
    episode_number = context.user_data["episode_number"]
    
    # Add episode to anime
    add_episode_to_anime(anime_id, episode_number, video_id)
    
    # Clear user data
    context.user_data.clear()
    
    # Send confirmation
    keyboard = [
        [InlineKeyboardButton("🔙 Admin panelga qaytish", callback_data="back_to_admin")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Epizod muvaffaqiyatli qo'shildi!",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    
    return ConversationHandler.END

async def show_manage_vip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show VIP management panel."""
    query = update.callback_query
    users = load_users()
    
    if not users["users"]:
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Foydalanuvchilar ro'yxati bo'sh.",
            reply_markup=reply_markup
        )
        return
    
    keyboard = []
    for user in users["users"]:
        status = "✅ VIP" if user.get("vip", False) else "❌ Oddiy"
        name = user.get("first_name", "Foydalanuvchi")
        keyboard.append([InlineKeyboardButton(f"{name} - {status}", callback_data=f"toggle_vip_{user['id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "VIP statusini o'zgartirish uchun foydalanuvchini tanlang:",
        reply_markup=reply_markup
    )

async def toggle_vip_status(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """Toggle VIP status for a user."""
    query = update.callback_query
    
    # Toggle VIP status
    toggle_user_vip(user_id)
    
    # Show updated VIP management panel
    await show_manage_vip(update, context)