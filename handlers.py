from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
import logging
from config import SEARCH_QUERY
from database import (
    load_data, get_anime_by_id, register_user, is_vip, search_anime
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    register_user(user)
    
    keyboard = [
        [InlineKeyboardButton("🔍 Anime qidirish", callback_data="search")],
        [InlineKeyboardButton("📋 Animelar ro'yxati", callback_data="anime_list")],
        [InlineKeyboardButton("👑 VIP", callback_data="vip_info")]
    ]
    
    from database import is_admin
    if is_admin(user.id):
        keyboard.append([InlineKeyboardButton("⚙️ Admin panel", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Assalomu alaykum, {user.first_name}! Anime ko'rish botiga xush kelibsiz!",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "Bot buyruqlari:\n"
        "/start - Botni ishga tushirish\n"
        "/search - Anime qidirish\n"
        "/list - Animelar ro'yxati\n"
        "/vip - VIP ma'lumotlari\n"
        "/help - Yordam"
    )

async def search_anime_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the search process."""
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "Qidirish uchun anime nomini yoki kodini kiriting:",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            "Qidirish uchun anime nomini yoki kodini kiriting:",
            parse_mode=ParseMode.HTML
        )
    
    return SEARCH_QUERY

# search_anime_query funksiyasini o'zgartirish
async def search_anime_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process search query."""
    query = update.message.text.strip()
    results = search_anime(query)
    
    if not results:
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Hech narsa topilmadi. Boshqa so'rov bilan urinib ko'ring.",
            reply_markup=reply_markup
        )
    else:
        keyboard = []
        for anime in results:
            keyboard.append([InlineKeyboardButton(f"{anime['name']} ({anime['id']})", callback_data=f"anime_{anime['id']}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"Qidiruv natijalari ({len(results)}):",
            reply_markup=reply_markup
        )
    
    return ConversationHandler.END

async def list_animes_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Command handler for /list."""
    await list_animes(update, context)

async def list_animes(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1) -> None:
    """Show list of animes."""
    data = load_data()
    
    if not data["animes"]:
        if update.callback_query:
            keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                "Animelar ro'yxati bo'sh.",
                reply_markup=reply_markup
            )
        else:
            keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "Animelar ro'yxati bo'sh.",
                reply_markup=reply_markup
            )
        return
    
    # Pagination
    items_per_page = 5
    total_pages = (len(data["animes"]) + items_per_page - 1) // items_per_page
    
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages
    
    start_idx = (page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, len(data["animes"]))
    
    keyboard = []
    for anime in data["animes"][start_idx:end_idx]:
        keyboard.append([InlineKeyboardButton(f"{anime['name']} ({anime['id']})", callback_data=f"anime_{anime['id']}")])
    
    # Pagination buttons
    pagination = []
    if page > 1:
        pagination.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"page_{page-1}"))
    if page < total_pages:
        pagination.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"page_{page+1}"))
    
    if pagination:
        keyboard.append(pagination)
    
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"Animelar ro'yxati ({start_idx+1}-{end_idx} / {len(data['animes'])}):"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            message,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            message,
            reply_markup=reply_markup
        )

async def show_anime_details(update: Update, context: ContextTypes.DEFAULT_TYPE, anime_id: str) -> None:
    """Show anime details."""
    query = update.callback_query
    anime = get_anime_by_id(anime_id)

    if not anime:
        await query.edit_message_text(
            "Anime topilmadi.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]])
        )
        return

    # Check if VIP
    is_user_vip = is_vip(query.from_user.id)

    # Create episode buttons
    keyboard = []
    episode_buttons = []
    
    if anime.get("episodes"):
        # Sort episodes by number
        sorted_episodes = sorted(anime["episodes"], key=lambda x: x["number"])
        
        # Create episode buttons in rows of 5
        for episode in sorted_episodes:
            # If anime is VIP, check user VIP status
            if anime.get("vip", False) and not is_user_vip:
                episode_buttons.append(InlineKeyboardButton(f"🔒 {episode['number']}", callback_data="vip_info"))
            else:
                episode_buttons.append(InlineKeyboardButton(f"{episode['number']}", callback_data=f"episode_{anime_id}_{episode['number']}"))
            
            # Create a new row after every 5 buttons
            if len(episode_buttons) == 5:
                keyboard.append(episode_buttons)
                episode_buttons = []
        
        # Add any remaining buttons
        if episode_buttons:
            keyboard.append(episode_buttons)
    
    # Add back button
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="anime_list")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send anime details with image
    vip_status = "Ha" if anime.get("vip", False) else "Yoq"

    if anime.get("image_id"):
        await query.message.reply_photo(
            photo=anime["image_id"],
            caption=(f"📺 <b>{anime['name']}</b> ({anime['id']})\n\n"
                   f"📝 <b>Tavsif:</b>\n{anime['description']}\n\n"
                   f"🔍 <b>Kod:</b> {anime.get('code', 'N/A')}\n"
                   f"👑 <b>VIP:</b> {vip_status}\n"
                   f"🎬 <b>Epizodlar soni:</b> {len(anime.get('episodes', []))}"),
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        await query.edit_message_text("Anime ma'lumotlari yuborildi.")
    else:
        await query.edit_message_text(
            (f"📺 <b>{anime['name']}</b> ({anime['id']})\n\n"
            f"📝 <b>Tavsif:</b>\n{anime['description']}\n\n"
            f"🔍 <b>Kod:</b> {anime.get('code', 'N/A')}\n"
            f"👑 <b>VIP:</b> {vip_status}\n"
            f"🎬 <b>Epizodlar soni:</b> {len(anime.get('episodes', []))}"),
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )

async def show_episode(update: Update, context: ContextTypes.DEFAULT_TYPE, anime_id: str, episode_num: int) -> None:
    """Show episode video."""
    query = update.callback_query
    anime = get_anime_by_id(anime_id)
    
    if not anime:
        await query.edit_message_text(
            "Anime topilmadi.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]])
        )
        return
    
    # Find episode
    episode = None
    for ep in anime.get("episodes", []):
        if ep["number"] == episode_num:
            episode = ep
            break
    
    if not episode:
        await query.edit_message_text(
            "Epizod topilmadi.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data=f"anime_{anime_id}")]])
        )
        return
    
    # Check if VIP
    if anime.get("vip", False) and not is_vip(query.from_user.id):
        await query.edit_message_text(
            "Bu anime faqat VIP foydalanuvchilar uchun.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 VIP haqida", callback_data="vip_info")],
                [InlineKeyboardButton("🔙 Orqaga", callback_data=f"anime_{anime_id}")]
            ])
        )
        return
    
    # Create navigation buttons
    keyboard = []
    
    # Previous episode button
    prev_episode = None
    for ep in anime.get("episodes", []):
        if ep["number"] < episode_num and (prev_episode is None or ep["number"] > prev_episode["number"]):
            prev_episode = ep
    
    if prev_episode:
        keyboard.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"episode_{anime_id}_{prev_episode['number']}"))
    
    # Next episode button
    next_episode = None
    for ep in anime.get("episodes", []):
        if ep["number"] > episode_num and (next_episode is None or ep["number"] < next_episode["number"]):
            next_episode = ep
    
    if next_episode:
        keyboard.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"episode_{anime_id}_{next_episode['number']}"))
    
    # Add navigation row if there are buttons
    nav_row = []
    if keyboard:
        nav_row = [keyboard]
    
    reply_markup = InlineKeyboardMarkup([
        *nav_row,
        [InlineKeyboardButton("🔙 Orqaga", callback_data=f"anime_{anime_id}")]
    ])
    
    # Send video
    await query.message.reply_video(
        video=episode["url"],
        caption=f"📺 <b>{anime['name']}</b> - {episode_num}-qism",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )
    
    await query.edit_message_text("Epizod yuborildi.")

async def vip_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show VIP information."""
    query = update.callback_query
    
    is_user_vip = is_vip(query.from_user.id)
    
    if is_user_vip:
        message = (
            "👑 <b>VIP STATUS</b> 👑\n\n"
            "Sizda VIP status mavjud!\n"
            "Barcha VIP kontentlardan foydalanishingiz mumkin."
        )
    else:
        message = (
            "👑 <b>VIP STATUS</b> 👑\n\n"
            "VIP status orqali maxsus animelarga kirish imkoniyatiga ega bo'lasiz.\n\n"
            "VIP olish uchun admin bilan bog'laning."
        )
    
    keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )

async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Command handler for /vip."""
    is_user_vip = is_vip(update.effective_user.id)
    
    if is_user_vip:
        message = (
            "👑 <b>VIP STATUS</b> 👑\n\n"
            "Sizda VIP status mavjud!\n"
            "Barcha VIP kontentlardan foydalanishingiz mumkin."
        )
    else:
        message = (
            "👑 <b>VIP STATUS</b> 👑\n\n"
            "VIP status orqali maxsus animelarga kirish imkoniyatiga ega bo'lasiz.\n\n"
            "VIP olish uchun admin bilan bog'laning."
        )
    
    keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        message,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel conversation."""
    await update.message.reply_text(
        "Amal bekor qilindi.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]])
    )
    
    # Clear user data
    context.user_data.clear()
    
    return ConversationHandler.END