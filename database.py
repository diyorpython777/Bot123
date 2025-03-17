import json
import logging
from datetime import datetime
from config import DATA_FILE, USER_FILE, ADMIN_IDS, CHANNEL_ID
from telegram import Bot
from telegram.constants import ParseMode
import asyncio

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot instance for channel posting
bot = None

def set_bot(bot_instance):
    global bot
    bot = bot_instance

# Load data from files
def load_data():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"animes": []}

def load_users():
    try:
        with open(USER_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"users": []}

# Save data to files
def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def save_users(data):
    with open(USER_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Helper functions
def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_anime_by_id(anime_id):
    data = load_data()
    for anime in data["animes"]:
        if anime["id"] == anime_id:
            return anime
    return None

def get_anime_by_code(code):
    data = load_data()
    for anime in data["animes"]:
        if anime.get("code") == code:
            return anime
    return None

def get_user_by_id(user_id):
    users = load_users()
    for user in users["users"]:
        if user["id"] == user_id:
            return user
    return None

def is_vip(user_id):
    user = get_user_by_id(user_id)
    return user and user.get("vip", False)

def generate_anime_id():
    data = load_data()
    if not data["animes"]:
        return "ANM001"
    
    last_id = data["animes"][-1]["id"]
    num = int(last_id[3:]) + 1
    return f"ANM{num:03d}"

def register_user(user):
    users = load_users()
    if not any(u["id"] == user.id for u in users["users"]):
        users["users"].append({
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "joined_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "vip": False
        })
        save_users(users)
        return True
    return False

async def post_anime_to_channel(anime_data):
    """Post anime to channel with nice formatting and stickers."""
    if bot is None:
        logger.error("Bot is not initialized for channel posting")
        return False
    
    try:
        # Create a nicely formatted message with emojis
        caption = (
            f"🌟 <b>YANGI ANIME QO'SHILDI!</b> 🌟\n\n"
            f"📺 <b>{anime_data['name']}</b> ({anime_data['id']})\n\n"
            f"📝 <b>Tavsif:</b>\n{anime_data['description']}\n\n"
            f"🔍 <b>Kod:</b> {anime_data['code']}\n"
            f"📅 <b>Qo'shilgan sana:</b> {datetime.now().strftime('%Y-%m-%d')}\n\n"
            f"🤖 @{(await bot.get_me()).username} orqali ko'ring!"
        )
        
        # Send photo with caption
        if anime_data.get("image_id"):
            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=anime_data["image_id"],
                caption=caption,
                parse_mode=ParseMode.HTML
            )
            
            # If there's a video, send it as a follow-up
            if anime_data.get("video_id"):
                await bot.send_video(
                    chat_id=CHANNEL_ID,
                    video=anime_data["video_id"],
                    caption=f"🎬 <b>{anime_data['name']}</b> - Treyler",
                    parse_mode=ParseMode.HTML
                )
            
            return True
        else:
            # If no image, just send text
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=caption,
                parse_mode=ParseMode.HTML
            )
            return True
    except Exception as e:
        logger.error(f"Error posting to channel: {e}")
        return False

async def add_anime_to_db_async(anime_data):
    """Add anime to database and post to channel asynchronously."""
    data = load_data()
    data["animes"].append(anime_data)
    save_data(data)
    
    # Post to channel
    await post_anime_to_channel(anime_data)
    
    return anime_data["id"]

def add_anime_to_db(anime_data):
    """Add anime to database and post to channel."""
    data = load_data()
    data["animes"].append(anime_data)
    save_data(data)
    
    # Schedule the channel posting for later
    # We don't wait for it to complete here to avoid event loop issues
    asyncio.create_task(post_anime_to_channel(anime_data))
    
    return anime_data["id"]

def delete_anime_from_db(anime_id):
    data = load_data()
    for i, anime in enumerate(data["animes"]):
        if anime["id"] == anime_id:
            del data["animes"][i]
            save_data(data)
            return True
    return False

def add_episode_to_anime(anime_id, episode_number, episode_url):
    data = load_data()
    for anime in data["animes"]:
        if anime["id"] == anime_id:
            # Check if episode already exists
            for i, ep in enumerate(anime.get("episodes", [])):
                if ep["number"] == episode_number:
                    # Update existing episode
                    anime["episodes"][i]["url"] = episode_url
                    break
            else:
                # Add new episode
                if "episodes" not in anime:
                    anime["episodes"] = []
                
                anime["episodes"].append({
                    "number": episode_number,
                    "url": episode_url
                })
                
                # Sort episodes by number
                anime["episodes"].sort(key=lambda x: x["number"])
            
            save_data(data)
            
            # Schedule the channel posting for later
            # We don't wait for it to complete here to avoid event loop issues
            asyncio.create_task(post_episode_to_channel(anime, episode_number, episode_url))
            
            return True
    return False

async def post_episode_to_channel(anime, episode_number, episode_url):
    """Post episode to channel with nice formatting."""
    if bot is None:
        logger.error("Bot is not initialized for channel posting")
        return False
    
    try:
        # Create a nicely formatted message with emojis
        caption = (
            f"🎬 <b>YANGI EPIZOD!</b> 🎬\n\n"
            f"📺 <b>{anime['name']}</b> - {episode_number}-qism\n\n"
            f"📅 <b>Qo'shilgan sana:</b> {datetime.now().strftime('%Y-%m-%d')}\n\n"
            f"🤖 @{(await bot.get_me()).username} orqali ko'ring!"
        )
        
        # Send video with caption
        await bot.send_video(
            chat_id=CHANNEL_ID,
            video=episode_url,
            caption=caption,
            parse_mode=ParseMode.HTML
        )
        
        return True
    except Exception as e:
        logger.error(f"Error posting episode to channel: {e}")
        return False

def toggle_user_vip(user_id):
    users = load_users()
    for user in users["users"]:
        if user["id"] == user_id:
            user["vip"] = not user.get("vip", False)
            save_users(users)
            return user["vip"]
    return False

def search_anime(query):
    data = load_data()
    results = []
    query = query.strip().lower()
    
    # Search by ID, code or name
    for anime in data["animes"]:
        if (query == anime["id"].lower() or 
            query == anime.get("code", "").lower() or 
            query in anime["name"].lower()):
            results.append(anime)
    
    return results