from aiogram import types
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import *

# start.py
from aiogram import types
from config import BOT_ADMINS

async def start(message: types.Message):
    print("✅ /start komandası alındı.")
    
    # Kullanıcı ID'sini kontrol et
    user_id = message.from_user.id
    is_admin = user_id in BOT_ADMINS
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("👤 Müştəriyəm", "🛠 Usta/Təmizlikçi")  # İki düyməni yan-yana yerləşdir
    keyboard.row("ℹ️ Əmr bələdçisi")  # Ayrı sətirdə Əmr bələdçisi
    
    if is_admin:
        keyboard.add("👨‍💼 Admin")
        
    await message.answer("Xoş gəldiniz! Rolunuzu seçin:", reply_markup=keyboard)

def register_handlers(dp):
    dp.register_message_handler(start, commands=['start'])