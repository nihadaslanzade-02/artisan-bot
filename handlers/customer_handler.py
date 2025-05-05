# customer_handler.py

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from dispatcher import bot, dp
from db import *
from datetime_helpers import (
    get_date_keyboard, get_time_slots_keyboard, format_datetime
)
from geo_helpers import format_distance, get_location_name
import logging
import datetime
import re
import asyncio
from config import *
import random

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define states for customer registration
class CustomerRegistrationStates(StatesGroup):
    confirming_name = State()
    entering_name = State()
    entering_phone = State()
    entering_city = State()
    confirming_registration = State()

# Define states for the customer order flow
class OrderStates(StatesGroup):
    selecting_service = State()
    selecting_subservice = State()
    sharing_location = State()
    selecting_date = State()
    selecting_time = State()
    entering_note = State()
    confirming_order = State()

# Define states for viewing nearby artisans
class NearbyArtisanStates(StatesGroup):
    sharing_location = State()
    viewing_artisans = State()
    filtering_by_service = State()

# Define states for profile management
class ProfileManagementStates(StatesGroup):
    viewing_profile = State()
    updating_name = State()
    updating_phone = State()
    updating_city = State()

class OrderRatingState(StatesGroup):
    waiting_for_comment = State()


async def show_command_guide(message: types.Message):
    """Display command guide information"""
    try:
        # Bələdçi mətnini hazırlayırıq
        guide_text = (
            "🔍 *Əmr Bələdçisi*\n\n"
            "*Əsas Əmrlər:*\n"
            "/start - Botu başlatmaq və yenidən rol seçmək\n"
            "/help - Kömək məlumatlarını göstərmək\n\n"
            
            "*Müştərilər üçün Əmrlər:*\n"
            "✅ Yeni sifariş ver - Yeni sifariş yaratmaq\n"
            "📜 Əvvəlki sifarişlərə bax - Keçmiş sifarişləri göstərmək\n"
            "🌍 Yaxınlıqdakı ustaları göstər - Məkana görə ustalar axtarmaq\n"
            "👤 Profilim - Profil məlumatlarını göstərmək və redaktə etmək\n"
            "🔍 Xidmətlər - Mövcud xidmət növlərini göstərmək\n\n"
            
            "*Ustalar üçün Əmrlər:*\n"
            "📋 Aktiv sifarişlər - Gözləyən sifarişləri göstərmək\n"
            "⭐ Rəylər - Müştəri rəylərini göstərmək\n"
            "💰 Qiymət ayarları - Xidmət qiymətlərini tənzimləmək\n"
            "👤 Profil ayarları - Profil məlumatlarını göstərmək və redaktə etmək\n\n"
            
            "*Bot haqqında:*\n"
            "Bu bot müştərilərə usta sifarişi verməyə və ustalara müştəri tapmağa kömək edir. "
            "Sifarişlər, ödənişlər və rəylər sistem tərəfindən idarə olunur.\n\n"
            "*Burada istifadəçilər üçün təlimat videosunun linki yerləşdiriləcək.*"
        )
        
        # Əsas menyuya qayıtmaq düyməsini əlavə edirik
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add("🔄 Rol seçiminə qayıt")
        
        await message.answer(guide_text, reply_markup=keyboard, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error in show_command_guide: {e}")
        await message.answer(
            "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
        )

# Register customer handlers
def register_handlers(dp):
    # Handler for when user selects "Customer" role
    @dp.message_handler(lambda message: message.text == "👤 Müştəriyəm")
    async def handle_customer(message: types.Message, state: FSMContext):
        """Handle when user selects the customer role"""
        try:
            # Check if the customer is already registered
            telegram_id = message.from_user.id
            customer = get_customer_by_telegram_id(telegram_id)
            
            if customer:
                # Check if customer is blocked
                is_blocked, reason, amount, block_until = get_customer_blocked_status(customer['id'])
                
                if is_blocked:
                    # Show blocked message with payment instructions
                    block_text = (
                        f"⛔ *Hesabınız bloklanıb*\n\n"
                        f"Səbəb: {reason}\n\n"
                        f"Bloku açmaq üçün {amount} AZN ödəniş etməlisiniz.\n"
                        f"Ödəniş etmək üçün:"
                    )

                    kb = InlineKeyboardMarkup().add(
                        InlineKeyboardButton(
                            text = "Cəriməni ödə",
                            callback_data="pay_customer_fine"
                        )
                    )
                    await message.answer(block_text, reply_markup=kb, parse_mode="Markdown")
                    return   
           
                await show_customer_menu(message)
            else:
                # Clear any existing state first
                current_state = await state.get_state()
                if current_state:
                    await state.finish()

                await show_customer_agreement(message, state)
                
        except Exception as e:
            logger.error(f"Error in handle_customer: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_role_selection(message)
    
    async def show_customer_agreement(message: types.Message, state: FSMContext):
        """Show agreement for new customers"""
        try:
            # First show guide
            guide_text = (
                "*Burada istifadəçilər üçün təlimat videosunun linki yerləşdiriləcək.*\n"
            )
            
            await message.answer(guide_text, parse_mode="Markdown")
            
            # Then show agreement
            agreement_text = (
                "📜 *Müştəri Müqaviləsi*\n\n"
                "📌 Qeyd: Bu botdan istifadə etməklə aşağıdakı şərtləri qəbul etmiş olursunuz:\n\n"
                "1. Sifariş və Ödəniş:\n"
                "• Sifariş zamanı xidmət yeri, növü və vaxtı düzgün qeyd edilməlidir.\n"
                "• Ustanın təyin etdiyi qiyməti qəbul etdikdən sonra, ödənişi nağd və ya kartla etməlisiniz\n"
                "2. Usta ilə Davranış və Vaxt Uyğunluğu:\n"
                "• Usta sifarişi qəbul etdikdən sonra təyin olunan vaxtda evdə olmağınız gözlənilir.\n"
                "• Əxlaqa uyğun olmayan davranış və ya saxta sifariş verilməsi halında hesabınız bloklana bilər.\n"
                "3. Qiymət Rədd Etmə Hüququ:\n"
                "• Əgər usta yüksək qiymət təklif edərsə, sifarişi ləğv edə bilərsiniz.\n"
                "4. Reytinq və Geri Bildirim:\n"
                "• Sifariş tamamlandıqdan sonra ustaya ulduz və rəy vermək imkanınız var.\n"
                "• Bu məlumatlar ustaların reytinqinə təsir edir.\n"
                "5. Zərərçəkmiş Hallar:\n"
                "• Əgər usta gəlməzsə, sizə 10 AZN endirim kuponu təqdim olunur və bu növbəti sifarişdə istifadə edilə bilər.\n\n"
                "Bu şərtləri qəbul edib davam etmək istəyirsinizsə,  - ✅ Qəbul edirəm - düyməsini klikləyin."
            )
            
            # Create agreement buttons
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("✅ Qəbul edirəm", callback_data="accept_customer_agreement"),
                InlineKeyboardButton("❌ Qəbul etmirəm", callback_data="decline_customer_agreement")
            )
            
            await message.answer(agreement_text, reply_markup=keyboard, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Error in show_customer_agreement: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await show_role_selection(message)

    async def show_customer_guide_and_agreement(message: types.Message):
        """Show guide and agreement for customers"""
        # First show guide
        guide_text = (
            " *Burada istifadəçilər üçün təlimat videosunun linki yerləşdiriləcək.*\n "
        )
        
        await message.answer(guide_text, parse_mode="Markdown")
        
        # Then show agreement
        agreement_text = (
                "📜 *Usta Razılaşması*\n\n"
                "📌 Qeyd: Bu botdan istifadə etməklə aşağıdakı şərtləri qəbul etmiş olursunuz:\n\n"
                "1. Sifariş və Ödəniş:\n"
                "• Sifariş zamanı xidmət yeri, növü və vaxtı düzgün qeyd edilməlidir.\n"
                "• Ustanın təyin etdiyi qiyməti qəbul etdikdən sonra, ödənişi nağd və ya kartla etməlisiniz\n"
                "2. Usta ilə Davranış və Vaxt Uyğunluğu:\n"
                "• Usta sifarişi qəbul etdikdən sonra təyin olunan vaxtda evdə olmağınız gözlənilir.\n"
                "• Əxlaqa uyğun olmayan davranış və ya saxta sifariş verilməsi halında hesabınız bloklana bilər.\n"
                "3. Qiymət Rədd Etmə Hüququ:\n"
                "• Əgər usta yüksək qiymət təklif edərsə, sifarişi ləğv edə bilərsiniz.\n"
                "4. Reytinq və Geri Bildirim:\n"
                "• Sifariş tamamlandıqdan sonra ustaya ulduz və rəy vermək imkanınız var.\n"
                "• Bu məlumatlar ustaların reytinqinə təsir edir.\n"
                "5. Zərərçəkmiş Hallar:\n"
                "• Əgər usta gəlməzsə, sizə 10 AZN endirim kuponu təqdim olunur və bu növbəti sifarişdə istifadə edilə bilər.\n\n"
                "Bu şərtləri qəbul edib davam etmək istəyirsinizsə,  - ✅ Qəbul edirəm - düyməsini klikləyin."
        )
        
        # Create agreement buttons
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("✅ Qəbul edirəm", callback_data="accept_customer_agreement"),
            InlineKeyboardButton("❌ Qəbul etmirəm", callback_data="decline_customer_agreement")
        )
        
        await message.answer(agreement_text, reply_markup=keyboard, parse_mode="Markdown")


    # Müştəri müqaviləsi qəbul edilmə prosesini düzəltmə
    @dp.callback_query_handler(lambda c: c.data == "accept_customer_agreement")
    async def accept_customer_agreement(callback_query: types.CallbackQuery, state: FSMContext):
        """Handle customer agreement acceptance"""
        try:
            await callback_query.message.answer(
                "✅ Təşəkkür edirik! Şərtləri qəbul etdiniz."
            )
            
            # Qəbul etdikdən sonra qeydiyyata başlamaq üçün düymə göstər
            await start_customer_registration(callback_query.message, state)
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in accept_customer_agreement: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()


    @dp.callback_query_handler(lambda c: c.data == "decline_customer_agreement")
    async def decline_customer_agreement(callback_query: types.CallbackQuery, state: FSMContext):
        """Handle customer agreement decline"""
        try:
            # Clear any state
            await state.finish()
            
            # Return to role selection
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.row("👤 Müştəriyəm", "👷 Ustayam")
            keyboard.row("ℹ️ Əmr bələdçisi")
            
            if callback_query.from_user.id in BOT_ADMINS:
                keyboard.add("👨‍💼 Admin")
            
            await callback_query.message.answer(
                "❌ Şərtləri qəbul etmədiniz. Xidmətlərimizdən istifadə etmək üçün şərtləri qəbul etməlisiniz.",
                reply_markup=keyboard
            )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in decline_customer_agreement: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()

    async def start_customer_registration(message: types.Message, state: FSMContext):
        """Start the customer registration process"""
        try:
            await message.answer(
                "👋 Xoş gəlmisiniz! Müştəri qeydiyyatı üçün zəhmət olmasa, məlumatlarınızı təqdim edin."
            )
            
            # Pre-fill name from Telegram profile with extra checks
            # Generate a user-specific name using their Telegram profile
            user_id = message.chat.id

            # Try to get the user's real name first
            if message.chat.first_name:
                if message.chat.last_name:
                    full_name = f"{message.chat.first_name} {message.chat.last_name}"
                else:
                    full_name = message.from_user.first_name
            # Then try username if no real name is available
            elif message.chat.username and len(message.chat.username.strip()) > 0:
                full_name = message.chat.username
            # Finally, generate a random name as last resort
            else:
                try:
                    import random
                    random.seed(user_id)  # Use user ID as seed
                    unique_number = random.randint(10000, 99999)
                    full_name = f"İstifadəçi{unique_number}"
                except Exception as e:
                    # Fallback if random fails
                    full_name = f"İstifadəçi{user_id % 100000}"
            
            # Log the name being used
            # Add this near the name generation code
            logger.info(f"User data - ID: {message.chat.id}, username: {message.chat.username}, first_name: {message.chat.first_name}, last_name: {message.chat.last_name}")
            logger.info(f"Generated name for registration: {full_name}")
        
            
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                InlineKeyboardButton("✅ Bəli, adımı təsdiqləyirəm", callback_data="confirm_name"),
                InlineKeyboardButton("🖊 Xeyr, başqa ad daxil etmək istəyirəm", callback_data="change_name")
            )
            
            await message.answer(
                f"👤 Telegram hesabınızda göstərilən adınız: *{full_name}*\n\n"
                "Bu addan istifadə etmək istəyirsiniz?",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            async with state.proxy() as data:
                data['suggested_name'] = full_name
            
            await CustomerRegistrationStates.confirming_name.set()
            
        except Exception as e:
            logger.error(f"Error in start_customer_registration: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_role_selection(message)
    
    @dp.callback_query_handler(
        lambda c: c.data in ["confirm_name", "change_name"],
        state=CustomerRegistrationStates.confirming_name
    )
    async def process_name_confirmation(callback_query: types.CallbackQuery, state: FSMContext):
        """Process name confirmation response"""
        try:
            if callback_query.data == "confirm_name":
                # User confirmed the suggested name
                data = await state.get_data()
                suggested_name = data.get('suggested_name')
                
                async with state.proxy() as data:
                    data['name'] = suggested_name
                
                # Move to phone number collection
                await callback_query.message.answer(
                    "📞 Zəhmət olmasa, əlaqə nömrənizi daxil edin (məsələn: +994501234567):"
                )
                await CustomerRegistrationStates.entering_phone.set()
            else:
                # User wants to enter a different name
                await callback_query.message.answer(
                    "👤 Zəhmət olmasa, adınızı daxil edin:"
                )
                await CustomerRegistrationStates.entering_name.set()
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in process_name_confirmation: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_role_selection(callback_query.message)
    
    @dp.message_handler(state=CustomerRegistrationStates.entering_name)
    async def process_name_input(message: types.Message, state: FSMContext):
        """Process customer name input"""
        try:
            # Validate and store name
            name = message.text.strip()
            
            if len(name) < 2 or len(name) > 50:
                await message.answer(
                    "❌ Ad ən azı 2, ən çoxu 50 simvol olmalıdır. Zəhmət olmasa, yenidən daxil edin:"
                )
                return
            
            async with state.proxy() as data:
                data['name'] = name
            
            # Move to phone number collection
            await message.answer(
                "📞 Zəhmət olmasa, əlaqə nömrənizi daxil edin (məsələn: +994501234567):"
            )
            await CustomerRegistrationStates.entering_phone.set()
            
        except Exception as e:
            logger.error(f"Error in process_name_input: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_role_selection(message)
    
    @dp.message_handler(state=CustomerRegistrationStates.entering_phone)
    async def process_phone_input(message: types.Message, state: FSMContext):
        """Process customer phone input"""
        try:
            # Get and validate phone number
            phone = message.text.strip()
            
            # Simple regex for Azerbaijani phone numbers
            phone_regex = r'^\+?994\d{9}$|^0\d{9}$'
            
            if not re.match(phone_regex, phone):
                await message.answer(
                    "❌ Düzgün telefon nömrəsi daxil edin (məsələn: +994501234567 və ya 0501234567):"
                )
                return
            
            # Normalize phone format
            if phone.startswith("0"):
                phone = "+994" + phone[1:]
            elif not phone.startswith("+"):
                phone = "+" + phone
            
            async with state.proxy() as data:
                data['phone'] = phone
            
            # Move to city collection
            await message.answer(
                "🏙 Zəhmət olmasa, şəhərinizi daxil edin (məsələn: Bakı):"
            )
            await CustomerRegistrationStates.entering_city.set()
            
        except Exception as e:
            logger.error(f"Error in process_phone_input: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_role_selection(message)
    
    @dp.message_handler(state=CustomerRegistrationStates.entering_city)
    async def process_city_input(message: types.Message, state: FSMContext):
        """Process customer city input"""
        try:
            # Validate and store city
            city = message.text.strip()
            
            if len(city) < 2 or len(city) > 50:
                await message.answer(
                    "❌ Şəhər adı ən azı 2, ən çoxu 50 simvol olmalıdır. Zəhmət olmasa, yenidən daxil edin:"
                )
                return
            
            async with state.proxy() as data:
                data['city'] = city
                
                # Create summary for confirmation
                name = data['name']
                phone = data['phone']
                
                confirmation_text = (
                    "📋 *Qeydiyyat məlumatları:*\n\n"
                    f"👤 *Ad:* {name}\n"
                    f"📞 *Telefon:* {phone}\n"
                    f"🏙 *Şəhər:* {city}\n\n"
                    f"Bu məlumatları təsdiqləyirsiniz?"
                )
            
            # Create confirmation keyboard
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("✅ Təsdiqlə", callback_data="confirm_customer_registration"),
                InlineKeyboardButton("❌ Ləğv et", callback_data="cancel_customer_registration")
            )
            
            await message.answer(
                confirmation_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            await CustomerRegistrationStates.confirming_registration.set()
            
        except Exception as e:
            logger.error(f"Error in process_city_input: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_role_selection(message)
    
    @dp.callback_query_handler(
        lambda c: c.data == "confirm_customer_registration",
        state=CustomerRegistrationStates.confirming_registration
    )
    async def confirm_customer_registration(callback_query: types.CallbackQuery, state: FSMContext):
        """Confirm customer registration"""
        try:
            # Get all registration data from state
            data = await state.get_data()
            name = data['name']
            phone = data['phone']
            city = data['city']
            
            # Register customer in database
            telegram_id = callback_query.from_user.id
            customer_id = get_or_create_customer(
                telegram_id=telegram_id,
                name=name,
                phone=phone,
                city=city
            )
            
            if customer_id:
                await callback_query.message.answer(
                    "✅ Qeydiyyatınız uğurla tamamlandı!\n"
                    "İndi siz müştəri olaraq xidmətlərimizdən istifadə edə bilərsiniz.",
                    reply_markup=types.ReplyKeyboardRemove()
                )
                
                # Show main customer menu
                await show_customer_menu(callback_query.message)
            else:
                await callback_query.message.answer(
                    "❌ Qeydiyyat zamanı xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
                await show_role_selection(callback_query.message)
            
            await callback_query.answer()
            await state.finish()
            
        except Exception as e:
            logger.error(f"Error in confirm_customer_registration: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_role_selection(callback_query.message)
    
    @dp.callback_query_handler(
        lambda c: c.data == "cancel_customer_registration",
        state=CustomerRegistrationStates.confirming_registration
    )
    async def cancel_customer_registration(callback_query: types.CallbackQuery, state: FSMContext):
        """Cancel customer registration"""
        try:
            await callback_query.message.answer(
                "❌ Qeydiyyat ləğv edildi.",
                reply_markup=types.ReplyKeyboardRemove()
            )
            
            # Return to role selection
            await show_role_selection(callback_query.message)
            
            await callback_query.answer()
            await state.finish()
            
        except Exception as e:
            logger.error(f"Error in cancel_customer_registration: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_role_selection(callback_query.message)
    
    async def show_customer_menu(message: types.Message):
        """Show the main customer menu"""
        try:
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(KeyboardButton("✅ Yeni sifariş ver"))
            keyboard.add(KeyboardButton("📜 Əvvəlki sifarişlərə bax"))
            keyboard.add(KeyboardButton("🌍 Yaxınlıqdakı ustaları göstər"))
            keyboard.add(KeyboardButton("👤 Profilim"), KeyboardButton("🔍 Xidmətlər"))
            keyboard.add(KeyboardButton("ℹ️ Əmr bələdçisi"))
            keyboard.add(KeyboardButton("🏠 Əsas menyuya qayıt"))
            
            await message.answer(
                "👤 *Müştəri menyusu*\n\n"
                "Aşağıdakı əməliyyatlardan birini seçin:",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Error in show_customer_menu: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await show_role_selection(message)
    
    async def show_role_selection(message: types.Message):
        """Show role selection menu"""
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(KeyboardButton("👤 Müştəriyəm"), KeyboardButton("🛠 Ustayam"))
        
        await message.answer(
            "Xoş gəldiniz! Zəhmət olmasa, rolunuzu seçin:",
            reply_markup=keyboard
        )
    
    # Handler for "New order" button
    @dp.message_handler(lambda message: message.text == "✅ Yeni sifariş ver")
    async def start_new_order(message: types.Message, state: FSMContext):
        """Start the new order process"""
        try:
            # Make sure customer is registered
            telegram_id = message.from_user.id
            customer = get_customer_by_telegram_id(telegram_id)
            
            if not customer or not customer.get('phone'):
                await message.answer(
                    "❌ Sifariş vermək üçün əvvəlcə qeydiyyatdan keçməlisiniz."
                )
                await start_customer_registration(message, state)
                return
            
            # Check if customer is blocked
            is_blocked, reason, amount, block_until = get_customer_blocked_status(customer['id'])
            if is_blocked:
                # Show blocked message with payment instructions
                block_text = (
                    f"⛔ *Hesabınız bloklanıb*\n\n"
                    f"Səbəb: {reason}\n\n"
                    f"Bloku açmaq üçün {amount} AZN ödəniş etməlisiniz.\n"
                    f"Ödəniş etmək üçün:"
                )
                
                kb = InlineKeyboardMarkup().add(
                        InlineKeyboardButton(
                            text = "Cəriməni ödə",
                            callback_data="pay_customer_fine"
                        )
                    )
                await message.answer(block_text, reply_markup=kb, parse_mode="Markdown")
                return
            # Get available services from the database
            services = get_services()
            
            # Create inline keyboard with service buttons
            keyboard = InlineKeyboardMarkup(row_width=2)
            
            for service in services:
                keyboard.add(InlineKeyboardButton(service, callback_data=f"service_{service}"))
            
            keyboard.add(InlineKeyboardButton("🔙 Geri", callback_data="back_to_menu"))
            
            await message.answer(
                "🛠 *Yeni sifariş*\n\n"
                "Xahiş edirəm, ehtiyacınız olan xidmət növünü seçin:",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            await OrderStates.selecting_service.set()
            
        except Exception as e:
            logger.error(f"Error in start_new_order: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
    
    # Handler for service selection via inline button
    @dp.callback_query_handler(lambda c: c.data.startswith('service_'), state=OrderStates.selecting_service)
    async def process_service_selection(callback_query: types.CallbackQuery, state: FSMContext):
        """Process the service selection"""
        try:
            # Extract service name from callback data
            selected_service = callback_query.data.split('_', 1)[1]
            
            # Store the selected service in state
            async with state.proxy() as data:
                data['service'] = selected_service
            

            # Get subservices for this service
            subservices = get_subservices(selected_service)
            
            if subservices:
                # Create keyboard with subservice options
                keyboard = InlineKeyboardMarkup(row_width=1)
                
                for subservice in subservices:
                    keyboard.add(
                        InlineKeyboardButton(
                            subservice, 
                            callback_data=f"subservice_{subservice}"
                        )
                    )
                
                keyboard.add(InlineKeyboardButton("🔙 Geri", callback_data="back_to_services"))
                
                await callback_query.message.answer(
                    f"Seçdiyiniz xidmət: *{selected_service}*\n\n"
                    f"İndi daha dəqiq xidmət növünü seçin:",
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
                
                await OrderStates.selecting_subservice.set()
            else:
                # If no subservices (unlikely), proceed directly to location
                keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
                keyboard.add(KeyboardButton("📍 Yerimi paylaş", request_location=True))
                keyboard.add(KeyboardButton("🔙 Geri"))
                
                await callback_query.message.answer(
                    f"Seçdiyiniz xidmət: *{selected_service}*\n\n"
                    f"📍 İndi zəhmət olmasa, yerləşdiyiniz məkanı paylaşın ki, ən yaxın ustaları tapaq:",
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
                
                await OrderStates.sharing_location.set()
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in process_service_selection: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_customer_menu(callback_query.message)
    
    @dp.callback_query_handler(lambda c: c.data == "back_to_services", state=OrderStates.selecting_subservice)
    async def back_to_services(callback_query: types.CallbackQuery, state: FSMContext):
        """Go back to service selection"""
        try:
            # Get available services from the database
            services = get_services()
            
            # Create inline keyboard with service buttons
            keyboard = InlineKeyboardMarkup(row_width=2)
            
            for service in services:
                keyboard.add(InlineKeyboardButton(service, callback_data=f"service_{service}"))
            
            keyboard.add(InlineKeyboardButton("🔙 Geri", callback_data="back_to_menu"))
            
            await callback_query.message.answer(
                "🛠 *Yeni sifariş*\n\n"
                "Xahiş edirəm, ehtiyacınız olan xidmət növünü seçin:",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            await OrderStates.selecting_service.set()
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in back_to_services: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_customer_menu(callback_query.message)
    
    @dp.callback_query_handler(lambda c: c.data.startswith('subservice_'), state=OrderStates.selecting_subservice)
    async def process_subservice_selection(callback_query: types.CallbackQuery, state: FSMContext):
        """Process the subservice selection"""
        try:
            # Extract subservice name from callback data
            selected_subservice = callback_query.data.split('_', 1)[1]
            
            # Store the selected subservice in state
            async with state.proxy() as data:
                data['subservice'] = selected_subservice
            
            # Create keyboard with location button
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(KeyboardButton("📍 Yerimi paylaş", request_location=True))
            keyboard.add(KeyboardButton("❌ Sifarişi ləğv et"))
            
            await callback_query.message.answer(
                f"Seçdiyiniz alt xidmət: *{selected_subservice}*\n\n"
                f"📍 İndi zəhmət olmasa, yerləşdiyiniz məkanı paylaşın ki, ən yaxın ustaları tapaq.\n\n"
                f"ℹ️ *Məlumat:* Yerləşdiyiniz məkanı dəqiq müəyyən etmək üçün telefonunuzda GPS xidmətinin aktiv olduğundan əmin olun.",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            await callback_query.answer()
            await OrderStates.sharing_location.set()
            
        except Exception as e:
            logger.error(f"Error in process_subservice_selection: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_customer_menu(callback_query.message)
    
    # Handler for location sharing
    @dp.message_handler(content_types=types.ContentType.LOCATION, state=OrderStates.sharing_location)
    async def process_location(message: types.Message, state: FSMContext):
        """Process the shared location"""
        try:
            # Store location in state
            latitude = message.location.latitude
            longitude = message.location.longitude
            
            # Get location name based on coordinates (if possible)
            location_name = await get_location_name(latitude, longitude)
            
            async with state.proxy() as data:
                data['latitude'] = latitude
                data['longitude'] = longitude
                data['location_name'] = location_name
            
            # Get date keyboard (next 1 day)
            keyboard = get_date_keyboard(days_ahead=1)
            
            location_text = f"📍 Yeriniz: {location_name}" if location_name else "📍 Yeriniz qeydə alındı."
            
            await message.answer(
                f"{location_text}\n\n"
                f"📅 İndi xidmətin tarixini seçin:",
                reply_markup=keyboard
            )
            
            await OrderStates.next()  # Move to date selection state
            
        except Exception as e:
            logger.error(f"Error in process_location: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.\n\n"
                "📱 Məkan paylaşarkən əgər problem yaranırsa, telefonunuzun parametrlərində GPS xidmətinin aktiv olduğundan əmin olun."
            )
            await state.finish()
            await show_customer_menu(message)
    
    # Handler for date selection
    # In customer_handler.py - modify process_date_selection
    @dp.callback_query_handler(lambda c: c.data.startswith('date_'), state=OrderStates.selecting_date)
    async def process_date_selection(callback_query: types.CallbackQuery, state: FSMContext):
        """Process the date selection"""
        try:
            # Extract date from callback data
            selected_date = callback_query.data.split('_', 1)[1]
            
            # Store the selected date in state
            async with state.proxy() as data:
                data['date'] = selected_date
            
            # Get time slots keyboard with availability flag
            keyboard, slots_available = get_time_slots_keyboard(selected_date)
            
            # Check if there are available slots
            if not slots_available and selected_date == datetime.datetime.now().strftime("%Y-%m-%d"):
                # No slots available for today
                await callback_query.message.answer(
                    "⚠️ Bu gün üçün artıq keçmiş saat seçə bilməzsiniz.\n\n"
                    "Xahiş edirik, başqa bir tarix seçin və ya sabahkı tarix üçün sifariş verin.",
                    reply_markup=get_date_keyboard(days_ahead=1)  # Show date selection again
                )
            else:
                # Show available time slots
                await callback_query.message.answer(
                    "🕒 Xidmətin saatını seçin:",
                    reply_markup=keyboard
                )
                
                await OrderStates.next()  # Move to time selection state
            
            await callback_query.answer()  # Acknowledge the callback
            
        except Exception as e:
            logger.error(f"Error in process_date_selection: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_customer_menu(callback_query.message)
    
    # Handler for going back to date selection
    @dp.callback_query_handler(lambda c: c.data == "back_to_date", state=OrderStates.selecting_time)
    async def back_to_date_selection(callback_query: types.CallbackQuery, state: FSMContext):
        """Go back to date selection"""
        try:
            # Get date keyboard
            keyboard = get_date_keyboard(days_ahead=1)
            
            await callback_query.message.answer(
                "📅 Xidmətin tarixini seçin:",
                reply_markup=keyboard
            )
            
            await callback_query.answer()  # Acknowledge the callback
            await OrderStates.selecting_date.set()  # Go back to date selection state
            
        except Exception as e:
            logger.error(f"Error in back_to_date_selection: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_customer_menu(callback_query.message)
    
    # Handler for time selection
    @dp.callback_query_handler(lambda c: c.data.startswith('time_'), state=OrderStates.selecting_time)
    async def process_time_selection(callback_query: types.CallbackQuery, state: FSMContext):
        """Process the time selection"""
        try:
            # Extract time from callback data
            selected_time = callback_query.data.split('_', 1)[1]
            
            # Store the selected time in state
            async with state.proxy() as data:
                data['time'] = selected_time
                # Combine date and time for database
                data['date_time'] = f"{data['date']} {selected_time}"
                
                # Format date and time for display
                selected_date = data['date']
                formatted_datetime = format_datetime(selected_date, selected_time)
            
            # Create note input keyboard
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(KeyboardButton("❌ Sifarişi ləğv et"))
            
            # Ask for additional notes
            await callback_query.message.answer(
                f"Seçdiyiniz tarix və saat: *{formatted_datetime}*\n\n"
                "✍️ Zəhmət olmasa, probleminiz haqqında qısa məlumat yazın. "
                "Bu, ustanın sizə daha yaxşı xidmət göstərməsinə kömək edəcək:",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            await callback_query.answer()  # Acknowledge the callback
            await OrderStates.next()  # Move to note input state
            
        except Exception as e:
            logger.error(f"Error in process_time_selection: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_customer_menu(callback_query.message)
            
    # Handler for note input
    @dp.message_handler(state=OrderStates.entering_note)
    async def process_note(message: types.Message, state: FSMContext):
        """Process the note input"""
        try:
            # Skip processing if user wants to cancel
            if message.text == "❌ Sifarişi ləğv et":
                await cancel_order_process(message, state)
                return
                
            # Store the note in state
            async with state.proxy() as data:
                data['note'] = message.text
                
                # Format date and time for display
                selected_date = data['date']
                selected_time = data['time']
                formatted_datetime = format_datetime(selected_date, selected_time)
                
                # Get location name for display
                location_display = data.get('location_name', 'Paylaşılan məkan')
                
                # Create order summary for confirmation
                service_text = data['service']
                if 'subservice' in data:
                    service_text += f" ({data['subservice']})"
                
                order_summary = (
                    "📋 *Sifariş məlumatları:*\n\n"
                    f"🛠 *Xidmət:* {service_text}\n"
                    f"📅 *Tarix və saat:* {formatted_datetime}\n"
                    f"📍 *Yer:* {location_display}\n"
                    f"📝 *Qeyd:* {data['note']}\n\n"
                    f"Bu məlumatları təsdiqləyirsiniz?"
                )
            
            # Create confirmation keyboard
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("✅ Təsdiqlə", callback_data="confirm_order"),
                InlineKeyboardButton("❌ Ləğv et", callback_data="cancel_order")
            )
            
            await message.answer(
                order_summary,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            await OrderStates.next()  # Move to confirmation state
            
        except Exception as e:
            logger.error(f"Error in process_note: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_customer_menu(message)
    
    # Handler for order confirmation
    @dp.callback_query_handler(lambda c: c.data == "confirm_order", state=OrderStates.confirming_order)
    async def confirm_order(callback_query: types.CallbackQuery, state: FSMContext):
        """Handle order confirmation"""
        try:
            # Get all order data from state
            data = await state.get_data()
            
            # Get customer information
            customer_id = get_or_create_customer(
                callback_query.from_user.id,
                callback_query.from_user.full_name
            )
            
            # Determine service for artisan matching
            service = data['service']
            
            # Find available artisans for this service
            artisans = get_nearby_artisans(
                latitude=data['latitude'], 
                longitude=data['longitude'],
                radius=10, 
                service=service,
                subservice=data.get('subservice')
            )
            
            if not artisans:
                await callback_query.message.answer(
                    "❌ Təəssüf ki, hal-hazırda bu xidmət növü üzrə usta tapılmadı. "
                    "Zəhmət olmasa, bir az sonra yenidən cəhd edin.",
                    reply_markup=types.ReplyKeyboardRemove()
                )
                await state.finish()
                await show_customer_menu(callback_query.message)
                return
            
            # Find the nearest artisan among available ones
            nearest_artisan = None
            min_distance = float('inf')
            
            for artisan in artisans:
                # Determine the data structure (tuple or dict)
                if isinstance(artisan, dict):
                    artisan_id = artisan.get('id')
                    artisan_latitude = artisan.get('latitude')
                    artisan_longitude = artisan.get('longitude')
                    artisan_name = artisan.get('name')
                else:  # It's a tuple
                    artisan_id = artisan[0]
                    artisan_name = artisan[1]
                    artisan_latitude = artisan[5] if len(artisan) > 5 else None
                    artisan_longitude = artisan[6] if len(artisan) > 6 else None
                
                if artisan_latitude and artisan_longitude:
                    from geo_helpers import calculate_distance
                    distance = calculate_distance(
                        data['latitude'], data['longitude'], 
                        artisan_latitude, artisan_longitude
                    )
                    
                    if distance < min_distance:
                        min_distance = distance
                        nearest_artisan = artisan
            
            # If no nearest found, just take the first one
            if not nearest_artisan and artisans:
                nearest_artisan = artisans[0]
            
            if nearest_artisan:
                # Extract artisan ID and name based on type
                if isinstance(nearest_artisan, dict):
                    artisan_id = nearest_artisan.get('id')
                    artisan_name = nearest_artisan.get('name')
                else:  # It's a tuple
                    artisan_id = nearest_artisan[0]
                    artisan_name = nearest_artisan[1]
                
                # Determine which subservice to store (if any)
                subservice = data.get('subservice')
                
                # Insert the order into the database
                try:
                    location_name = await get_location_name(data['latitude'], data['longitude'])

                    order_id = insert_order(
                        customer_id=customer_id,
                        artisan_id=artisan_id,
                        service=service,
                        date_time=data['date_time'],
                        note=data['note'],
                        latitude=data['latitude'],
                        longitude=data['longitude'],
                        location_name=location_name,
                        subservice=subservice,
                        status = "pending"
                    )
                    
                    # Send confirmation to the customer
                    await callback_query.message.answer(
                        f"✅ Sifarişiniz uğurla qəbul olundu! (Sifariş #{order_id}).\n\n"
                        f"*{artisan_name}* adlı ustaya sifarişiniz haqqında bildiriş göndərildi.\n"
                        f"Usta sifarişinizi qəbul etdikdən sonra sizə xəbər veriləcək.",
                        parse_mode="Markdown",
                        reply_markup=types.ReplyKeyboardRemove()
                    )
                    
                    # Import notification service
                    try:
                        from notification_service import notify_artisan_about_new_order
                        
                        # Notify artisan about new order
                        await notify_artisan_about_new_order(order_id, artisan_id)
                    except ImportError as ie:
                        logger.error(f"Failed to import notification_service: {ie}")
                    except Exception as e:
                        logger.error(f"Failed to notify artisan: {e}")
                    
                    # Reset to main customer menu
                    await show_customer_menu(callback_query.message)
                    
                except Exception as e:
                    logger.error(f"Database error when inserting order: {e}")
                    await callback_query.message.answer(
                        f"❌ Sifariş yaradılarkən xəta baş verdi. Zəhmət olmasa, bir az sonra yenidən cəhd edin.",
                        reply_markup=types.ReplyKeyboardRemove()
                    )
                    await show_customer_menu(callback_query.message)
            else:
                await callback_query.message.answer(
                    "❌ Təəssüf ki, hal-hazırda bu xidmət növü üzrə usta tapılmadı. "
                    "Zəhmət olmasa, bir az sonra yenidən cəhd edin.",
                    reply_markup=types.ReplyKeyboardRemove()
                )
                await show_customer_menu(callback_query.message)
            
            await callback_query.answer()  # Acknowledge the callback
            await state.finish()  # End the conversation
            
        except Exception as e:
            logger.error(f"Error in confirm_order: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_customer_menu(callback_query.message)
    
    # Handler for explicit order cancellation
    @dp.message_handler(lambda message: message.text == "❌ Sifarişi ləğv et", state="*")
    async def cancel_order_process(message: types.Message, state: FSMContext):
        """Explicitly cancel the order process"""
        try:
            current_state = await state.get_state()
            if current_state:
                await state.finish()
            
            await message.answer(
                "❌ Sifariş prosesi ləğv edildi.",
                reply_markup=types.ReplyKeyboardRemove()
            )
            
            # Return to customer menu
            await show_customer_menu(message)
            
        except Exception as e:
            logger.error(f"Error in cancel_order_process: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_customer_menu(message)
    
    # Handler for order cancellation from confirmation
    @dp.callback_query_handler(lambda c: c.data == "cancel_order", state=OrderStates.confirming_order)
    async def cancel_order(callback_query: types.CallbackQuery, state: FSMContext):
        """Handle order cancellation from confirmation"""
        try:
            await callback_query.message.answer(
                "❌ Sifariş ləğv edildi.",
                reply_markup=types.ReplyKeyboardRemove()
            )
            
            # Return to customer menu
            await show_customer_menu(callback_query.message)
            
            await callback_query.answer()  # Acknowledge the callback
            await state.finish()  # End the conversation
            
        except Exception as e:
            logger.error(f"Error in cancel_order: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_customer_menu(callback_query.message)
    
    # Handler for "View previous orders" button
    @dp.message_handler(lambda message: message.text == "📜 Əvvəlki sifarişlərə bax")
    async def view_previous_orders(message: types.Message):
        """Handle viewing previous orders"""
        try:
            # Müşteri bilgilerini al
            telegram_id = message.from_user.id
            customer = get_customer_by_telegram_id(telegram_id)
            
            if not customer:
                await message.answer(
                    "❌ Sizin profiliniz tapılmadı. Zəhmət olmasa, qeydiyyatdan keçin."
                )
                return
                
            customer_id = customer.get('id')
            
            # Müşteri siparişlerini al
            orders = get_customer_orders(customer_id)
            
            if not orders:
                # Sipariş yoksa mesaj göster
                await message.answer(
                    "📭 Hələlik heç bir sifarişiniz yoxdur.",
                    reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(
                        KeyboardButton("✅ Yeni sifariş ver"),
                        KeyboardButton("🔙 Geri")
                    )
                )
                return
            
            await message.answer("📋 *Son sifarişləriniz:*", parse_mode="Markdown")
            
            # Her siparişi göster
            for order in orders:
                # Sözlük erişimiyle değerleri al (order[0] yerine order.get('id') gibi)
                order_id = order.get('id')
                service = order.get('service')
                date_time = order.get('date_time')
                note = order.get('note')
                status = order.get('status')
                artisan_name = order.get('artisan_name')
                artisan_phone = order.get('artisan_phone')
                
                # Tarih formatlama için try-except bloğu
                try:
                    import datetime
                    dt_obj = datetime.datetime.strptime(str(date_time), "%Y-%m-%d %H:%M:%S")
                    formatted_date = dt_obj.strftime("%d.%m.%Y")
                    formatted_time = dt_obj.strftime("%H:%M")
                except Exception as e:
                    logger.error(f"Error formatting date: {e}")
                    formatted_date = str(date_time).split(" ")[0] if date_time else "Bilinmiyor"
                    formatted_time = str(date_time).split(" ")[1] if date_time and " " in str(date_time) else "Bilinmiyor"
                
                # Duruma göre emoji ayarla
                status_emoji = "⏳" if status == "pending" else "✅" if status == "completed" else "👍" if status == "accepted" else "❌"
                status_text = "Gözləyir" if status == "pending" else "Tamamlanıb" if status == "completed" else "Qəbul edildi" if status == "accepted" else "Ləğv edilib"
                
                # Sipariş metnini oluştur
                order_text = (
                    f"🔹 *Sifariş #{order_id}*\n"
                    f"🛠 *Xidmət:* {service}\n"
                    f"👤 *Usta:* {artisan_name}\n"
                    f"📞 *Əlaqə:* {artisan_phone}\n"
                    f"📅 *Tarix:* {formatted_date}\n"
                    f"🕒 *Saat:* {formatted_time}\n"
                    f"📝 *Qeyd:* {note}\n"
                    f"🔄 *Status:* {status_emoji} {status_text}\n"
                )
                
                # Bekleyen siparişler için düğmeler göster
                if status == "pending":
                    keyboard = InlineKeyboardMarkup(row_width=1)
                    keyboard.add(
                        InlineKeyboardButton("❌ Sifarişi ləğv et", callback_data=f"cancel_order_{order_id}")
                    )
                    
                    await message.answer(
                        order_text,
                        reply_markup=keyboard,
                        parse_mode="Markdown"
                    )
                else:
                    await message.answer(
                        order_text,
                        parse_mode="Markdown"
                    )
            
            # Geri dönüş düğmelerini göster
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(KeyboardButton("✅ Yeni sifariş ver"))
            keyboard.add(KeyboardButton("🔙 Geri"))
            
            await message.answer(
                "Əməliyyat seçin:",
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"Error in view_previous_orders: {e}")
            await message.answer(
                "❌ Sifarişlər yüklənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await show_customer_menu(message)
    
    # Handler for canceling a specific order from history
    @dp.callback_query_handler(lambda c: c.data.startswith('cancel_order_'))
    async def cancel_specific_order(callback_query: types.CallbackQuery):
        """Cancel a specific order from order history"""
        try:
            # Extract order ID from callback data
            order_id = int(callback_query.data.split('_')[-1])
            
            # Update order status in database
            success = update_order_status(order_id, "cancelled")
            
            if success:
                await callback_query.message.answer(
                    f"✅ Sifariş #{order_id} uğurla ləğv edildi."
                )
            else:
                await callback_query.message.answer(
                    f"❌ Sifariş #{order_id} ləğv edilərkən xəta baş verdi. Zəhmət olmasa, bir az sonra yenidən cəhd edin."
                )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in cancel_specific_order: {e}")
            await callback_query.message.answer(
                "❌ Sifariş ləğv edilərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
    
    # Handler for "Show nearby artisans" button
    @dp.message_handler(lambda message: message.text == "🌍 Yaxınlıqdakı ustaları göstər")
    async def start_nearby_artisans(message: types.Message, state: FSMContext):
        """Start the process of showing nearby artisans"""
        try:
            # Create keyboard with location button
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(KeyboardButton("📍 Yerimi paylaş", request_location=True))
            keyboard.add(KeyboardButton("🔙 Geri"))
            
            await message.answer(
                "📍 Yaxınlıqdakı ustaları tapmaq üçün, zəhmət olmasa, yerləşdiyiniz məkanı paylaşın.\n\n"
                "ℹ️ *Məlumat:* Yerləşdiyiniz məkanı dəqiq müəyyən etmək üçün telefonunuzda GPS xidmətinin aktiv olduğundan əmin olun.",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            await NearbyArtisanStates.sharing_location.set()
            
        except Exception as e:
            logger.error(f"Error in start_nearby_artisans: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await show_customer_menu(message)
    
    # Handler for location sharing (nearby artisans)
    @dp.message_handler(content_types=types.ContentType.LOCATION, state=NearbyArtisanStates.sharing_location)
    async def process_location_for_nearby(message: types.Message, state: FSMContext):
        """Process shared location for finding nearby artisans"""
        try:
            latitude = message.location.latitude
            longitude = message.location.longitude
            
            # Get location name based on coordinates
            location_name = await get_location_name(latitude, longitude)
            
            # Store location in state
            async with state.proxy() as data:
                data['latitude'] = latitude
                data['longitude'] = longitude
                data['location_name'] = location_name
            
            # Get service filter options
            services = get_services()
            
            # Create keyboard for selecting services or viewing all
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(InlineKeyboardButton("🔍 Bütün ustalar", callback_data="nearby_all"))
            
            for service in services:
                keyboard.add(InlineKeyboardButton(service, callback_data=f"nearby_service_{service}"))
            
            location_text = f"📍 Yeriniz: {location_name}" if location_name else "📍 Yeriniz qeydə alındı."
            
            await message.answer(
                f"{location_text}\n\n"
                f"🔍 Hansı xidmət növü üzrə ustaları görmək istəyirsiniz?",
                reply_markup=keyboard
            )
            
            await NearbyArtisanStates.filtering_by_service.set()
            
        except Exception as e:
            logger.error(f"Error in process_location_for_nearby: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.\n\n"
                "📱 Məkan paylaşarkən əgər problem yaranırsa, telefonunuzun parametrlərində GPS xidmətinin aktiv olduğundan əmin olun."
            )
            await state.finish()
            await show_customer_menu(message)
    
    # Handler for service filter selection (nearby artisans)
    @dp.callback_query_handler(
        lambda c: c.data.startswith('nearby_'), 
        state=NearbyArtisanStates.filtering_by_service
    )
    async def process_nearby_filter(callback_query: types.CallbackQuery, state: FSMContext):
        """Process service filter selection for nearby artisans"""
        try:
            # Get location from state
            data = await state.get_data()
            latitude = data['latitude']
            longitude = data['longitude']
            
            # Determine if filtering by service
            filter_data = callback_query.data.split('_', 2)
            
            if len(filter_data) == 3 and filter_data[1] == "service":
                service = filter_data[2]
                # Find nearby artisans with service filter
                artisans = get_nearby_artisans(latitude, longitude, radius=10, service=service)
                await callback_query.message.answer(
                    f"🔍 *{service}* xidməti göstərən yaxınlıqdakı ustalar axtarılır...",
                    parse_mode="Markdown"
                )
            else:
                # Find all nearby artisans
                artisans = get_nearby_artisans(latitude, longitude, radius=10)
                await callback_query.message.answer(
                    "🔍 Yaxınlıqdakı bütün ustalar axtarılır..."
                )
            
            if not artisans:
                await callback_query.message.answer(
                    "❌ Təəssüf ki, yaxınlıqda heç bir usta tapılmadı. "
                    "Zəhmət olmasa, daha sonra yenidən cəhd edin."
                )
                
                # Return to customer menu
                await show_customer_menu(callback_query.message)
                
                await callback_query.answer()
                await state.finish()
                return
            
            await callback_query.message.answer(
                f"🔍 Yaxınlıqda *{len(artisans)}* usta tapıldı:",
                parse_mode="Markdown"
            )
            
            # Display each artisan
            for artisan in artisans:
                artisan_id = artisan[0]     # ID
                name = artisan[1]           # Name
                phone = artisan[2]          # Phone
                service = artisan[3]        # Service
                location = artisan[4]       # Location
                distance = artisan[-1]      # Distance (added by get_nearby_artisans)
                
                # Format distance
                formatted_distance = format_distance(distance)
                
                artisan_text = (
                    f"👤 *{name}*\n"
                    f"🛠 *Xidmət:* {service}\n"
                    f"📞 *Əlaqə:* {phone}\n"
                    f"🏙 *Ərazi:* {location}\n"
                    f"📏 *Məsafə:* {formatted_distance}\n"
                )
                
                # Create an inline button to immediately order from this artisan
                keyboard = InlineKeyboardMarkup()
                keyboard.add(
                    InlineKeyboardButton(
                        "✅ Bu ustadan sifariş ver", 
                        callback_data=f"order_from_{artisan_id}"
                    )
                )
                
                await callback_query.message.answer(
                    artisan_text,
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
            
            # Return to customer menu
            await show_customer_menu(callback_query.message)
            
            await callback_query.answer()
            await state.finish()
            
        except Exception as e:
            logger.error(f"Error in process_nearby_filter: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_customer_menu(callback_query.message)

        # Handler for profile management
    @dp.message_handler(lambda message: message.text == "👤 Profilim")
    async def show_profile(message: types.Message, state: FSMContext):
        """Show customer profile"""
        try:
            # Get customer information
            telegram_id = message.from_user.id
            customer = get_customer_by_telegram_id(telegram_id)
            
            if not customer:
                await message.answer(
                    "❌ Sizin profiliniz tapılmadı. Zəhmət olmasa, qeydiyyatdan keçin."
                )
                await start_customer_registration(message, state)
                return
            
            # Display profile information
            profile_text = (
                "👤 *Profiliniz*\n\n"
                f"👤 *Ad:* {customer.get('name', 'Təyin edilməyib')}\n"
                f"📞 *Telefon:* {customer.get('phone', 'Təyin edilməyib')}\n"
                f"🏙 *Şəhər:* {customer.get('city', 'Təyin edilməyib')}\n"
            )
            
            # Create profile management keyboard
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                InlineKeyboardButton("✏️ Adımı dəyiş", callback_data="edit_name"),
                InlineKeyboardButton("📞 Telefon nömrəmi dəyiş", callback_data="edit_phone"),
                InlineKeyboardButton("🏙 Şəhərimi dəyiş", callback_data="edit_city"),
                InlineKeyboardButton("🔙 Geri", callback_data="back_to_menu")
            )
            
            await message.answer(
                profile_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            await ProfileManagementStates.viewing_profile.set()
            
        except Exception as e:
            logger.error(f"Error in show_profile: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await show_customer_menu(message)
    
    @dp.callback_query_handler(lambda c: c.data == "edit_name", state=ProfileManagementStates.viewing_profile)
    async def edit_name(callback_query: types.CallbackQuery, state: FSMContext):
        """Start editing customer name"""
        try:
            await callback_query.message.answer(
                "👤 Zəhmət olmasa, yeni adınızı daxil edin:"
            )
            
            await ProfileManagementStates.updating_name.set()
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in edit_name: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_customer_menu(callback_query.message)
    
    @dp.message_handler(state=ProfileManagementStates.updating_name)
    async def process_updated_name(message: types.Message, state: FSMContext):
        """Process updated customer name"""
        try:
            # Validate and store name
            name = message.text.strip()
            
            if len(name) < 2 or len(name) > 50:
                await message.answer(
                    "❌ Ad ən azı 2, ən çoxu 50 simvol olmalıdır. Zəhmət olmasa, yenidən daxil edin:"
                )
                return
            
            # Update customer name in database
            telegram_id = message.from_user.id
            success = update_customer_profile(telegram_id, {'name': name})
            
            if success:
                await message.answer(
                    "✅ Adınız uğurla yeniləndi!"
                )
            else:
                await message.answer(
                    "❌ Adınız yenilənərkən xəta baş verdi. Zəhmət olmasa, bir az sonra yenidən cəhd edin."
                )
            
            # Show updated profile
            await show_profile(message, state)
            
        except Exception as e:
            logger.error(f"Error in process_updated_name: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_customer_menu(message)
    
    @dp.callback_query_handler(lambda c: c.data == "edit_phone", state=ProfileManagementStates.viewing_profile)
    async def edit_phone(callback_query: types.CallbackQuery, state: FSMContext):
        """Start editing customer phone"""
        try:
            await callback_query.message.answer(
                "📞 Zəhmət olmasa, yeni telefon nömrənizi daxil edin (məsələn: +994501234567):"
            )
            
            await ProfileManagementStates.updating_phone.set()
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in edit_phone: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_customer_menu(callback_query.message)
    
    @dp.message_handler(state=ProfileManagementStates.updating_phone)
    async def process_updated_phone(message: types.Message, state: FSMContext):
        """Process updated customer phone"""
        try:
            # Get and validate phone number
            phone = message.text.strip()
            
            # Simple regex for Azerbaijani phone numbers
            phone_regex = r'^\+?994\d{9}$|^0\d{9}$'
            
            if not re.match(phone_regex, phone):
                await message.answer(
                    "❌ Düzgün telefon nömrəsi daxil edin (məsələn: +994501234567 və ya 0501234567):"
                )
                return
            
            # Normalize phone format
            if phone.startswith("0"):
                phone = "+994" + phone[1:]
            elif not phone.startswith("+"):
                phone = "+" + phone
            
            # Update customer phone in database
            telegram_id = message.from_user.id
            success = update_customer_profile(telegram_id, {'phone': phone})
            
            if success:
                await message.answer(
                    "✅ Telefon nömrəniz uğurla yeniləndi!"
                )
            else:
                await message.answer(
                    "❌ Telefon nömrəniz yenilənərkən xəta baş verdi. Zəhmət olmasa, bir az sonra yenidən cəhd edin."
                )
            
            # Show updated profile
            await show_profile(message, state)
            
        except Exception as e:
            logger.error(f"Error in process_updated_phone: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_customer_menu(message)
    
    @dp.callback_query_handler(lambda c: c.data == "edit_city", state=ProfileManagementStates.viewing_profile)
    async def edit_city(callback_query: types.CallbackQuery, state: FSMContext):
        """Start editing customer city"""
        try:
            await callback_query.message.answer(
                "🏙 Zəhmət olmasa, yeni şəhərinizi daxil edin:"
            )
            
            await ProfileManagementStates.updating_city.set()
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in edit_city: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_customer_menu(callback_query.message)
    
    @dp.message_handler(state=ProfileManagementStates.updating_city)
    async def process_updated_city(message: types.Message, state: FSMContext):
        """Process updated customer city"""
        try:
            # Validate and store city
            city = message.text.strip()
            
            if len(city) < 2 or len(city) > 50:
                await message.answer(
                    "❌ Şəhər adı ən azı 2, ən çoxu 50 simvol olmalıdır. Zəhmət olmasa, yenidən daxil edin:"
                )
                return
            
            # Update customer city in database
            telegram_id = message.from_user.id
            success = update_customer_profile(telegram_id, {'city': city})
            
            if success:
                await message.answer(
                    "✅ Şəhəriniz uğurla yeniləndi!"
                )
            else:
                await message.answer(
                    "❌ Şəhəriniz yenilənərkən xəta baş verdi. Zəhmət olmasa, bir az sonra yenidən cəhd edin."
                )
            
            # Show updated profile
            await show_profile(message, state)
            
        except Exception as e:
            logger.error(f"Error in process_updated_city: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_customer_menu(message)
    
    @dp.callback_query_handler(lambda c: c.data == "back_to_menu", state="*")
    async def back_to_menu_handler(callback_query: types.CallbackQuery, state: FSMContext):
        """Handle back to menu button from any state"""
        try:
            current_state = await state.get_state()
            if current_state:
                await state.finish()
            
            await callback_query.message.answer(
                "Əsas müştəri menyusuna qayıdılır..."
            )
            
            await show_customer_menu(callback_query.message)
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in back_to_menu_handler: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_customer_menu(callback_query.message)
    
    # Handler for "Services" button
    @dp.message_handler(lambda message: message.text == "🔍 Xidmətlər")
    async def show_services(message: types.Message):
        """Show available services"""
        try:
            # Get available services
            services = get_services()
            
            if not services:
                await message.answer("❌ Təəssüf ki, hal-hazırda heç bir xidmət mövcud deyil.")
                return
            
            # Create a message with all available services
            services_text = "🛠 *Mövcud xidmətlər:*\n\n"
            
            for i, service in enumerate(services, 1):
                services_text += f"{i}. {service}\n"
                
                # Get subservices for this service
                subservices = get_subservices(service)
                if subservices:
                    for j, subservice in enumerate(subservices, 1):
                        services_text += f"   {i}.{j}. {subservice}\n"
            
            services_text += "\nSifariş vermək üçün \"✅ Yeni sifariş ver\" düyməsinə klikləyin."
            
            await message.answer(
                services_text,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Error in show_services: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await show_customer_menu(message)
    
    # Handler for returning to main menu (role selection)
    @dp.message_handler(lambda message: message.text == "🏠 Əsas menyuya qayıt")
    async def return_to_main_menu(message: types.Message, state: FSMContext):
        """Return to the main menu (role selection)"""
        try:
            current_state = await state.get_state()
            if current_state:
                await state.finish()
            
            await show_role_selection(message)
            
        except Exception as e:
            logger.error(f"Error in return_to_main_menu: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_role_selection(message)
    
    # Handler for order from specific artisan
    @dp.callback_query_handler(lambda c: c.data.startswith('order_from_'))
    async def order_from_artisan(callback_query: types.CallbackQuery, state: FSMContext):
        """Start ordering process from a specific artisan"""
        try:
            # Extract artisan ID from callback data
            artisan_id = int(callback_query.data.split('_')[-1])
            
            # Get artisan info
            artisan = get_artisan_by_id(artisan_id)
            
            if not artisan:
                await callback_query.message.answer(
                    "❌ Təəssüf ki, seçdiyiniz usta tapılmadı. "
                    "Zəhmət olmasa, başqa ustanı seçin."
                )
                await callback_query.answer()
                await show_customer_menu(callback_query.message)
                return
            
            # Store artisan info in state
            await state.finish()  # Clear any previous state
            await OrderStates.selecting_service.set()
            
            async with state.proxy() as data:
                data['artisan_id'] = artisan_id
                data['service'] = artisan[3]  # Service is the 4th column
            
            # Get subservices for this service
            subservices = get_subservices(artisan[3])
            
            if subservices:
                # Create keyboard with subservice options
                keyboard = InlineKeyboardMarkup(row_width=1)
                
                for subservice in subservices:
                    keyboard.add(
                        InlineKeyboardButton(
                            subservice, 
                            callback_data=f"subservice_{subservice}"
                        )
                    )
                
                keyboard.add(InlineKeyboardButton("🔙 Geri", callback_data="back_to_menu"))
                
                await callback_query.message.answer(
                    f"Siz *{artisan[1]}* adlı ustadan *{artisan[3]}* xidməti sifariş vermək istəyirsiniz.\n\n"
                    f"İndi zəhmət olmasa, daha dəqiq xidmət növünü seçin:",
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
                
                await OrderStates.selecting_subservice.set()
            else:
                # If no subservices (unlikely), proceed directly to location
                keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
                keyboard.add(KeyboardButton("📍 Yerimi paylaş", request_location=True))
                keyboard.add(KeyboardButton("❌ Sifarişi ləğv et"))
                
                await callback_query.message.answer(
                    f"Siz *{artisan[1]}* adlı ustadan *{artisan[3]}* xidməti sifariş vermək istəyirsiniz.\n\n"
                    f"📍 İndi zəhmət olmasa, yerləşdiyiniz məkanı paylaşın:",
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
                
                await OrderStates.sharing_location.set()
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in order_from_artisan: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_customer_menu(callback_query.message)
    
    # Handler for "back" button
    @dp.message_handler(lambda message: message.text == "🔙 Geri", state="*")
    async def go_back_to_menu(message: types.Message, state: FSMContext):
        """Go back to the main menu from any state"""
        try:
            # Cancel the current operation
            current_state = await state.get_state()
            if current_state is not None:
                await state.finish()
            
            # Reset main customer menu
            await show_customer_menu(message)
            
        except Exception as e:
            logger.error(f"Error in go_back_to_menu: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_customer_menu(message)    

    @dp.callback_query_handler(lambda c: c.data == "continue_customer_registration")
    async def continue_customer_registration(callback_query: types.CallbackQuery, state: FSMContext):
        """Continue customer registration after confirmation"""
        try:
            await start_customer_registration(callback_query.message, state)
            await callback_query.answer()
        except Exception as e:
            logger.error(f"Error in continue_customer_registration: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_role_selection(callback_query.message)

    @dp.callback_query_handler(lambda c: c.data == "back_to_role_selection")
    async def back_to_role_selection_handler(callback_query: types.CallbackQuery, state: FSMContext):
        """Go back to role selection"""
        try:
            await state.finish()
            await show_role_selection(callback_query.message)
            await callback_query.answer()
        except Exception as e:
            logger.error(f"Error in back_to_role_selection_handler: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_role_selection(callback_query.message) 


    @dp.callback_query_handler(lambda c: c.data.startswith('confirm_arrival_'))
    async def confirm_artisan_arrival(callback_query: types.CallbackQuery):
        """Müşterinin ustanın geldiğini onaylaması"""
        try:
            # Extract order ID from callback data
            order_id = int(callback_query.data.split('_')[-1])
            
            # Get order details
            order = get_order_details(order_id)
            
            if not order:
                await callback_query.message.answer(
                    "❌ Sifariş tapılmadı. Silinmiş və ya ləğv edilmiş ola bilər."
                )
                await callback_query.answer()
                return
            
            # Get customer ID
            telegram_id = callback_query.from_user.id
            customer = get_customer_by_telegram_id(telegram_id)
            
            if not customer:
                await callback_query.message.answer(
                    "❌ Müştəri məlumatlarınız tapılmadı."
                )
                await callback_query.answer()
                return
            
            # Check if the order belongs to this customer
            if order['customer_id'] != customer['id']:
                await callback_query.message.answer(
                    "❌ Bu sifariş sizə aid deyil."
                )
                await callback_query.answer()
                return
            
            # Import price request function
            from order_status_service import request_price_from_artisan
            
            # Request price from artisan
            await request_price_from_artisan(order_id)
            
            await callback_query.message.answer(
                f"✅ Ustanın gəlişini təsdiqlədiniz.\n\n"
                f"Usta xidmətə başlayacaq və qiymət təyin edəcək. "
                f"Qiymət təyin edildikdə, sizə bildiriş gələcək."
            )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in confirm_artisan_arrival: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer() 


    @dp.callback_query_handler(lambda c: c.data.startswith('deny_arrival_'))
    async def deny_artisan_arrival(callback_query: types.CallbackQuery):
        """Müşterinin ustanın gelmediğini bildirmesi"""
        try:
            # Extract order ID from callback data
            order_id = int(callback_query.data.split('_')[-1])
            
            # Get order details
            order = get_order_details(order_id)
            
            if not order:
                await callback_query.message.answer(
                    "❌ Sifariş tapılmadı. Silinmiş və ya ləğv edilmiş ola bilər."
                )
                await callback_query.answer()
                return
            
            # Import warning function
            from order_status_service import handle_arrival_warning
            
            # Schedule arrival warning
            asyncio.create_task(handle_arrival_warning(order_id))
            
            await callback_query.message.answer(
                f"⚠️ Ustanın məkanda olmadığı bildirildi.\n\n"
                f"Ustaya 5 dəqiqə ərzində gəlməsi üçün xəbərdarlıq ediləcək.\n"
                f"5 dəqiqə sonra sizdən yenidən soruşulacaq."
            )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in deny_artisan_arrival: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()


    @dp.callback_query_handler(lambda c: c.data.startswith('final_deny_arrival_'))
    async def final_deny_artisan_arrival(callback_query: types.CallbackQuery):
        """Müşterinin ustanın son uyarıdan sonra da gelmediğini bildirmesi"""
        try:
            # Extract order ID from callback data
            order_id = int(callback_query.data.split('_')[-1])
            
            # Get order details
            order = get_order_details(order_id)
            
            if not order:
                await callback_query.message.answer(
                    "❌ Sifariş tapılmadı. Silinmiş və ya ləğv edilmiş ola bilər."
                )
                await callback_query.answer()
                return
            
            # Import block function
            from order_status_service import block_artisan_for_no_show
            
            # Block artisan for no-show
            await block_artisan_for_no_show(order_id)
            
            await callback_query.message.answer(
                f"🎁 Üzrxahlıq olaraq növbəti sifarişiniz üçün 10 AZN endirim qazandınız.\n\n"
                f"Yeni bir sifariş verməyiniz tövsiyə olunur."
            )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in final_deny_artisan_arrival: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()



    # Ödeme süreci için callback handler'lar
    @dp.callback_query_handler(lambda c: c.data.startswith('accept_price_'))
    async def accept_price(callback_query: types.CallbackQuery):
        """Müşterinin qiyməti qəbul etməsi"""
        try:
            # Extract order ID from callback data
            order_id = int(callback_query.data.split('_')[-1])
            logger.info(f"Price acceptance callback received for order {order_id}")
            
            # Get order details
            order = get_order_details(order_id)
            
            if not order:
                logger.error(f"Order {order_id} not found")
                await callback_query.message.answer(
                    "❌ Sifariş tapılmadı. Silinmiş və ya ləğv edilmiş ola bilər."
                )
                await callback_query.answer()
                return
                
            # Log retrieved order details for debugging
            logger.info(f"Order details for order {order_id}: {order}")
            
            # Check if price exists in orders table directly
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT price FROM orders WHERE id = %s", (order_id,))
            direct_price = cursor.fetchone()
            conn.close()
            
            logger.info(f"Direct price query for order {order_id}: {direct_price}")
            
            # Ensure price is set before proceeding
            price = order.get('price')
            if price is None or price == 0:
                # If direct_price is available, update the order object
                if direct_price and direct_price[0]:
                    price = direct_price[0]
                    order['price'] = price
                    logger.info(f"Using direct price from orders table: {price}")
                else:
                    logger.error(f"Price not set for order {order_id}")
                    await callback_query.message.answer(
                        "❌ Bu sifariş üçün qiymət hələ təyin edilməyib. Zəhmət olmasa, bir az sonra yenidən cəhd edin."
                    )
                    await callback_query.answer()
                    return
            
            # Import payment options function
            from payment_service import notify_customer_about_payment_options
            
            # First, notify artisan about price acceptance
            try:
                from notification_service import notify_artisan_about_price_acceptance
                logger.info(f"Attempting to notify artisan for order {order_id}")
                success_notify = await notify_artisan_about_price_acceptance(order_id)
                if not success_notify:
                    logger.error(f"Failed to notify artisan about price acceptance for order {order_id}")
                    # Continue anyway, this shouldn't block the payment process
            except Exception as e:
                logger.error(f"Error notifying artisan about price acceptance: {e}", exc_info=True)
                # Continue with payment options even if artisan notification fails
            
            # Show payment options to customer
            logger.info(f"Showing payment options for order {order_id}")
            success = await notify_customer_about_payment_options(order_id)
            
            if success:
                await callback_query.message.answer(
                    f"✅ Qiyməti qəbul etdiniz.\n\n"
                    f"İndi ödəniş üsulunu seçə bilərsiniz."
                )
            else:
                logger.error(f"Failed to show payment options for order {order_id}")
                await callback_query.message.answer(
                    "❌ Ödəniş məlumatları yüklənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in accept_price: {e}", exc_info=True)
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith('reject_price_'))
    async def reject_price(callback_query: types.CallbackQuery):
        """Müşterinin fiyatı reddetmesi"""
        try:
            # Extract order ID from callback data
            order_id = int(callback_query.data.split('_')[-1])
            
            # Get order details
            order = get_order_details(order_id)
            
            if not order:
                await callback_query.message.answer(
                    "❌ Sifariş tapılmadı. Silinmiş və ya ləğv edilmiş ola bilər."
                )
                await callback_query.answer()
                return
            
            # Update order status to cancelled
            update_order_status(order_id, "cancelled")
            
            # Notify artisan about rejection
            artisan = get_artisan_by_id(order['artisan_id'])
            if artisan and artisan.get('telegram_id'):
                await bot.send_message(
                    chat_id=artisan['telegram_id'],
                    text=f"❌ *Qiymət rədd edildi*\n\n"
                        f"Təəssüf ki, müştəri sifariş #{order_id} üçün təyin etdiyiniz "
                        f"qiyməti qəbul etmədi. Sifariş ləğv edildi.",
                    parse_mode="Markdown"
                )
            
            await callback_query.message.answer(
                f"❌ Qiyməti rədd etdiniz. Sifariş ləğv edildi.\n\n"
                f"Başqa bir usta tapmaq üçün yeni sifariş verə bilərsiniz."
            )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in reject_price: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()



    @dp.callback_query_handler(lambda c: c.data.startswith('pay_card_'))
    async def pay_by_card(callback_query: types.CallbackQuery):
        """Müştərinin kart ilə ödəmə seçməsi"""
        try:
            # Extract order ID from callback data
            order_id = int(callback_query.data.split('_')[-1])
            
            # Get order details
            order = get_order_details(order_id)
            
            if not order:
                await callback_query.message.answer(
                    "❌ Sifariş tapılmadı. Silinmiş və ya ləğv edilmiş ola bilər."
                )
                await callback_query.answer()
                return
            
            # Import payment functions
            from payment_service import notify_artisan_about_payment_method, notify_customer_about_card_payment
            
            # Notify artisan about payment method
            artisan_notified = await notify_artisan_about_payment_method(order_id, "card")
            
            # Notify customer about card payment details
            customer_notified = await notify_customer_about_card_payment(order_id)
            
            if not artisan_notified or not customer_notified:
                await callback_query.message.answer(
                    "❌ Ödəniş məlumatları göndərilməsində xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in pay_by_card: {e}", exc_info=True)
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()


    @dp.callback_query_handler(lambda c: c.data.startswith('pay_cash_'))
    async def pay_by_cash(callback_query: types.CallbackQuery):
        """Müştərinin nağd ödəmə seçməsi"""
        try:
            # Extract order ID from callback data
            order_id = int(callback_query.data.split('_')[-1])
            
            # Get order details
            order = get_order_details(order_id)
            
            if not order:
                await callback_query.message.answer(
                    "❌ Sifariş tapılmadı. Silinmiş və ya ləğv edilmiş ola bilər."
                )
                await callback_query.answer()
                return
            
            # Import payment functions
            from payment_service import notify_artisan_about_payment_method, notify_customer_about_cash_payment
            
            # Notify artisan about payment method
            artisan_notified = await notify_artisan_about_payment_method(order_id, "cash")
            
            # Notify customer about cash payment
            customer_notified = await notify_customer_about_cash_payment(order_id)
            
            if not artisan_notified or not customer_notified:
                await callback_query.message.answer(
                    "❌ Ödəniş məlumatları göndərilməsində xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in pay_by_cash: {e}", exc_info=True)
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()


    @dp.callback_query_handler(lambda c: c.data.startswith('payment_completed_'))
    async def card_payment_completed(callback_query: types.CallbackQuery):
        """Müştərinin kart ödəməsini tamamlaması"""
        try:
            # Extract order ID from callback data
            order_id = int(callback_query.data.split('_')[-1])
            
            # Ask for receipt
            await callback_query.message.answer(
                "📸 Zəhmət olmasa, ödəniş qəbzinin şəklini göndərin.\n\n"
                "Bu, ödənişin təsdiqlənməsi üçün lazımdır. Şəkil aydın və oxunaqlı olmalıdır."
            )
            
            # Set context for receipt upload
            telegram_id = callback_query.from_user.id
            set_user_context(telegram_id, {
                "action": "card_payment_receipt",
                "order_id": order_id
            })
            
            # Log the action
            logger.info(f"Card payment completed action initiated for order {order_id}")
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in card_payment_completed: {e}", exc_info=True)
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()


    @dp.callback_query_handler(lambda c: c.data.startswith('cash_payment_completed_'))
    async def cash_payment_completed(callback_query: types.CallbackQuery):
        """Müştərinin nağd ödəməsini tamamlaması"""
        try:
            # Extract order ID from callback data
            order_id = int(callback_query.data.split('_')[-1])
            
            # Get order details
            order = get_order_details(order_id)
            
            if not order:
                await callback_query.message.answer(
                    "❌ Sifariş tapılmadı. Silinmiş və ya ləğv edilmiş ola bilər."
                )
                await callback_query.answer()
                return
            
            # Notify artisan
            artisan = get_artisan_by_id(order['artisan_id'])
            if artisan and artisan.get('telegram_id'):
                await bot.send_message(
                    chat_id=artisan['telegram_id'],
                    text=f"✅ *Nağd ödəniş təsdiqləndi*\n\n"
                        f"Müştəri sifariş #{order_id} üçün nağd ödənişi tamamladığını təsdiqlədi.\n\n"
                        f"Zəhmət olmasa, 24 saat ərzində komissiya məbləğini admin kartına köçürün.",
                    parse_mode="Markdown"
                )
                
                # Schedule commission payment deadline notification
                from payment_service import handle_admin_payment_deadline
                asyncio.create_task(handle_admin_payment_deadline(order_id))
            
            
            
            # Mark order as completed
            update_order_status(order_id, "completed")
            
            # Log the action
            logger.info(f"Cash payment completed and order marked as completed: {order_id}")
            
            await callback_query.message.answer(
                f"✅ Ödəniş təsdiqləndi. Sifarişiniz tamamlandı.\n\n"
                f"Təşəkkür edirik!"
            )

            # Send review request to customer
            try:
                from notification_service import send_review_request_to_customer
                await send_review_request_to_customer(order_id)
                logger.info(f"Review request sent successfully for order {order_id}")
            except Exception as review_error:
                logger.error(f"Error sending review request: {review_error}", exc_info=True)

            
            # Return to customer menu after a short delay
            await asyncio.sleep(1)  # Wait 2 seconds to ensure messages are seen
            await show_customer_menu(callback_query.message)
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in cash_payment_completed: {e}", exc_info=True)
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()
            # Still show menu even if there's an error
            await show_customer_menu(callback_query.message)



    # customer_handler.py içine ekleyeceğimiz kod:

    @dp.message_handler(content_types=types.ContentType.PHOTO)
    async def handle_photo(message: types.Message):
        """Process uploaded photos (payment receipts, etc.)"""
        try:
            telegram_id = message.from_user.id
            
            # Get user context
            context = get_user_context(telegram_id)
            
            if not context or not context.get('action'):
                # No context requiring photo, ignore
                return
            
            action = context.get('action')
            
            if action == 'card_payment_receipt':
                order_id = context.get('order_id')
                
                if not order_id:
                    await message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
                    return
                
                # Get the highest quality photo
                photo = message.photo[-1]
                file_id = photo.file_id
                
                # Save receipt to database
                success = save_payment_receipt(order_id, file_id)
                
                if success:
                    # Clear user context
                    clear_user_context(telegram_id)
                    
                    # Mark order as completed
                    update_order_status(order_id, "completed")
                    
                    await message.answer(
                        "✅ Ödəniş qəbzi uğurla yükləndi!\n\n"
                        "Sifarişiniz tamamlandı. Təşəkkür edirik!",
                        reply_markup=types.ReplyKeyboardRemove()
                    )
                    
                    # Notify artisan
                    order = get_order_details(order_id)
                    if order:
                        artisan = get_artisan_by_id(order['artisan_id'])
                        if artisan and artisan.get('telegram_id'):
                            # Send text notification to artisan
                            await bot.send_message(
                                chat_id=artisan['telegram_id'],
                                text=f"💳 *Ödəniş bildirişi*\n\n"
                                    f"Sifariş #{order_id} üçün müştəri ödəniş etdi və qəbz göndərdi.\n"
                                    f"Ödəniş 24 saat ərzində hesabınıza köçürüləcək.",
                                parse_mode="Markdown"
                            )

                        from notification_service import send_review_request_to_customer
                        await send_review_request_to_customer(order_id)

                    await asyncio.sleep(2)  # Wait 2 seconds to ensure messages are seen
                    await show_customer_menu(message)

                else:
                    await message.answer(
                        "❌ Qəbz yüklənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                    )
            
            elif action == 'resend_payment_receipt':
                order_id = context.get('order_id')
                
                if not order_id:
                    await message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
                    return
                
                # Get the highest quality photo
                photo = message.photo[-1]
                file_id = photo.file_id
                
                # Save receipt to database
                success = save_payment_receipt(order_id, file_id)

                if success:
                    # Clear user context
                    clear_user_context(telegram_id)
                    
                    # Reset receipt verification status to pending
                    from db import update_receipt_verification_status
                    update_receipt_verification_status(order_id, False)
                    
                    await message.answer(
                        "✅ Ödəniş qəbzi uğurla yükləndi!\n\n"
                        "Qəbz yoxlanıldıqdan sonra sifarişiniz tamamlanacaq. Təşəkkür edirik!",
                        reply_markup=types.ReplyKeyboardRemove()
                    )

                    await asyncio.sleep(2)  # 2 saniyə gözləyin ki, mesajlar görünsün
                    await show_customer_menu(message)
                else:
                    await message.answer(
                        "❌ Qəbz yüklənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                    )

            elif action == 'customer_fine_receipt':
                # Get customer info
                customer = get_customer_by_telegram_id(telegram_id)
                if not customer:
                    await message.answer("❌ Müştəri məlumatları tapılmadı.")
                    return
                
                # Get the highest quality photo
                photo = message.photo[-1]
                file_id = photo.file_id
                
                # Save fine receipt for customer
                from db import save_customer_fine_receipt
                success = save_customer_fine_receipt(customer['id'], file_id)

                if success:
                    # Clear user context
                    clear_user_context(telegram_id)
                    
                    await message.answer(
                        "✅ Cərimə ödənişinin qəbzi uğurla yükləndi!\n\n"
                        "Qəbz yoxlanıldıqdan sonra hesabınız blokdan çıxarılacaq. "
                        "Bu, adətən 24 saat ərzində baş verir.",
                        reply_markup=types.ReplyKeyboardRemove()
                    )
                    
                    # Notify admins
                    try:
                        for admin_id in BOT_ADMINS:
                            await bot.send_photo(
                                chat_id=admin_id,
                                photo=file_id,
                                caption=f"💰 *Müştəri cərimə ödənişi*\n\n"
                                    f"Müştəri: {customer['name']} (ID: {customer['id']})\n\n"
                                    f"Zəhmət olmasa yoxlayın və təsdiqləyin.",
                                parse_mode="Markdown"
                            )
                    except Exception as admin_error:
                        logger.error(f"Error notifying admin: {admin_error}")
                else:
                    await message.answer(
                        "❌ Qəbz yüklənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                        )

        except Exception as e:
            logger.error(f"Error in handle_photo: {e}")
            # Log detailed error for debugging
            import traceback
            logger.error(traceback.format_exc())

    # customer_handler.py içindəki register_handlers funksiyasına əlavə edin

    # Debug əmri: sifariş məlumatlarını yoxlama
    @dp.message_handler(commands=['check_order'])
    async def debug_check_order(message: types.Message):
        """Debug command to check order details"""
        try:
            # Extract order ID from command
            command_parts = message.text.split()
            if len(command_parts) != 2:
                await message.answer("Doğru format: /check_order [order_id]")
                return
                
            try:
                order_id = int(command_parts[1])
            except ValueError:
                await message.answer("Sifariş ID rəqəm olmalıdır")
                return
                
            # Get order details
            order = get_order_details(order_id)
            
            if not order:
                await message.answer(f"Sifariş #{order_id} tapılmadı")
                return
                
            # Display order details
            details = (
                f"📋 *Sifariş #{order_id} detalları:*\n\n"
                f"Müştəri ID: {order['customer_id']}\n"
                f"Usta ID: {order['artisan_id']}\n"
                f"Xidmət: {order['service']}\n"
                f"Alt xidmət: {order.get('subservice', 'Təyin edilməyib')}\n"
                f"Tarix: {order['date_time']}\n"
                f"Status: {order['status']}\n"
                f"Qiymət: {order.get('price', 'Təyin edilməyib')}\n"
                f"Ödəniş üsulu: {order.get('payment_method', 'Təyin edilməyib')}\n"
                f"Ödəniş statusu: {order.get('payment_status', 'Təyin edilməyib')}\n"
            )
            
            await message.answer(details, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Error in debug_check_order: {e}")
            await message.answer(f"Xəta: {str(e)}")


    @dp.callback_query_handler(lambda c: c.data.startswith('cash_payment_made_'))
    async def cash_payment_made(callback_query: types.CallbackQuery):
        """Müşterinin nakit ödeme yaptığını bildirmesi"""
        try:
            # Extract order ID from callback data
            order_id = int(callback_query.data.split('_')[-1])
            
            # Get order details
            order = get_order_details(order_id)
            
            if not order:
                await callback_query.message.answer(
                    "❌ Sifariş tapılmadı. Silinmiş və ya ləğv edilmiş ola bilər."
                )
                await callback_query.answer()
                return
            
            # Notify artisan to confirm payment
            artisan = get_artisan_by_id(order['artisan_id'])
            if artisan and artisan.get('telegram_id'):
                # Create confirmation keyboard for artisan
                keyboard = InlineKeyboardMarkup(row_width=1)
                keyboard.add(
                    InlineKeyboardButton("✅ Ödənişi aldım", callback_data=f"artisan_confirm_cash_{order_id}"),
                    InlineKeyboardButton("❌ Ödəniş alınmadı", callback_data=f"artisan_deny_cash_{order_id}")
                )
                
                await bot.send_message(
                    chat_id=artisan['telegram_id'],
                    text=f"💵 *Nağd ödəniş bildirişi*\n\n"
                        f"Müştəri sifariş #{order_id} üçün nağd ödəniş etdiyini bildirdi.\n"
                        f"Məbləğ: {order.get('price', 0)} AZN\n\n"
                        f"Zəhmət olmasa, ödənişi aldığınızı təsdiqləyin:",
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
            
            await callback_query.message.answer(
                f"✅ Ödəniş bildirişi ustaya göndərildi.\n\n"
                f"Usta ödənişi aldığını təsdiq etdikdən sonra sizə bildiriş gələcək."
            )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in cash_payment_made: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()


    # Hem customer hem de artisan handler'a eklenebilir
    @dp.message_handler(commands=['debug_payment'])
    async def debug_payment_command(message: types.Message):
        """Debug command to check payment details for an order"""
        try:
            # Extract order ID from command
            command_parts = message.text.split()
            if len(command_parts) != 2:
                await message.answer("Doğru format: /debug_payment [order_id]")
                return
                
            try:
                order_id = int(command_parts[1])
            except ValueError:
                await message.answer("Sifariş ID rəqəm olmalıdır")
                return
                
            # Get payment details
            from db import debug_order_payment
            payment_details = debug_order_payment(order_id)
            
            if not payment_details:
                await message.answer(f"Sifariş #{order_id} üçün ödəniş məlumatları tapılmadı")
                return
                
            # Format payment details
            details = (
                f"🔍 *Sifariş #{order_id} ödəniş detalları:*\n\n"
                f"Ümumi məbləğ: {payment_details.get('amount', 'Yoxdur')} AZN\n"
                f"Komissiya: {payment_details.get('admin_fee', 'Yoxdur')} AZN\n"
                f"Ustaya qalan: {payment_details.get('artisan_amount', 'Yoxdur')} AZN\n"
                f"Ödəniş üsulu: {payment_details.get('payment_method', 'Yoxdur')}\n"
                f"Ödəniş statusu: {payment_details.get('payment_status', 'Yoxdur')}\n"
                f"Çek ID: {payment_details.get('receipt_file_id', 'Yoxdur')}\n"
                f"Çek yüklənmə tarixi: {payment_details.get('receipt_uploaded_at', 'Yoxdur')}\n"
                f"Admin ödənişi tamamlandı: {'Bəli' if payment_details.get('admin_payment_completed') else 'Xeyr'}\n"
                f"Yaradılma tarixi: {payment_details.get('created_at', 'Yoxdur')}\n"
                f"Yenilənmə tarixi: {payment_details.get('updated_at', 'Yoxdur')}"
            )
            
            await message.answer(details, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Error in debug_payment_command: {e}")
            await message.answer(f"Xəta: {str(e)}")


    @dp.callback_query_handler(lambda c: c.data.startswith('retry_cash_payment_'))
    async def retry_cash_payment(callback_query: types.CallbackQuery):
        """Müşterinin nakit ödemeyi yeniden denemesi"""
        try:
            # Extract order ID from callback data
            order_id = int(callback_query.data.split('_')[-1])
            
            # Get order details
            order = get_order_details(order_id)
            
            if not order:
                await callback_query.message.answer(
                    "❌ Sifariş tapılmadı. Silinmiş və ya ləğv edilmiş ola bilər."
                )
                await callback_query.answer()
                return
            
            # Create payment confirmation keyboard
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton(
                "✅ Nağd ödənişi etdim", 
                callback_data=f"cash_payment_made_{order_id}"
            ))
            
            # Send cash payment notification to customer
            await callback_query.message.answer(
                f"💵 *Nağd ödəniş*\n\n"
                f"Sifariş: #{order_id}\n"
                f"Məbləğ: {order.get('price', 0)} AZN\n\n"
                f"Zəhmət olmasa, ödənişi ustaya nağd şəkildə edin və "
                f"ödənişi etdikdən sonra aşağıdakı düyməni basın.",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in retry_cash_payment: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()


    # Nakit ödeme handler'ları
    dp.register_callback_query_handler(
        cash_payment_made,
        lambda c: c.data.startswith('cash_payment_made_')
    )
    
    dp.register_callback_query_handler(
        retry_cash_payment,
        lambda c: c.data.startswith('retry_cash_payment_')
    )



    @dp.callback_query_handler(lambda c: c.data.startswith('resend_receipt_'))
    async def resend_receipt(callback_query: types.CallbackQuery):
        """Handle re-uploading receipt after verification failure"""
        try:
            # Extract order ID from callback data
            order_id = int(callback_query.data.split('_')[-1])
            
            # Set context for receipt upload
            telegram_id = callback_query.from_user.id
            set_user_context(telegram_id, {
                "action": "resend_payment_receipt",
                "order_id": order_id
            })
            
            # Ask for receipt
            await callback_query.message.answer(
                "📸 Zəhmət olmasa, ödəniş qəbzinin şəklini göndərin.\n\n"
                "Bu, ödənişin təsdiqlənməsi üçün lazımdır. Şəkil aydın və oxunaqlı olmalıdır."
            )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in resend_receipt: {e}", exc_info=True)
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()

    @dp.message_handler(commands=['pay_customer_fine'])
    async def pay_customer_fine_command(message: types.Message):
        """Handle the pay_customer_fine command for blocked customers"""
        try:
            telegram_id = message.from_user.id
            customer = get_customer_by_telegram_id(telegram_id)
            
            if not customer:
                await message.answer(
                    "❌ Siz hələ müştəri kimi qeydiyyatdan keçməmisiniz."
                )
                return
                
            # Check if customer is blocked
            is_blocked, reason, amount, block_until = get_customer_blocked_status(customer['id'])
            
            if not is_blocked:
                await message.answer(
                    "✅ Sizin hesabınız bloklanmayıb. Bütün xidmətlərdən istifadə edə bilərsiniz."
                )
                return
                
            # Show payment instructions
            await message.answer(
                f"💰 *Cərimə ödənişi*\n\n"
                f"Hesabınız aşağıdakı səbəbə görə bloklanıb:\n"
                f"*Səbəb:* {reason}\n\n"
                f"Bloku açmaq üçün {amount} AZN ödəniş etməlisiniz.\n\n"
                f"*Ödəniş təlimatları:*\n"
                f"1. Bu karta ödəniş edin: {ADMIN_CARD_NUMBER} ({ADMIN_CARD_HOLDER})\n"
                f"2. Ödəniş qəbzini saxlayın (şəkil çəkin)\n"
                f"3. Qəbzi göndərmək üçün aşağıdakı düyməni basın\n\n"
                f"⚠️ Qeyd: Ödəniş qəbzi yoxlanıldıqdan sonra hesabınız blokdan çıxarılacaq.",
                parse_mode="Markdown"
            )
            
            # Add button to send receipt
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton(
                "📸 Ödəniş qəbzini göndər", callback_data="send_customer_fine_receipt"
            ))
            
            await message.answer(
                "Ödənişi tamamladıqdan sonra, qəbzi göndərmək üçün bu düyməni basın:",
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"Error in pay_customer_fine_command: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            

    @dp.callback_query_handler(lambda c: c.data == "send_customer_fine_receipt")
    async def send_customer_fine_receipt(callback_query: types.CallbackQuery):
        """Handle customer fine receipt upload request"""
        try:
            telegram_id = callback_query.from_user.id
            
            # Set context for receipt upload
            context_data = {
                "action": "customer_fine_receipt"
            }
            
            set_user_context(telegram_id, context_data)
            
            await callback_query.message.answer(
                "📸 Zəhmət olmasa, ödəniş qəbzinin şəklini göndərin.\n\n"
                "Şəkil aydın və oxunaqlı olmalıdır. Ödəniş məbləği, tarix və kart məlumatları görünməlidir."
            )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in send_customer_fine_receipt: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()

    # Add these handlers to customer_handler.py in the register_handlers function

    @dp.callback_query_handler(lambda c: c.data.startswith('rate_'))
    async def process_rating(callback_query: types.CallbackQuery, state: FSMContext):
        """Process rating selection and ask for comment"""
        try:
            # Extract order ID and rating from callback data
            parts = callback_query.data.split('_')
            order_id = int(parts[1])
            rating = int(parts[2])
            
            # Store rating in state
            async with state.proxy() as data:
                data['order_id'] = order_id
                data['rating'] = rating
            
            # Ask for comment
            await callback_query.message.answer(
                f"Seçdiyiniz qiymətləndirmə: {'⭐' * rating}\n\n"
                f"İstəsəniz, əlavə şərh də yaza bilərsiniz. Əgər şərh yazmaq istəmirsinizsə, "
                f"'Şərh yoxdur' yazın."
            )
            
            # Set state to wait for comment
            await OrderRatingState.waiting_for_comment.set()
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in process_rating: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()
            await state.finish()

    @dp.message_handler(state=OrderRatingState.waiting_for_comment)
    async def process_rating_comment(message: types.Message, state: FSMContext):
        """Process rating comment and save review"""
        try:
            # Get comment text
            comment = message.text.strip()
            
            # Skip storing comment if it's "No comment"
            if comment.lower() in ["şərh yoxdur", "yoxdur", "no comment", "-"]:
                comment = None
            
            # Get data from state
            data = await state.get_data()
            order_id = data.get('order_id')
            rating = data.get('rating')
            
            if not order_id or not rating:
                await message.answer("❌ Qiymətləndirmə məlumatları tapılmadı.")
                await state.finish()
                await show_customer_menu(message)
                return
            
            # Get order details
            order = get_order_details(order_id)
            if not order:
                await message.answer(f"❌ Sifariş #{order_id} tapılmadı.")
                await state.finish()
                await show_customer_menu(message)
                return
            
            # Add review to database
            success = add_review(
                order_id=order_id,
                customer_id=order['customer_id'],
                artisan_id=order['artisan_id'],
                rating=rating,
                comment=comment
            )
            
            if success:
                # Thank the customer
                await message.answer(
                    f"✅ Təşəkkür edirik! Rəyiniz uğurla qeydə alındı.\n\n"
                    f"Ustanı {'⭐' * rating} ulduzla qiymətləndirdiniz."
                )
                
                # Notify artisan about the review
                artisan_telegram_id = get_artisan_by_id(order['artisan_id']).get('telegram_id')
                if artisan_telegram_id:
                    await bot.send_message(
                        chat_id=artisan_telegram_id,
                        text=f"⭐ *Yeni rəy aldınız!*\n\n"
                            f"Sifariş #{order_id} üçün müştəridən {'⭐' * rating} "
                            f"({rating}/5) qiymətləndirmə aldınız.\n"
                            f"{f'💬 Şərh: {comment}' if comment else ''}",
                        parse_mode="Markdown"
                    )
            else:
                await message.answer(
                    "❌ Rəyiniz qeydə alınarkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
            
            # Clear state and return to menu
            await state.finish()
            await show_customer_menu(message)
            
        except Exception as e:
            logger.error(f"Error in process_rating_comment: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_customer_menu(message)

    @dp.callback_query_handler(lambda c: c.data.startswith('skip_rating_'))
    async def skip_rating(callback_query: types.CallbackQuery, state: FSMContext):
        """Handle when user skips rating"""
        try:
            await callback_query.message.answer(
                "✅ Qiymətləndirməni keçdiniz. Təşəkkür edirik!"
            )
            
            await callback_query.answer()
            await state.finish()
            
            # Return to customer menu
            await show_customer_menu(callback_query.message)
            
        except Exception as e:
            logger.error(f"Error in skip_rating: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()
            await state.finish()
            await show_customer_menu(callback_query.message)

    @dp.callback_query_handler(lambda c: c.data == "pay_customer_fine")
    async def pay_customer_fine_callback(callback_query: types.CallbackQuery):
        """Handle pay fine button click"""
        try:
            # Buton tıklamasını onaylayın
            await callback_query.answer()
            
            # Kullanıcı bilgilerini alın
            telegram_id = callback_query.from_user.id
            customer = get_customer_by_telegram_id(telegram_id)
            
            if not customer:
                await callback_query.message.answer(
                    "❌ Siz hələ müştəri kimi qeydiyyatdan keçməmisiniz."
                )
                return
                
            # Blok durumunu kontrol edin
            is_blocked, reason, amount, block_until = get_customer_blocked_status(customer['id'])
            
            if not is_blocked:
                await callback_query.message.answer(
                    "✅ Sizin hesabınız bloklanmayıb. Bütün xidmətlərdən istifadə edə bilərsiniz."
                )
                return
                
            # Ödeme talimatları mesajını gösterin
            await callback_query.message.answer(
                f"💰 *Cərimə ödənişi*\n\n"
                f"Hesabınız aşağıdakı səbəbə görə bloklanıb:\n"
                f"*Səbəb:* {reason}\n\n"
                f"Bloku açmaq üçün {amount} AZN ödəniş etməlisiniz.\n\n"
                f"*Ödəniş təlimatları:*\n"
                f"1. Bu karta ödəniş edin: {ADMIN_CARD_NUMBER} ({ADMIN_CARD_HOLDER})\n"
                f"2. Ödəniş qəbzini saxlayın (şəkil çəkin)\n"
                f"3. Qəbzi göndərmək üçün aşağıdakı düyməni basın\n\n"
                f"⚠️ Qeyd: Ödəniş qəbzi yoxlanıldıqdan sonra hesabınız blokdan çıxarılacaq.",
                parse_mode="Markdown"
            )
            
            # Makbuz gönderme düğmesini ekleyin
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton(
                "📸 Ödəniş qəbzini göndər", callback_data="send_customer_fine_receipt"
            ))
            
            await callback_query.message.answer(
                "Ödənişi tamamladıqdan sonra, qəbzi göndərmək üçün bu düyməni basın:",
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"Error in pay_customer_fine_callback: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )

    # Əmr bələdçisi funksiyasını əlavə et
    dp.register_message_handler(show_command_guide, lambda message: message.text == "ℹ️ Əmr bələdçisi")