# artisan_handler.py

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))  # Ana qovluğu əlavə et
from dispatcher import bot, dp
from db import *
from db import set_order_price as db_set_order_price
from datetime_helpers import format_datetime
from geo_helpers import calculate_distance, format_distance, get_location_name
import logging
import re
import asyncio
from config import *
from notification_service import *


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define states for artisan registration
class ArtisanRegistrationStates(StatesGroup):
    confirming_name = State()
    entering_name = State()
    entering_phone = State()
    entering_city = State()
    selecting_service = State()
    sharing_location = State()
    confirming_registration = State()

# Define states for managing orders
class ArtisanOrderStates(StatesGroup):
    viewing_orders = State()
    managing_order = State()
    completing_order = State()
    rating_request = State()
    entering_order_price = State()

# Define states for profile management
class ArtisanProfileStates(StatesGroup):
    viewing_profile = State()
    updating_name = State()
    updating_phone = State()
    updating_city = State()
    updating_service = State()
    updating_location = State()
    setting_price_ranges = State()
    setting_subservice_price = State()
    entering_card_number = State()  # Add new state for card number
    entering_card_holder = State()  # Add new state for card holder


class AdminPaymentStates(StatesGroup):
    waiting_for_receipt = State()

# Define payment receipt state class
class PaymentReceiptState(StatesGroup):
    waiting_for_receipt = State()

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
            "Sifarişlər, ödənişlər və rəylər sistem tərəfindən idarə olunur."
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
# Register artisan handlers
def register_handlers(dp):
    # Handler for when user selects "Artisan" role
    @dp.message_handler(lambda message: message.text == "🛠 Ustayam")
    async def handle_artisan(message: types.Message, state: FSMContext):
        """Handle when user selects the artisan role"""
        try:
            # Check if artisan is already registered
            telegram_id = message.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if artisan_id:
                # Check if artisan is blocked
                is_blocked, reason, required_payment = get_artisan_blocked_status(artisan_id)
                
                if is_blocked:
                    # Show blocked message with reason and payment requirements
                    await message.answer(
                        f"⛔ *Hesabınız bloklanıb*\n\n"
                        f"Səbəb: {reason}\n\n"
                        f"Bloku açmaq üçün {required_payment} AZN ödəniş etməlisiniz.\n"
                        f"Ödəniş etmək üçün: /pay_fine komandası ilə ətraflı məlumat ala bilərsiniz.",
                        parse_mode="Markdown"
                    )
                    return
        
                # Artisan already registered and not blocked, show main menu
                await show_artisan_menu(message)
            else:
                # Start registration process
                await show_artisan_agreement(message, state)
                
            
        except Exception as e:
            logger.error(f"Error in handle_artisan: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_role_selection(message)
    

    async def show_artisan_agreement(message: types.Message, state: FSMContext):
        """Show agreement for new artisans"""
        try:
            # First show guide
            guide_text = (
                " - "
            )
            
            await message.answer(guide_text, parse_mode="Markdown")
            
            # Then show agreement
            agreement_text = (
                "📜 *Usta Müqaviləsi*\n\n"
                "📌 Qeyd: Bu razılaşmanı qəbul etməklə, aşağıdakı şərtləri təsdiq etmiş olursunuz:\n\n"
                "1. Sifariş Qəbulu və Xidmət Öhdəliyi:\n"
                "• Usta sifarişi qəbul etdikdən sonra, təyin olunan ünvana və vaxtda getmək və göstəriləcək xidməti keyfiyyətlə yerinə yetirmək öhdəliyini daşıyır.\n"
                "2. Qiymət Təyini və Müştəri ilə Razılaşma:\n"
                "• Sifariş qəbul edildikdən sonra qiyməti siz təyin edirsiniz. Müştəri qiyməti qəbul etdikdən sonra razılaşma qüvvəyə minir.\n"
                "3. Komissiya Qaydasının Qəbulu:\n"
                "• Hər tamamlanmış 0-50 AZN məbləğindəki sifariş üçün 12%, 51-200 AZN məbləğindəki sifariş üçün 16%, 200 AZN-dən yüksək məbləğlərdə sifarişlər üçün 20% komissiya ödənilir.\n"
                "4. Ödəniş və Komissiya Prosesi:\n"
                "• Müştəri ödənişi nağd və ya kartla edə bilər.\n"
                "• Siz ödənişi aldıqdan sonra komissiyanı adminə 24 saat ərzində köçürməlisiniz.\n"
                "• Komissiya ödənişi gecikərsə, 15% cərimə əlavə olunur və 18 saat ərzində ödənilməzsə hesabınız bloklanır.\n"
                "• Hesabınızın bloku yalnız cərimə ödənişi menyusundan müəyyən olunmuş komissiya həcmini 50% cərimə məbləği ilə birlikdə ödənildikdə açılır.\n"
                "5. Bloklanma halları:\n"
                "• Sifariş yerinə getmədikdə: 30 AZN cərimə ilə bloklanırsınız\n"
                "• Komissiya qəbzi saxta və ya uyğun deyilsə, bloklanma və əlavə cərimə tətbiq olunur.\n"
                "6. Təsdiqlər və Məsuliyyət:\n"
                "• Komissiya üçün təqdim etdiyiniz qəbz admin tərəfindən yoxlanır.\n"
                "• Əgər təsdiqlənməzsə, 18 saat ərzində yeni və düzgün qəbz göndərilməlidir.\n\n"
                "• Botun qaydalarını pozduqda hesabınız bloklanacaq\n\n"
                "Bu şərtləri qəbul edib davam etmək istəyirsinizsə,  - ✅ Qəbul edirəm - düyməsini klikləyin."
                )
            
            # Create agreement buttons
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("✅ Qəbul edirəm", callback_data="accept_artisan_agreement"),
                InlineKeyboardButton("❌ Qəbul etmirəm", callback_data="decline_artisan_agreement")
            )
            
            await message.answer(agreement_text, reply_markup=keyboard, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Error in show_artisan_agreement: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await show_role_selection(message)

    # Usta müqaviləsi qəbul edilmə prosesini düzəltmə
    @dp.callback_query_handler(lambda c: c.data == "accept_artisan_agreement")
    async def accept_artisan_agreement(callback_query: types.CallbackQuery, state: FSMContext):
        """Handle artisan agreement acceptance"""
        try:
            await callback_query.message.answer(
                "✅ Təşəkkür edirik! Şərtləri qəbul etdiniz."
            )
            
            # Qəbul etdikdən sonra qeydiyyata başlamaq üçün düymə göstər
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                InlineKeyboardButton("✅ Qeydiyyatı tamamla", callback_data="continue_artisan_registration")
            )
            
            await callback_query.message.answer(
                "Qeydiyyatı tamamlamaq üçün aşağıdakı düyməni klikləyin:",
                reply_markup=keyboard
            )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in accept_artisan_agreement: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()

    # Qeydiyyata davam etmə prosesi üçün yeni handler
    @dp.callback_query_handler(lambda c: c.data == "continue_artisan_registration")
    async def continue_artisan_registration(callback_query: types.CallbackQuery, state: FSMContext):
        """Continue artisan registration after confirmation"""
        try:
            # Qeydiyyat prosesinə keçid
            await start_registration(callback_query.message, state)
            await callback_query.answer()
        except Exception as e:
            logger.error(f"Error in continue_artisan_registration: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_role_selection(callback_query.message)

    @dp.callback_query_handler(lambda c: c.data == "decline_artisan_agreement")
    async def decline_artisan_agreement(callback_query: types.CallbackQuery, state: FSMContext):
        """Handle artisan agreement decline"""
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
            logger.error(f"Error in decline_artisan_agreement: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()

        

    async def start_registration(message: types.Message, state: FSMContext):
        """Start the artisan registration process"""
        try:
            await message.answer(
                "👋 Xoş gəlmisiniz! Usta qeydiyyatı üçün zəhmət olmasa, məlumatlarınızı təqdim edin."
            )
            
            # Pre-fill name from Telegram profile
            full_name = message.from_user.full_name
            
            # Create inline keyboard for name confirmation
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                InlineKeyboardButton("✅ Bəli, adımı təsdiqləyirəm", callback_data="confirm_artisan_name"),
                InlineKeyboardButton("🖊 Xeyr, başqa ad daxil etmək istəyirəm", callback_data="change_artisan_name")
            )
            
            await message.answer(
                f"👤 Telegram hesabınızda göstərilən adınız: *{full_name}*\n\n"
                "Bu addan istifadə etmək istəyirsiniz?",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            # Store suggested name in state
            async with state.proxy() as data:
                data['suggested_name'] = full_name
            
            await ArtisanRegistrationStates.confirming_name.set()
            
        except Exception as e:
            logger.error(f"Error in start_registration: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_role_selection(message)
    
    @dp.callback_query_handler(
        lambda c: c.data in ["confirm_artisan_name", "change_artisan_name"],
        state=ArtisanRegistrationStates.confirming_name
    )
    async def process_name_confirmation(callback_query: types.CallbackQuery, state: FSMContext):
        """Process artisan name confirmation"""
        try:
            if callback_query.data == "confirm_artisan_name":
                # User confirmed the suggested name
                data = await state.get_data()
                suggested_name = data.get('suggested_name')
                
                # Store name in state
                async with state.proxy() as data:
                    data['name'] = suggested_name
                
                # Proceed to phone input
                await ask_for_phone(callback_query.message)
                await ArtisanRegistrationStates.entering_phone.set()
            else:
                # User wants to provide a different name
                await callback_query.message.answer(
                    "👤 Zəhmət olmasa, adınızı daxil edin:"
                )
                await ArtisanRegistrationStates.entering_name.set()
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in process_name_confirmation: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_role_selection(callback_query.message)

    @dp.message_handler(state=ArtisanRegistrationStates.entering_name)
    async def process_name_input(message: types.Message, state: FSMContext):
        """Process artisan name input"""
        try:
            # Validate and store name
            name = message.text.strip()
            
            if len(name) < 2 or len(name) > 50:
                await message.answer(
                    "❌ Ad ən azı 2, ən çoxu 50 simvol olmalıdır. Zəhmət olmasa, yenidən daxil edin:"
                )
                return
            
            # Store name in state
            async with state.proxy() as data:
                data['name'] = name
            
            # Proceed to phone input
            await ask_for_phone(message)
            await ArtisanRegistrationStates.entering_phone.set()
            
        except Exception as e:
            logger.error(f"Error in process_name_input: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_role_selection(message)
            
    async def ask_for_phone(message: types.Message):
        """Ask user for phone number"""
        # Create keyboard with main menu return option
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton("🏠 Əsas menyuya qayıt"))
        
        await message.answer(
            "📞 Zəhmət olmasa, əlaqə nömrənizi daxil edin (məsələn: +994501234567):",
            reply_markup=keyboard
        )
    
    @dp.message_handler(state=ArtisanRegistrationStates.entering_phone)
    async def process_phone(message: types.Message, state: FSMContext):
        """Process artisan phone number input"""
        try:
            # Check if user wants to return to main menu
            if message.text == "🏠 Əsas menyuya qayıt":
                await state.finish()
                await show_role_selection(message)
                return
            
            # Get user input and validate phone format
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
            
            # Check if phone number is already registered
            if check_artisan_exists(phone=phone):
                await message.answer(
                    "❌ Bu telefon nömrəsi artıq qeydiyyatdan keçib. Zəhmət olmasa, başqa nömrə daxil edin."
                )
                return
            
            # Store phone in state
            async with state.proxy() as data:
                data['phone'] = phone
            
            # Proceed to city input
            await message.answer(
                "🏙 Şəhərinizi daxil edin (məsələn: Bakı):"
            )
            
            await ArtisanRegistrationStates.entering_city.set()
            
        except Exception as e:
            logger.error(f"Error in process_phone: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_role_selection(message)
    
    @dp.message_handler(state=ArtisanRegistrationStates.entering_city)
    async def process_city(message: types.Message, state: FSMContext):
        """Process artisan city input"""
        try:
            # Check if user wants to return to main menu
            if message.text == "🏠 Əsas menyuya qayıt":
                await state.finish()
                await show_role_selection(message)
                return
            
            # Validate and store city
            city = message.text.strip()
            
            if len(city) < 2 or len(city) > 50:
                await message.answer(
                    "❌ Şəhər adı ən azı 2, ən çoxu 50 simvol olmalıdır. Zəhmət olmasa, yenidən daxil edin:"
                )
                return
            
            # Store city in state
            async with state.proxy() as data:
                data['city'] = city
            
            # Get available services
            services = get_services()
            
            # Create inline keyboard with service buttons
            keyboard = InlineKeyboardMarkup(row_width=2)
            
            for service in services:
                keyboard.add(InlineKeyboardButton(service, callback_data=f"artisan_service_{service}"))
            
            await message.answer(
                "🛠 Təqdim etdiyiniz xidmət növünü seçin:",
                reply_markup=keyboard
            )
            
            await ArtisanRegistrationStates.selecting_service.set()
            
        except Exception as e:
            logger.error(f"Error in process_city: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_role_selection(message)
    
    @dp.callback_query_handler(
        lambda c: c.data.startswith('artisan_service_'),
        state=ArtisanRegistrationStates.selecting_service
    )
    async def process_service_selection(callback_query: types.CallbackQuery, state: FSMContext):
        """Process service selection for artisan registration"""
        try:
            # Extract service from callback data
            selected_service = callback_query.data.split('_', 2)[2]
            
            # Store service in state
            async with state.proxy() as data:
                data['service'] = selected_service
            
            # Create keyboard with location button and help text for GPS
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(KeyboardButton("📍 Yerimi paylaş", request_location=True))
            keyboard.add(KeyboardButton("🏠 Əsas menyuya qayıt"))
            
            await callback_query.message.answer(
                f"Seçdiyiniz xidmət: *{selected_service}*\n\n"
                "📍 İndi zəhmət olmasa, xidmət göstərdiyiniz ərazini paylaşın.\n\n"
                "ℹ️ *Ətraflı məlumat:*\n"
                "• Yerləşdiyiniz məkanı dəqiq müəyyən etmək üçün telefonunuzda GPS xidmətinin aktiv olduğundan əmin olun.\n"
                "• 'Yerimi paylaş' düyməsinə basdıqdan sonra sizə gələn sorğunu təsdiqləyin.\n"
                "• Bu lokasiya əsas xidmət göstərdiyiniz ərazi kimi qeyd olunacaq və müştərilər axtarış edərkən bu əraziyə uyğun olaraq sizi tapacaq.",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            await callback_query.answer()
            await ArtisanRegistrationStates.sharing_location.set()
            
        except Exception as e:
            logger.error(f"Error in process_service_selection: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_role_selection(callback_query.message)
    
    @dp.message_handler(
        content_types=types.ContentType.LOCATION,
        state=ArtisanRegistrationStates.sharing_location
    )
    async def process_location(message: types.Message, state: FSMContext):
        """Process location sharing for artisan registration"""
        try:
            # Store location in state
            latitude = message.location.latitude
            longitude = message.location.longitude
            
            # Try to get location name (city/district) based on coordinates
            location_name = await get_location_name(latitude, longitude)
            city = location_name if location_name else "Bakı"  # Default if geocoding fails
            
            async with state.proxy() as data:
                data['latitude'] = latitude
                data['longitude'] = longitude
                data['location_name'] = location_name
                
                # If no city was provided earlier, use the one from location
                if not data.get('city'):
                    data['city'] = city
                
                # Create summary for confirmation
                name = data['name']
                phone = data['phone']
                city = data['city']
                service = data['service']
                
                location_display = location_name if location_name else "Paylaşılan məkan"
                
                confirmation_text = (
                    "📋 *Qeydiyyat məlumatları:*\n\n"
                    f"👤 *Ad:* {name}\n"
                    f"📞 *Telefon:* {phone}\n"
                    f"🏙 *Şəhər:* {city}\n"
                    f"🛠 *Xidmət:* {service}\n"
                    f"📍 *Yer:* {location_display}\n\n"
                    f"Qeydiyyatı tamamlamaq üçün bu məlumatları təsdiqləyin.\n\n"
                    f"ℹ️ Qeydiyyatı tamamladıqdan sonra, xidmət növünüzə uyğun alt xidmətləri və qiymət aralıqlarını təyin edə biləcəksiniz."
                )
            
            # Create confirmation keyboard
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("✅ Təsdiqlə", callback_data="confirm_artisan_registration"),
                InlineKeyboardButton("❌ Ləğv et", callback_data="cancel_artisan_registration")
            )
            
            await message.answer(
                confirmation_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            await ArtisanRegistrationStates.confirming_registration.set()
            
        except Exception as e:
            logger.error(f"Error in process_location: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.\n\n"
                "Konum paylaşmada problem yaşanırsa:\n"
                "1. Telefonunuzun ayarlarından GPS/lokasiya xidmətini aktiv edin\n"
                "2. Telegram tətbiqinə konum icazəsi verdiyinizdən əmin olun\n"
                "3. Yenidən cəhd edin"
            )
            await state.finish()
            await show_role_selection(message)
            
            
    @dp.callback_query_handler(
    lambda c: c.data == "confirm_artisan_registration",
    state=ArtisanRegistrationStates.confirming_registration
    )
    async def confirm_registration(callback_query: types.CallbackQuery, state: FSMContext):
        """Confirm artisan registration"""
        try:
            # Get all registration data from state
            data = await state.get_data()
            name = data['name']
            phone = data['phone']
            city = data['city']
            service = data['service']
            latitude = data.get('latitude')
            longitude = data.get('longitude')
            location_name = data.get('location_name', city)
            
            # Default values for address and card info
            default_card_number = ''  # Empty string, not NULL
            default_card_holder = name  # Use artisan name as default
            default_address = city  # Use city as default address
            
            # Register artisan in database
            telegram_id = callback_query.from_user.id
            
            # First, clean up state
            await state.finish()
            
            # Check if already registered with this telegram_id
            existing_artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if existing_artisan_id:
                # If already registered, use existing ID
                artisan_id = existing_artisan_id
                
                # Update profile info
                update_artisan_profile(artisan_id, {
                    'name': name,
                    'phone': phone,
                    'city': city,
                    'service': service,
                    'location': location_name,
                    'profile_complete': True
                })
                
                # Add default card info (to avoid nulls)
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE artisans 
                    SET payment_card_number = %s, 
                        payment_card_holder = %s,
                        address = %s,
                        profile_complete = TRUE
                    WHERE id = %s
                    """,
                    (default_card_number, default_card_holder, default_address, artisan_id)
                )
                conn.commit()
                conn.close()
                
                # Update location info
                if latitude and longitude:
                    update_artisan_location(
                        artisan_id=artisan_id,
                        latitude=latitude,
                        longitude=longitude,
                        location_name=location_name
                    )
            else:
                # Create new registration
                artisan_id = get_or_create_artisan(
                    telegram_id=telegram_id,
                    name=name,
                    phone=phone,
                    service=service,
                    location=location_name,
                    city=city,
                    latitude=latitude,
                    longitude=longitude
                )
                
                # Update additional info
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE artisans 
                    SET payment_card_number = %s, 
                        payment_card_holder = %s,
                        address = %s,
                        profile_complete = TRUE
                    WHERE id = %s
                    """,
                    (default_card_number, default_card_holder, default_address, artisan_id)
                )
                conn.commit()
                conn.close()
            
            if artisan_id:
                try:
                    set_user_context(telegram_id, {"is_initial_registration": "true"})
                except Exception as e:
                    logger.error(f"Error setting initial context: {e}")
                
                # Show welcome message
                await callback_query.message.answer(
                    "✅ *Qeydiyyatınız uğurla tamamlandı!*\n\n"
                    "Siz artıq rəsmi olaraq usta hesabınızı yaratdınız. İndi xidmət növünüzə uyğun "
                    "alt xidmətləri və qiymət aralıqlarını təyin etməlisiniz.",
                    parse_mode="Markdown",
                    reply_markup=types.ReplyKeyboardRemove()
                )
                
                # IMPORTANT CHANGE: Directly prompt to set up price ranges immediately
                # Get artisan service and its subservices
                artisan = get_artisan_by_id(artisan_id)
                service = artisan['service']
                subservices = get_subservices(service)
                
                if subservices:
                    # Create keyboard with subservice options
                    keyboard = InlineKeyboardMarkup(row_width=1)
                    
                    for subservice in subservices:
                        keyboard.add(InlineKeyboardButton(
                            f"🔸 {subservice}", 
                            callback_data=f"set_price_range_{subservice}"
                        ))
                    
                    await callback_query.message.answer(
                        "💰 *Qiymət aralıqlarını təyin edin*\n\n"
                        "Xidmət növünüzə uyğun qiymət aralıqlarını təyin etmək üçün "
                        "zəhmət olmasa, aşağıdakı alt xidmətlərdən birini seçin:",
                        reply_markup=keyboard,
                        parse_mode="Markdown"
                    )
                    
                    await ArtisanProfileStates.setting_price_ranges.set()
                else:
                    await callback_query.message.answer(
                        "❌ Xidmət növünüz üçün alt xidmətlər tapılmadı. Zəhmət olmasa, administratorla əlaqə saxlayın."
                    )
                    
                    # Show artisan menu as fallback
                    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
                    keyboard.add(KeyboardButton("📋 Aktiv sifarişlər"))
                    keyboard.add(KeyboardButton("⭐ Rəylər"), KeyboardButton("📊 Statistika"))
                    keyboard.add(KeyboardButton("💰 Qiymət ayarları"), KeyboardButton("⚙️ Profil ayarları"))
                    keyboard.add(KeyboardButton("🔄 Rol seçiminə qayıt"))
                    
                    await callback_query.message.answer(
                        "👷‍♂️ *Usta Paneli*\n\n"
                        "Aşağıdakı əməliyyatlardan birini seçin:",
                        reply_markup=keyboard,
                        parse_mode="Markdown"
                    )
            else:
                await callback_query.message.answer(
                    "❌ Qeydiyyat zamanı xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
                await show_role_selection(callback_query.message)
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in confirm_registration: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_role_selection(callback_query.message)
    
    @dp.callback_query_handler(
        lambda c: c.data == "cancel_artisan_registration",
        state=ArtisanRegistrationStates.confirming_registration
    )
    async def cancel_registration(callback_query: types.CallbackQuery, state: FSMContext):
        """Cancel artisan registration"""
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
            logger.error(f"Error in cancel_registration: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_role_selection(callback_query.message)
    

    async def show_artisan_menu(message: types.Message):
        """Show the main artisan menu"""
        try:
            # Get artisan ID to check registration
            telegram_id = message.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if not artisan_id:
                # If not registered, show role selection menu
                await show_role_selection(message)
                return
                    
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(KeyboardButton("📋 Aktiv sifarişlər"))
            keyboard.add(KeyboardButton("⭐ Rəylər"), KeyboardButton("📊 Statistika"))
            keyboard.add(KeyboardButton("💰 Qiymət ayarları"), KeyboardButton("⚙️ Profil ayarları"))
            keyboard.add(KeyboardButton("ℹ️ Əmr bələdçisi"))
            keyboard.add(KeyboardButton("🔄 Rol seçiminə qayıt"))
            
            await message.answer(
                "👷‍♂️ *Usta Paneli*\n\n"
                "Aşağıdakı əməliyyatlardan birini seçin:",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error in show_artisan_menu: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
    
    # Function to show the role selection
    async def show_role_selection(message: types.Message):
        """Show role selection menu"""
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(KeyboardButton("👤 Müştəriyəm"), KeyboardButton("🛠 Ustayam"))
        
        await message.answer(
            "Xoş gəldiniz! Zəhmət olmasa, rolunuzu seçin:",
            reply_markup=keyboard
        )
    
    # Handler for "Active Orders" button
    @dp.message_handler(lambda message: message.text == "📋 Aktiv sifarişlər")
    async def view_active_orders(message: types.Message):
        """Show active orders for the artisan"""
        try:
            # Get artisan ID
            telegram_id = message.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if not artisan_id:
                await message.answer(
                    "❌ Siz hələ usta kimi qeydiyyatdan keçməmisiniz."
                )
                return
            
            # Check if artisan is blocked
            is_blocked, reason, amount = get_artisan_blocked_status(artisan_id)
            if is_blocked:
                await message.answer(
                    f"⛔ Hesabınız bloklanıb. Sifarişlərinizi görmək üçün əvvəlcə bloku açın.\n"
                    f"Səbəb: {reason}\n"
                    f"Ödəniş məbləği: {amount} AZN\n"
                    f"Ödəniş etmək üçün: /pay_fine"
                )
                return
            
            # Get active orders
            orders = get_artisan_active_orders(artisan_id)
            
            if not orders:
                await message.answer(
                    "📭 Hal-hazırda heç bir aktiv sifarişiniz yoxdur."
                )
                return
            
            await message.answer(
                f"📋 *Aktiv sifarişlər ({len(orders)}):*",
                parse_mode="Markdown"
            )
            
            # Display each order
            for order in orders:
                try:
                    # Extract order details based on type (tuple or dict)
                    if isinstance(order, dict):
                        order_id = order.get('id')
                        customer_id = order.get('customer_id')
                        service = order.get('service')
                        subservice = order.get('subservice', '')
                        date_time = order.get('date_time')
                        note = order.get('note')
                        customer_name = order.get('customer_name')
                        customer_phone = order.get('customer_phone')
                        status = order.get('status', 'pending')
                    else:
                        # If it's a tuple (old implementation)
                        order_id = order[0]
                        customer_id = order[1]
                        service = order[3]
                        subservice = order.get('subservice', '')
                        date_time = order[4]
                        note = order[5]
                        customer_name = order[8]
                        customer_phone = order[9]
                        status = order[7] if len(order) > 7 else 'pending'
                    
                    # Format date and time
                    try:
                        import datetime
                        dt_obj = datetime.datetime.strptime(str(date_time), "%Y-%m-%d %H:%M:%S")
                        formatted_date = dt_obj.strftime("%d.%m.%Y")
                        formatted_time = dt_obj.strftime("%H:%M")
                    except Exception as e:
                        logger.error(f"Error formatting date: {e}")
                        formatted_date = str(date_time).split(" ")[0] if date_time else "Bilinmiyor"
                        formatted_time = str(date_time).split(" ")[1] if date_time and " " in str(date_time) else "Bilinmiyor"
                    
                    # Build service text with subservice if available
                    service_text = service
                    if subservice:
                        service_text += f" ({subservice})"
                    
                    order_text = (
                        f"🔹 *Sifariş #{order_id}*\n"
                        f"👤 *Müştəri:* {customer_name}\n"
                        f"📞 *Əlaqə:* {customer_phone}\n"
                        f"🛠 *Xidmət:* {service_text}\n"
                        f"📅 *Tarix:* {formatted_date}\n"
                        f"🕒 *Saat:* {formatted_time}\n"
                        f"📝 *Qeyd:* {note}\n"
                    )
                    
                    # Add status indicator if not 'pending'
                    if status != 'pending':
                        status_emoji = "✅" if status == "accepted" else "⏳"
                        status_text = "Qəbul edildi" if status == "accepted" else status
                        order_text += f"🔄 *Status:* {status_emoji} {status_text}\n"
                    
                    # Add action buttons for pending orders
                    keyboard = InlineKeyboardMarkup(row_width=1)
                    
                    # Button options based on status
                    if status == 'pending':
                        keyboard.add(
                            InlineKeyboardButton("✅ Qəbul et", callback_data=f"accept_order_{order_id}"),
                            InlineKeyboardButton("❌ İmtina et", callback_data=f"reject_order_{order_id}")
                        )
                    elif status == 'accepted':
                        keyboard.add(
                            InlineKeyboardButton("📍 Yeri göstər", callback_data=f"show_location_{order_id}"),
                            InlineKeyboardButton("💰 Qiymət təyin et", callback_data=f"set_price_{order_id}"),
                            InlineKeyboardButton("✅ Sifarişi tamamla", callback_data=f"complete_order_{order_id}"),
                            InlineKeyboardButton("❌ Sifarişi ləğv et", callback_data=f"cancel_order_{order_id}")
                        )
                    else:
                        keyboard.add(
                            InlineKeyboardButton("📍 Yeri göstər", callback_data=f"show_location_{order_id}")
                        )
                    
                    await message.answer(
                        order_text,
                        reply_markup=keyboard,
                        parse_mode="Markdown"
                    )
                    
                except Exception as e:
                    logger.error(f"Error displaying order: {e}")
                    continue
                
        except Exception as e:
            logger.error(f"Error in view_active_orders: {e}")
            await message.answer(
                "❌ Sifarişlər yüklənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )




    # Handler for setting price for an order
    @dp.callback_query_handler(lambda c: c.data.startswith('set_price_'))
    async def set_order_price(callback_query: types.CallbackQuery, state: FSMContext):
        """Set price for a specific order"""
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
            
            # Store order ID in state
            async with state.proxy() as data:
                data['order_id'] = order_id
                data['service'] = order['service']
                data['subservice'] = order.get('subservice')
                data['customer_id'] = order['customer_id']
            
            # Get price range for this subservice (if exists)
            price_range = None
            if order.get('subservice'):
                artisan_id = get_artisan_by_telegram_id(callback_query.from_user.id)
                price_range = get_artisan_price_ranges(artisan_id, order['subservice'])
            
            price_info = ""
            if price_range:
                price_info = f"\n\nSizin bu xidmət üçün təyin etdiyiniz qiymət aralığı: {price_range['min_price']}-{price_range['max_price']} AZN"
            
            await callback_query.message.answer(
                f"💰 *Sifariş #{order_id} üçün qiymət təyin edin*\n\n"
                f"Xidmət: {order['service']}{' (' + order.get('subservice', '') + ')' if order.get('subservice') else ''}\n"
                f"Müştəri: {order['customer_name']}{price_info}\n\n"
                f"Zəhmət olmasa, xidmət üçün təyin etdiyiniz qiyməti AZN ilə daxil edin (məsələn: 50):",
                parse_mode="Markdown"
            )
            
            await ArtisanOrderStates.entering_order_price.set()
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in set_order_price: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()
    
    @dp.message_handler(state=ArtisanOrderStates.entering_order_price)
    async def process_order_price(message: types.Message, state: FSMContext):
        """Process order price input"""
        try:
            # Validate price input
            price_text = message.text.strip()
            
            try:
                price = float(price_text.replace(',', '.'))
                if price <= 0:
                    await message.answer("❌ Qiymət müsbət olmalıdır. Zəhmət olmasa, yenidən daxil edin:")
                    return
            except ValueError:
                await message.answer("❌ Düzgün qiymət daxil edin (məsələn: 50). Zəhmət olmasa, yenidən cəhd edin:")
                return
            
            # Get stored order data
            data = await state.get_data()
            order_id = data['order_id']
            
            # Debugging
            logger.info(f"Processing order price: ID={order_id}, Price={price}")
            
            # Calculate commission based on price
            commission_rate = 0.12  # Default rate (12%)
            
            for tier, info in COMMISSION_RATES.items():
                if price <= info["threshold"]:
                    commission_rate = info["rate"] / 100  # Convert percentage to decimal
                    break
            
            admin_fee = price * commission_rate
            artisan_amount = price - admin_fee
            
            # First update the price directly in the orders table
            conn = get_connection()
            cursor = conn.cursor()
            try:
                # Update orders table first
                cursor.execute(
                    "UPDATE orders SET price = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (price, order_id)
                )
                conn.commit()
                logger.info(f"Updated price in orders table for order {order_id}: {price}")
            except Exception as e:
                logger.error(f"Error updating price in orders table: {e}")
            finally:
                conn.close()
            
            # Save price to order in database using the main function
            success = set_order_price(
                order_id=order_id,
                price=price,
                admin_fee=admin_fee,
                artisan_amount=artisan_amount
            )
            
            if success:
                # Show payment options to artisan
                keyboard = InlineKeyboardMarkup(row_width=1)
                keyboard.add(
                    InlineKeyboardButton("💳 Kartla ödəniş", callback_data=f"payment_card_{order_id}"),
                    InlineKeyboardButton("💵 Nağd ödəniş", callback_data=f"payment_cash_{order_id}")
                )
                
                await message.answer(
                    f"✅ Qiymət uğurla təyin edildi: {price} AZN\n\n"
                    f"Komissiya ({int(commission_rate*100)}%): {admin_fee:.2f} AZN\n"
                    f"Sizə qalacaq məbləğ: {artisan_amount:.2f} AZN\n\n"
                    f"İndi müştəriyə ödəniş üsulunu seçməyi təklif edin:",
                    reply_markup=keyboard
                )
                
                # Notify customer about the price
                # Import inside function to avoid circular import
                from db import get_order_details, get_customer_by_id
                
                # Get order details for notification
                order = get_order_details(order_id)
                if order and order.get('customer_id'):
                    customer = get_customer_by_id(order['customer_id'])
                    if customer and customer.get('telegram_id'):
                        telegram_id = message.from_user.id
                        artisan_id = get_artisan_by_telegram_id(telegram_id)
                        artisan = get_artisan_by_id(artisan_id)
                    
                        if not artisan:
                            # Artisan bilgisi bulunamazsa, order'dan alalım
                            artisan = {'name': order.get('artisan_name', 'Usta')}

                        # Create accept/reject buttons
                        keyboard = InlineKeyboardMarkup(row_width=2)
                        keyboard.add(
                            InlineKeyboardButton("✅ Qəbul edirəm", callback_data=f"accept_price_{order_id}"),
                            InlineKeyboardButton("❌ Qəbul etmirəm", callback_data=f"reject_price_{order_id}")
                        )
                        
                        # Send price notification to customer
                        await bot.send_message(
                            chat_id=customer['telegram_id'],
                            text=f"💰 *Təyin edilmiş qiymət*\n\n"
                                f"Usta *{artisan['name']}* sifariş #{order_id} üçün "
                                f"*{price} AZN* məbləğində qiymət təyin etdi.\n\n"
                                f"Bu qiyməti qəbul edirsinizmi?",
                            reply_markup=keyboard,
                            parse_mode="Markdown"
                        )
                        logger.info(f"Price notification sent to customer for order {order_id}")
                    else:
                        logger.error(f"Customer information missing for order {order_id}")
                else:
                    logger.error(f"Failed to get order details for notification: {order_id}")
                
            else:
                await message.answer(
                    "❌ Qiymət təyin edilərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
            
            await state.finish()
            
        except Exception as e:
            logger.error(f"Error in process_order_price: {e}", exc_info=True)
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
    
    # Handler for card payment selection
    @dp.callback_query_handler(lambda c: c.data.startswith('payment_card_'))
    async def handle_card_payment(callback_query: types.CallbackQuery):
        """Handle card payment selection"""
        try:
            # Extract order ID from callback data
            order_id = int(callback_query.data.split('_')[-1])
            
            # Get order details including price
            order = get_order_details(order_id)
            
            if not order or not order.get('price'):
                await callback_query.message.answer(
                    "❌ Sifariş məlumatları və ya qiyməti tapılmadı."
                )
                await callback_query.answer()
                return
            
            # Get artisan info
            artisan_id = get_artisan_by_telegram_id(callback_query.from_user.id)
            artisan = get_artisan_by_id(artisan_id)
            
            if not artisan:
                await callback_query.message.answer("❌ Usta məlumatları tapılmadı.")
                await callback_query.answer()
                return
            
            # Update payment method in database
            from db import update_payment_method
            success = update_payment_method(order_id, "card")
            
            if success:
                # Inform artisan about the process
                await callback_query.message.answer(
                    f"💳 *Kart ödənişi seçildi*\n\n"
                    f"Sifariş: #{order_id}\n"
                    f"Məbləğ: {order['price']} AZN\n"
                    f"Sizə qalacaq: {order['artisan_amount']:.2f} AZN\n\n"
                    f"Müştəriyə ödəniş bildirişi göndərildi. Ödəniş tamamlandıqdan sonra "
                    f"24 saat ərzində hesabınıza köçürüləcək.\n\n"
                    f"ℹ️ Qeyd: Əgər ödəniş 24 saat ərzində hesabınıza köçürülməzsə, "
                    f"müqaviləyə uyğun olaraq şirkət tərəfindən əlavə olaraq məbləğin 15%-i həcmində "
                    f"kompensasiya ödəniləcək.",
                    parse_mode="Markdown"
                )
                
                # Notify customer about payment details
                # This would normally be done through a customer notification system
                # notify_customer_about_card_payment(order)
                
            else:
                await callback_query.message.answer(
                    "❌ Ödəniş məlumatları yenilənilərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in handle_card_payment: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()
    
    # Handler for cash payment selection
    @dp.callback_query_handler(lambda c: c.data.startswith('payment_cash_'))
    async def handle_cash_payment(callback_query: types.CallbackQuery):
        """Handle cash payment selection"""
        try:
            # Extract order ID from callback data
            order_id = int(callback_query.data.split('_')[-1])
            
            # Get order details including price
            order = get_order_details(order_id)
            
            if not order or not order.get('price'):
                await callback_query.message.answer(
                    "❌ Sifariş məlumatları və ya qiyməti tapılmadı."
                )
                await callback_query.answer()
                return
            
            # Update payment method in database
            from db import update_payment_method
            success = update_payment_method(order_id, "cash")
            
            if success:
                # Calculate admin fee
                admin_fee = order.get('admin_fee', order['price'] * 0.12)  # Default 12% if not set
                
                # Inform artisan about the process
                await callback_query.message.answer(
                    f"💵 *Nağd ödəniş seçildi*\n\n"
                    f"Sifariş: #{order_id}\n"
                    f"Ümumi məbləğ: {order['price']} AZN\n"
                    f"Komissiya məbləği: {admin_fee:.2f} AZN\n\n"
                    f"Müştəridən ödənişi aldıqdan sonra, 24 saat ərzində komissiya məbləğini "
                    f"admin kartına köçürməlisiniz.\n\n"
                    f"Admin kart məlumatları:\n"
                    f"Kart nömrəsi: 4169 7388 5555 6666\n"
                    f"Sahibi: USTABOT LLC\n\n"
                    f"⚠️ *Diqqət*: 24 saat ərzində komissiya ödənişi edilməzsə, "
                    f"hesabınız avtomatik bloklanacaq və məbləğin 15%-i həcmində əlavə cərimə tətbiq ediləcək.",
                    parse_mode="Markdown"
                )
                
                # Add payment confirmation button
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton(
                    "✅ Ödənişi təsdiqlə", 
                    callback_data=f"confirm_art_payment_{order_id}"
                ))
                
                await callback_query.message.answer(
                    "Komissiya ödənişini tamamladıqdan sonra, bu düyməni basaraq təsdiq edin:",
                    reply_markup=keyboard
                )
                
                # Notify customer about payment details
                # notify_customer_about_cash_payment(order)
                
            else:
                await callback_query.message.answer(
                    "❌ Ödəniş məlumatları yenilənilərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in handle_cash_payment: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()
    
    # Handler for showing order location
    @dp.callback_query_handler(lambda c: c.data.startswith('show_location_'))
    async def show_order_location(callback_query: types.CallbackQuery):
        """Show customer location for an order"""
        try:
            # Extract order ID from callback data
            order_id = int(callback_query.data.split('_')[-1])
            
            # Get order details
            order = get_order_details(order_id)
            
            if not order or not order.get('latitude') or not order.get('longitude'):
                await callback_query.message.answer(
                    "❌ Bu sifariş üçün yer məlumatı tapılmadı."
                )
                await callback_query.answer()
                return
            
            # Send location
            await callback_query.message.answer_location(
                latitude=order['latitude'],
                longitude=order['longitude']
            )
            
            # Send additional information
            customer_name = order['customer_name']
            customer_phone = order['customer_phone']
            
            await callback_query.message.answer(
                f"📍 *{customer_name}* adlı müştərinin yeri.\n"
                f"📞 Əlaqə: {customer_phone}\n\n"
                f"ℹ️ Müştəriyə getməzdən əvvəl telefon vasitəsilə əlaqə saxlamağınız tövsiyə olunur.",
                parse_mode="Markdown"
            )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in show_order_location: {e}")
            await callback_query.message.answer(
                "❌ Yer məlumatı göstərilərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()
    
    # Handler for completing an order
    @dp.callback_query_handler(lambda c: c.data.startswith('complete_order_'))
    async def complete_order(callback_query: types.CallbackQuery, state: FSMContext):
        """Mark an order as completed"""
        try:
            # Extract order ID from callback data
            order_id = int(callback_query.data.split('_')[-1])
            
            # Check if price has been set
            order = get_order_details(order_id)
            if not order.get('price'):
                await callback_query.message.answer(
                    "❌ Sifarişi tamamlamaq üçün əvvəlcə qiymət təyin etməlisiniz. "
                    "Zəhmət olmasa, 'Qiymət təyin et' düyməsini istifadə edin."
                )
                await callback_query.answer()
                return
            
            # Store order ID in state
            async with state.proxy() as data:
                data['order_id'] = order_id
            
            # Ask for confirmation
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("✅ Bəli", callback_data=f"confirm_complete_{order_id}"),
                InlineKeyboardButton("❌ Xeyr", callback_data=f"cancel_complete_{order_id}")
            )
            
            await callback_query.message.answer(
                f"Sifariş #{order_id} tamamlandı? Bu əməliyyat geri qaytarıla bilməz.",
                reply_markup=keyboard
            )
            
            await callback_query.answer()
            await ArtisanOrderStates.completing_order.set()
            
        except Exception as e:
            logger.error(f"Error in complete_order: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()
    
    # Handler for confirming order completion
    @dp.callback_query_handler(
        lambda c: c.data.startswith('confirm_complete_'),
        state=ArtisanOrderStates.completing_order
    )
    async def confirm_complete_order(callback_query: types.CallbackQuery, state: FSMContext):
        """Confirm order completion"""
        try:
            # Extract order ID from callback data
            order_id = int(callback_query.data.split('_')[-1])
            
            # Update order status in database
            success = update_order_status(order_id, "completed")
            
            if success:
                await callback_query.message.answer(
                    f"✅ Sifariş #{order_id} uğurla tamamlandı!\n\n"
                    f"Müştəriyə bildiriş göndərildi və qiymətləndirmə üçün dəvət edildi. "
                    f"Qiymətləndirmə alındıqdan sonra sizə bildiriş göndəriləcək."
                )
                
                # Get order details for notification
                order = get_order_details(order_id)
                
                if order and order.get('customer_id'):
                    # Notify customer that order is completed
                    customer = get_customer_by_id(order['customer_id'])
                    if customer and customer.get('telegram_id'):
                        await bot.send_message(
                            chat_id=customer['telegram_id'],
                            text=f"✅ *Sifarişiniz tamamlandı*\n\n"
                                f"Usta, sifariş #{order_id} üçün xidmətin tamamlandığını təsdiqlədi.\n"
                                f"Təşəkkür edirik!",
                            parse_mode="Markdown"
                        )
                        
                        # Send review request
                        from notification_service import send_review_request_to_customer
                        await send_review_request_to_customer(order_id)
                
            else:
                await callback_query.message.answer(
                    "❌ Sifariş statusu yenilənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
            
            await callback_query.answer()
            await state.finish()
            
        except Exception as e:
            logger.error(f"Error in confirm_complete_order: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()
            await state.finish()
    
    # Handler for canceling order completion
    @dp.callback_query_handler(
        lambda c: c.data.startswith('cancel_complete_'),
        state=ArtisanOrderStates.completing_order
    )
    async def cancel_complete_order(callback_query: types.CallbackQuery, state: FSMContext):
        """Cancel order completion"""
        try:
            await callback_query.message.answer(
                "❌ Əməliyyat ləğv edildi. Sifariş statusu dəyişdirilmədi."
            )
            
            await callback_query.answer()
            await state.finish()
            
        except Exception as e:
            logger.error(f"Error in cancel_complete_order: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()
            await state.finish()
    
    # Handler for canceling an order
    @dp.callback_query_handler(lambda c: c.data.startswith('cancel_order_'))
    async def cancel_order(callback_query: types.CallbackQuery, state: FSMContext):
        """Cancel an order"""
        try:
            # Extract order ID from callback data
            order_id = int(callback_query.data.split('_')[-1])
            
            # Store order ID in state
            async with state.proxy() as data:
                data['order_id'] = order_id
            
            # Ask for confirmation
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("✅ Bəli", callback_data=f"confirm_cancel_{order_id}"),
                InlineKeyboardButton("❌ Xeyr", callback_data=f"abort_cancel_{order_id}")
            )
            
            await callback_query.message.answer(
                f"Sifariş #{order_id} ləğv edilsin? Bu əməliyyat geri qaytarıla bilməz.",
                reply_markup=keyboard
            )
            
            await callback_query.answer()
            await ArtisanOrderStates.managing_order.set()
            
        except Exception as e:
            logger.error(f"Error in cancel_order: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()
    
    # Handler for confirming order cancellation
    @dp.callback_query_handler(
        lambda c: c.data.startswith('confirm_cancel_'),
        state=ArtisanOrderStates.managing_order
    )
    async def confirm_cancel_order(callback_query: types.CallbackQuery, state: FSMContext):
        """Confirm order cancellation"""
        try:
            # Extract order ID from callback data
            order_id = int(callback_query.data.split('_')[-1])
            
            # Update order status in database
            success = update_order_status(order_id, "cancelled")
            
            if success:
                await callback_query.message.answer(
                    f"❌ Sifariş #{order_id} ləğv edildi.\n\n"
                    f"Müştəriyə bu barədə bildiriş göndərildi."
                )
                
                # Get order details for notification
                order = get_order_details(order_id)
                
                # Here you would normally send a notification to the customer
                # This would be implemented through a customer notification system
                
            else:
                await callback_query.message.answer(
                    "❌ Sifariş statusu yenilənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
            
            await callback_query.answer()
            await state.finish()
            
        except Exception as e:
            logger.error(f"Error in confirm_cancel_order: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()
            await state.finish()
    
    # Handler for aborting order cancellation
    @dp.callback_query_handler(
        lambda c: c.data.startswith('abort_cancel_'),
        state=ArtisanOrderStates.managing_order
    )
    async def abort_cancel_order(callback_query: types.CallbackQuery, state: FSMContext):
        """Abort order cancellation"""
        try:
            await callback_query.message.answer(
                "✅ Əməliyyat ləğv edildi. Sifariş statusu dəyişdirilmədi."
            )
            
            await callback_query.answer()
            await state.finish()
            
        except Exception as e:
            logger.error(f"Error in abort_cancel_order: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()
            await state.finish()
    
    # Handler for "Reviews" button
    @dp.message_handler(lambda message: message.text == "⭐ Rəylər")
    async def view_reviews(message: types.Message):
        """Show reviews for the artisan"""
        try:
            # Get artisan ID
            telegram_id = message.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if not artisan_id:
                await message.answer(
                    "❌ Siz hələ usta kimi qeydiyyatdan keçməmisiniz."
                )
                return
            
            # Check if artisan is blocked
            is_blocked, reason, amount = get_artisan_blocked_status(artisan_id)
            if is_blocked:
                await message.answer(
                    f"⛔ Hesabınız bloklanıb. Rəylərinizi görmək üçün əvvəlcə bloku açın.\n"
                    f"Səbəb: {reason}\n"
                    f"Ödəniş məbləği: {amount} AZN\n"
                    f"Ödəniş etmək üçün: /pay_fine"
                )
                return
            
            # Get reviews
            reviews = get_artisan_reviews(artisan_id)
            
            if not reviews:
                await message.answer(
                    "📭 Hal-hazırda heç bir rəyiniz yoxdur.\n\n"
                    "Rəylər sifarişlər tamamlandıqdan sonra müştərilər tərəfindən verilir. "
                    "Xidmətinizi yaxşılaşdırmaq üçün müştəriləri rəy verməyə həvəsləndirin."
                )
                return
            
            await message.answer(
                f"⭐ *Rəylər ({len(reviews)}):*",
                parse_mode="Markdown"
            )
            
            # Display each review
            for review in reviews:
                # Ensure review is a dictionary
                if isinstance(review, dict):
                    review_id = review.get('id')
                    rating = review.get('rating')
                    comment = review.get('comment')
                    customer_name = review.get('customer_name')
                    service = review.get('service')
                else:
                    # If it's a tuple (old implementation), extract values
                    review_id = review[0]
                    rating = review[4]
                    comment = review[5]
                    customer_name = review[7] 
                    service = review[8]
                
                # Create star rating display
                stars = "⭐" * rating if rating else ""
                
                review_text = (
                    f"📝 *Rəy #{review_id}*\n"
                    f"👤 *Müştəri:* {customer_name}\n"
                    f"🛠 *Xidmət:* {service}\n"
                    f"⭐ *Qiymətləndirmə:* {stars} ({rating}/5)\n"
                )
                
                if comment:
                    review_text += f"💬 *Şərh:* {comment}\n"
                
                await message.answer(
                    review_text,
                    parse_mode="Markdown"
                )
            
            avg_rating = get_artisan_average_rating(artisan_id)
        
            if avg_rating:
                avg_stars = "⭐" * round(avg_rating)
                await message.answer(
                    f"📊 *Ümumi qiymətləndirməniz:* {avg_stars} ({avg_rating:.1f}/5)\n\n"
                    f"Yaxşı rəylər müştərilərin sizi seçməsinə kömək edir. Xidmətinizi yüksək səviyyədə "
                    f"saxlayın və müştəriləri rəy verməyə həvəsləndirin!",
                    parse_mode="Markdown"
                )
        
        except Exception as e:
            logger.error(f"Error in view_reviews: {e}")
            await message.answer(
                "❌ Rəylər yüklənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
    
    # Handler for "Statistics" button
    @dp.message_handler(lambda message: message.text == "📊 Statistika")
    async def view_statistics(message: types.Message):
        """Show statistics for the artisan"""
        try:
            # Get artisan ID
            telegram_id = message.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if not artisan_id:
                await message.answer(
                    "❌ Siz hələ usta kimi qeydiyyatdan keçməmisiniz."
                )
                return
            
            # Check if artisan is blocked
            is_blocked, reason, amount = get_artisan_blocked_status(artisan_id)
            if is_blocked:
                await message.answer(
                    f"⛔ Hesabınız bloklanıb. Statistikanızı görmək üçün əvvəlcə bloku açın.\n"
                    f"Səbəb: {reason}\n"
                    f"Ödəniş məbləği: {amount} AZN\n"
                    f"Ödəniş etmək üçün: /pay_fine"
                )
                return
            
            # Get artisan statistics from database
            from db import get_artisan_statistics
            stats = get_artisan_statistics(artisan_id)
            
            if stats:
                # Display the statistics
                await message.answer(
                    "📊 *Statistika*\n\n"
                    f"👥 *Ümumi müştəri sayı:* {stats['total_customers']}\n"
                    f"✅ *Tamamlanan sifarişlər:* {stats['completed_orders']}\n"
                    f"❌ *Ləğv edilən sifarişlər:* {stats['cancelled_orders']}\n"
                    f"⭐ *Orta qiymətləndirmə:* {stats['avg_rating']:.1f}/5\n"
                    f"💰 *Ümumi qazanc:* {stats['total_earnings']:.2f} AZN\n"
                    f"💰 *Son 30 gündə qazanc:* {stats['monthly_earnings']:.2f} AZN\n\n"
                    f"📈 *Fəaliyyətiniz:* {stats['activity_status']}\n\n"
                    f"🔝 *Ən çox tələb olunan xidmətiniz:* {stats['top_service']}\n"
                    f"🔝 *Ən çox qazanc gətirən xidmətiniz:* {stats['most_profitable_service']}\n\n"
                    f"📆 *Son 7 gündə sifarişlər:* {stats['last_week_orders']}\n"
                    f"📆 *Son 30 gündə sifarişlər:* {stats['last_month_orders']} "
                    f"({'+' if stats['order_growth'] >= 0 else ''}{stats['order_growth']}%)",
                    parse_mode="Markdown"
                )
            else:
                # Display placeholder stats if no actual data
                await message.answer(
                    "📊 *Statistika*\n\n"
                    "👥 *Ümumi müştəri sayı:* 0\n"
                    "✅ *Tamamlanan sifarişlər:* 0\n"
                    "⭐ *Orta qiymətləndirmə:* N/A\n"
                    "💰 *Ümumi qazanc:* 0.00 AZN\n"
                    "📈 *Son 30 gündə sifarişlər:* 0\n\n"
                    "_Daha çox statistika görmək üçün sifarişlər tamamlamalısınız._",
                    parse_mode="Markdown"
                )
            
        except Exception as e:
            logger.error(f"Error in view_statistics: {e}")
            await message.answer(
                "❌ Statistika yüklənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
    
    # Handler for "Profile Settings" button
    @dp.message_handler(lambda message: message.text == "⚙️ Profil ayarları")
    async def profile_settings(message: types.Message, state: FSMContext):
        """Show and manage artisan profile settings"""
        try:
            # Clear any existing state first
            current_state = await state.get_state()
            if current_state:
                await state.finish()
                
            # Get artisan ID
            telegram_id = message.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if not artisan_id:
                await message.answer(
                    "❌ Siz hələ usta kimi qeydiyyatdan keçməmisiniz."
                )
                return
            
            # Get artisan details
            artisan = get_artisan_by_id(artisan_id)
            
            if not artisan:
                await message.answer(
                    "❌ Profil məlumatları tapılmadı. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
                return
                    
            # Check if artisan is blocked
            is_blocked, reason, amount = get_artisan_blocked_status(artisan_id)
            if is_blocked:
                blocked_info = (
                    f"\n\n⛔ *Hesabınız bloklanıb*\n"
                    f"Səbəb: {reason}\n"
                    f"Ödəniş məbləği: {amount} AZN\n"
                    f"Ödəniş etmək üçün: /pay_fine"
                )
            else:
                blocked_info = ""
            
            # Display profile information
            profile_text = (
                "👤 *Profil məlumatlarınız*\n\n"
                f"👤 *Ad:* {artisan['name']}\n"
                f"📞 *Telefon:* {artisan['phone']}\n"
                f"🏙 *Şəhər:* {artisan['city']}\n"
                f"🛠 *Xidmət:* {artisan['service']}\n"
                f"📍 *Yer:* {artisan['location']}\n"
                f"⭐ *Reytinq:* {artisan['rating']:.1f}/5\n"
                f"📅 *Qeydiyyat tarixi:* {artisan['created_at'].strftime('%d.%m.%Y')}\n"
                f"🔄 *Status:* {'Aktiv' if artisan['active'] else 'Qeyri-aktiv'}{blocked_info}"
            )
            
            await message.answer(
                profile_text,
                parse_mode="Markdown"
            )
            
            # Create settings keyboard
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                InlineKeyboardButton("👤 Adımı dəyiş", callback_data="change_artisan_name"),
                InlineKeyboardButton("📞 Telefon nömrəsini dəyiş", callback_data="change_artisan_phone"),
                InlineKeyboardButton("🏙 Şəhəri dəyiş", callback_data="change_artisan_city"),
                InlineKeyboardButton("🛠 Xidmət növünü dəyiş", callback_data="change_artisan_service"),
                InlineKeyboardButton("📍 Yeri yenilə", callback_data="update_artisan_location"),
                InlineKeyboardButton("🔄 Aktivliyi dəyiş", callback_data="toggle_artisan_active"),
                InlineKeyboardButton("💳 Ödəniş məlumatlarını tənzimlə", callback_data="setup_payment_info"),
                InlineKeyboardButton("🔙 Geri", callback_data="back_to_artisan_menu")
            )
            
            await message.answer(
                "⚙️ *Profil ayarları*\n\n"
                "Aşağıdakı əməliyyatlardan birini seçin:",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            # Set state for profile management
            await ArtisanProfileStates.viewing_profile.set()
        
        except Exception as e:
            logger.error(f"Error in profile_settings: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            # Problem yaranarsa, əsas menyuya qayıtmaqla həlli asanlaşdıraq
            await show_artisan_menu(message)
    
    # Handler for changing artisan name
    @dp.callback_query_handler(
        lambda c: c.data == "change_artisan_name",
        state=ArtisanProfileStates.viewing_profile
    )
    async def change_artisan_name(callback_query: types.CallbackQuery, state: FSMContext):
        """Start process to change artisan name"""
        try:
            await callback_query.message.answer(
                "👤 Zəhmət olmasa, yeni adınızı daxil edin:"
            )
            
            await ArtisanProfileStates.updating_name.set()
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in change_artisan_name: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await callback_query.answer()
    
    @dp.message_handler(state=ArtisanProfileStates.updating_name)
    async def process_updated_name(message: types.Message, state: FSMContext):
        """Process updated artisan name"""
        try:
            # Validate name
            name = message.text.strip()
            
            if len(name) < 2 or len(name) > 50:
                await message.answer(
                    "❌ Ad ən azı 2, ən çoxu 50 simvol olmalıdır. Zəhmət olmasa, yenidən daxil edin:"
                )
                return
            
            # Update name in database
            telegram_id = message.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            success = update_artisan_profile(artisan_id, {'name': name})
            
            if success:
                await message.answer(
                    "✅ Adınız uğurla yeniləndi!"
                )
            else:
                await message.answer(
                    "❌ Ad yenilənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
            
            # Return to profile settings
            await state.finish()
            await profile_settings(message, state)
            
        except Exception as e:
            logger.error(f"Error in process_updated_name: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_artisan_menu(message)
    
    # Handler for changing artisan phone number
    @dp.callback_query_handler(
        lambda c: c.data == "change_artisan_phone",
        state=ArtisanProfileStates.viewing_profile
    )
    async def change_artisan_phone(callback_query: types.CallbackQuery, state: FSMContext):
        """Start process to change artisan phone number"""
        try:
            await callback_query.message.answer(
                "📞 Zəhmət olmasa, yeni telefon nömrənizi daxil edin (məsələn: +994501234567):"
            )
            
            await ArtisanProfileStates.updating_phone.set()
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in change_artisan_phone: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await callback_query.answer()
    
    @dp.message_handler(state=ArtisanProfileStates.updating_phone)
    async def process_updated_phone(message: types.Message, state: FSMContext):
        """Process updated artisan phone number"""
        try:
            # Validate phone format
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
            
            # Check if phone is already used by another artisan
            telegram_id = message.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if check_artisan_exists(phone=phone, exclude_id=artisan_id):
                await message.answer(
                    "❌ Bu telefon nömrəsi artıq başqa usta tərəfindən istifadə olunur. "
                    "Zəhmət olmasa, başqa nömrə daxil edin:"
                )
                return
            
            # Update phone in database
            success = update_artisan_profile(artisan_id, {'phone': phone})
            
            if success:
                await message.answer(
                    "✅ Telefon nömrəniz uğurla yeniləndi!"
                )
            else:
                await message.answer(
                    "❌ Telefon nömrəsi yenilənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
            
            # Return to profile settings
            await state.finish()
            await profile_settings(message, state)
            
        except Exception as e:
            logger.error(f"Error in process_updated_phone: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_artisan_menu(message)
    
    # Handler for changing artisan city
    @dp.callback_query_handler(
        lambda c: c.data == "change_artisan_city",
        state=ArtisanProfileStates.viewing_profile
    )
    async def change_artisan_city(callback_query: types.CallbackQuery, state: FSMContext):
        """Start process to change artisan city"""
        try:
            await callback_query.message.answer(
                "🏙 Zəhmət olmasa, yeni şəhərinizi daxil edin:"
            )
            
            await ArtisanProfileStates.updating_city.set()
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in change_artisan_city: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await callback_query.answer()
    
    @dp.message_handler(state=ArtisanProfileStates.updating_city)
    async def process_updated_city(message: types.Message, state: FSMContext):
        """Process updated artisan city"""
        try:
            # Validate city
            city = message.text.strip()
            
            if len(city) < 2 or len(city) > 50:
                await message.answer(
                    "❌ Şəhər adı ən azı 2, ən çoxu 50 simvol olmalıdır. Zəhmət olmasa, yenidən daxil edin:"
                )
                return
            
            # Update city in database
            telegram_id = message.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            success = update_artisan_profile(artisan_id, {'city': city})
            
            if success:
                await message.answer(
                    "✅ Şəhəriniz uğurla yeniləndi!"
                )
            else:
                await message.answer(
                    "❌ Şəhər yenilənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
            
            # Return to profile settings
            await state.finish()
            await profile_settings(message, state)
            
        except Exception as e:
            logger.error(f"Error in process_updated_city: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_artisan_menu(message)
    
    # Handler for changing artisan service
    @dp.callback_query_handler(
    lambda c: c.data == "change_artisan_service",
    state="*"
    )
    async def change_artisan_service(callback_query: types.CallbackQuery, state: FSMContext):
        """Start process to change service type"""
        try:
            # Get artisan ID and current service
            telegram_id = callback_query.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if not artisan_id:
                await callback_query.message.answer(
                    "❌ Siz hələ usta kimi qeydiyyatdan keçməmisiniz."
                )
                await callback_query.answer()
                await state.finish()
                return
                
            # Get current service
            artisan = get_artisan_by_id(artisan_id)
            current_service = artisan['service']
            
            # Get available services
            services = get_services()
            
            # Filter out current service
            available_services = [s for s in services if s != current_service]
            
            # Create inline keyboard with service buttons
            keyboard = InlineKeyboardMarkup(row_width=2)
            
            for service in available_services:
                keyboard.add(InlineKeyboardButton(service, callback_data=f"update_service_{service}"))
            
            keyboard.add(InlineKeyboardButton("🔙 Geri", callback_data="back_to_artisan_menu"))
            
            await callback_query.message.answer(
                f"🛠 Hal-hazırda seçilmiş xidmət növünüz: *{current_service}*\n\n"
                "Zəhmət olmasa, yeni xidmət növünü seçin:\n\n"
                "⚠️ *Diqqət*: Xidmət növünü dəyişdikdə, bütün alt xidmətlər və qiymət aralıqları silinəcək "
                "və yeni xidmət növü üçün yenidən təyin etməli olacaqsınız.",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            await ArtisanProfileStates.updating_service.set()
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in change_artisan_service: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await callback_query.answer()
    
    # Handler for selected service update
    @dp.callback_query_handler(
        lambda c: c.data.startswith("update_service_"),
        state=ArtisanProfileStates.updating_service
    )
    async def process_updated_service(callback_query: types.CallbackQuery, state: FSMContext):
        """Process the updated service selection"""
        try:
            # Extract service from callback data
            selected_service = callback_query.data.split('_', 2)[2]
            
            # Update service in database
            telegram_id = callback_query.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            # Update service and reset price ranges
            from db import update_artisan_service_and_reset_prices
            success = update_artisan_service_and_reset_prices(artisan_id, selected_service)
            
            if success:
                await callback_query.message.answer(
                    f"✅ Xidmət növünüz uğurla *{selected_service}* olaraq dəyişdirildi!\n\n"
                    f"İndi bu xidmət növü üçün alt xidmətləri və qiymət aralıqlarını təyin etməlisiniz.",
                    parse_mode="Markdown"
                )
                
                # Prompt to set up price ranges
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton(
                    "💰 Qiymət aralıqlarını təyin et", 
                    callback_data="setup_price_ranges"
                ))
                
                await callback_query.message.answer(
                    "Qiymət aralıqlarını təyin etmək üçün aşağıdakı düyməni istifadə edin:",
                    reply_markup=keyboard
                )
            else:
                await callback_query.message.answer(
                    "❌ Xidmət növü dəyişdirildiyi zaman xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
            
            await callback_query.answer()
            await state.finish()
            
        except Exception as e:
            logger.error(f"Error in process_updated_service: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await callback_query.answer()
    
    # Handler for "Update Location" button
    # 1. Əvvəlcə update_artisan_location funksiyasını dəqiq analiz edək
    # Terminaldakı xətaya görə, update_artisan_location funksiyasına artisan_id parametri ötürülməyib

    @dp.callback_query_handler(
        lambda c: c.data == "update_artisan_location",
        state="*"  # Hər hansı state'də işə düşsün
    )
    async def handle_update_artisan_location(callback_query: types.CallbackQuery, state: FSMContext):
        """Update artisan location"""
        try:
            # Get artisan ID
            telegram_id = callback_query.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if not artisan_id:
                await callback_query.message.answer(
                    "❌ Siz hələ usta kimi qeydiyyatdan keçməmisiniz."
                )
                await callback_query.answer()
                await state.finish()
                return
            
            # Create keyboard with location button
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(KeyboardButton("📍 Yerimi paylaş", request_location=True))
            keyboard.add(KeyboardButton("🔙 Geri"))
            
            await callback_query.message.answer(
                "📍 Xidmət göstərdiyiniz yeni ərazini paylaşın:\n\n"
                "ℹ️ *Ətraflı məlumat:*\n"
                "• Yerləşdiyiniz məkanı dəqiq müəyyən etmək üçün telefonunuzda GPS xidmətinin aktiv olduğundan əmin olun.\n"
                "• 'Yerimi paylaş' düyməsinə basdıqdan sonra sizə gələn sorğunu təsdiqləyin.\n"
                "• Bu lokasiya əsas xidmət göstərdiyiniz ərazi kimi qeyd olunacaq və müştərilər axtarış edərkən bu əraziyə uyğun olaraq sizi tapacaq.",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            # Store artisan_id in state for later use
            async with state.proxy() as data:
                data['artisan_id'] = artisan_id
            
            await ArtisanProfileStates.updating_location.set()
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in handle_update_artisan_location: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await callback_query.answer()
    
    # Handler for location update
    @dp.message_handler(
    content_types=types.ContentType.LOCATION,
    state=ArtisanProfileStates.updating_location
    )
    async def process_artisan_location_update(message: types.Message, state: FSMContext):
        """Process location update for artisan profile"""
        try:
            # Get artisan_id from state
            data = await state.get_data()
            artisan_id = data.get('artisan_id')
            
            if not artisan_id:
                # If not found in state, try to get from telegram_id
                telegram_id = message.from_user.id
                artisan_id = get_artisan_by_telegram_id(telegram_id)
                    
            if not artisan_id:
                await message.answer(
                    "❌ Artisan ID tapılmadı. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
                await state.finish()
                await show_artisan_menu(message)
                return
            
            # Get location data
            latitude = message.location.latitude
            longitude = message.location.longitude
            
            # Try to get location name based on coordinates
            location_name = await get_location_name(latitude, longitude)
            city = None
            
            if location_name:
                city = location_name  # Use location name as city if available
            
            # Get current artisan info for confirmation
            artisan = get_artisan_by_id(artisan_id)
            
            # Store location in state for confirmation
            async with state.proxy() as data:
                data['new_latitude'] = latitude
                data['new_longitude'] = longitude
                data['new_location_name'] = location_name
                data['new_city'] = city
            
            # Create confirmation keyboard
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("✅ Təsdiqlə", callback_data="confirm_location_update"),
                InlineKeyboardButton("❌ Ləğv et", callback_data="cancel_location_update")
            )
            
            location_display = location_name if location_name else "paylaşdığınız məkan"
            
            # Show confirmation message
            await message.answer(
                f"📍 *Yeni məkan məlumatları:*\n\n"
                f"Seçdiyiniz məkan: *{location_display}*\n\n"
                f"Bu məkanı əsas xidmət göstərdiyiniz ərazi kimi təyin etmək istəyirsiniz?",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Error in process_artisan_location_update: {e}", exc_info=True)
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.",
                reply_markup=types.ReplyKeyboardRemove()
            )
            await state.finish()
            await show_artisan_menu(message)



    @dp.callback_query_handler(
    lambda c: c.data == "confirm_location_update",
    state=ArtisanProfileStates.updating_location
    )
    async def confirm_location_update(callback_query: types.CallbackQuery, state: FSMContext):
        """Confirm artisan location update"""
        try:
            # Get data from state
            data = await state.get_data()
            artisan_id = data.get('artisan_id')
            latitude = data.get('new_latitude')
            longitude = data.get('new_longitude')
            location_name = data.get('new_location_name')
            city = None
            
            if not artisan_id:
                # Try to get from telegram_id
                telegram_id = callback_query.from_user.id
                artisan_id = get_artisan_by_telegram_id(telegram_id)
                
            if not artisan_id or not latitude or not longitude:
                await callback_query.message.answer(
                    "❌ Məkan məlumatları tam deyil. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
                await state.finish()
                await show_artisan_menu(callback_query.message)
                return
                
            # Update location in database with correct parameter passing
            success = update_artisan_location(
                artisan_id=artisan_id,
                latitude=latitude,
                longitude=longitude,
                location_name=location_name,
                city=city
            )
            
            if success:
                location_display = location_name if location_name else "yeni məkan"
                
                await callback_query.message.answer(
                    f"✅ Yeriniz uğurla *{location_display}* olaraq yeniləndi!\n\n"
                    f"Bu, müştərilərin sizi daha asanlıqla tapmasına kömək edəcək.",
                    parse_mode="Markdown",
                    reply_markup=types.ReplyKeyboardRemove()
                )
                
                # Get updated artisan info
                artisan = get_artisan_by_id(artisan_id)
                
                # Display updated profile info
                if artisan:
                    profile_text = (
                        "👤 *Yenilənmiş profil məlumatlarınız*\n\n"
                        f"👤 *Ad:* {artisan['name']}\n"
                        f"📞 *Telefon:* {artisan['phone']}\n"
                        f"🏙 *Şəhər:* {artisan['city']}\n"
                        f"🛠 *Xidmət:* {artisan['service']}\n"
                        f"📍 *Yer:* {location_display}\n"
                        f"⭐ *Reytinq:* {artisan['rating']:.1f}/5\n"
                    )
                    
                    await callback_query.message.answer(
                        profile_text,
                        parse_mode="Markdown"
                    )
            else:
                await callback_query.message.answer(
                    "❌ Yer məlumatı yenilənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
            
            # Show main menu
            await state.finish()
            await callback_query.answer()

            keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(KeyboardButton("📋 Aktiv sifarişlər"))
            keyboard.add(KeyboardButton("⭐ Rəylər"), KeyboardButton("📊 Statistika"))
            keyboard.add(KeyboardButton("💰 Qiymət ayarları"), KeyboardButton("⚙️ Profil ayarları"))
            keyboard.add(KeyboardButton("🔄 Rol seçiminə qayıt"))
                
            await callback_query.message.answer(
                "👷‍♂️ *Usta Paneli*\n\n"
                "Aşağıdakı əməliyyatlardan birini seçin:",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Error in confirm_location_update: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await callback_query.answer()
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(KeyboardButton("📋 Aktiv sifarişlər"))
            keyboard.add(KeyboardButton("⭐ Rəylər"), KeyboardButton("📊 Statistika"))
            keyboard.add(KeyboardButton("💰 Qiymət ayarları"), KeyboardButton("⚙️ Profil ayarları"))
            keyboard.add(KeyboardButton("🔄 Rol seçiminə qayıt"))
                
            await callback_query.message.answer(
                "👷‍♂️ *Usta Paneli*\n\n"
                "Aşağıdakı əməliyyatlardan birini seçin:",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )


    @dp.callback_query_handler(
    lambda c: c.data == "cancel_location_update",
    state=ArtisanProfileStates.updating_location
    )
    async def cancel_location_update(callback_query: types.CallbackQuery, state: FSMContext):
        """Cancel artisan location update"""
        try:
            await callback_query.message.answer(
                "❌ Məkan yenilənməsi ləğv edildi.",
                reply_markup=types.ReplyKeyboardRemove()
            )
            await state.finish()
            await show_artisan_menu(callback_query.message)
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in cancel_location_update: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_artisan_menu(callback_query.message)
            await callback_query.answer()
    
    # Handler for "Toggle Active" button
    @dp.callback_query_handler(
    lambda c: c.data == "toggle_artisan_active",
    state="*"  # Burada state'i genişləndiririk ki, hər hansı state'də işləsin
    )
    async def toggle_artisan_active(callback_query: types.CallbackQuery, state: FSMContext):
        """Toggle artisan active status"""
        try:
            # Get artisan ID and current status
            telegram_id = callback_query.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if not artisan_id:
                await callback_query.message.answer(
                    "❌ Siz hələ usta kimi qeydiyyatdan keçməmisiniz."
                )
                await callback_query.answer()
                await state.finish()
                return
            
            # Toggle active status in database
            success, new_status = toggle_artisan_active_status(artisan_id)
            
            if success:
                status_text = "aktiv" if new_status else "qeyri-aktiv"
                explanation = (
                    "Siz artıq müştərilərdən yeni sifarişlər qəbul edə bilərsiniz." 
                    if new_status else 
                    "Siz artıq müştərilərdən yeni sifarişlər qəbul etməyəcəksiniz. "
                    "Mövcud sifarişlərinizi tamamlaya bilərsiniz."
                )
                
                await callback_query.message.answer(
                    f"✅ Aktivlik statusunuz uğurla *{status_text}* olaraq dəyişdirildi!\n\n"
                    f"{explanation}",
                    parse_mode="Markdown"
                )
            else:
                await callback_query.message.answer(
                    "❌ Status dəyişdirildiyi zaman xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
            
            await callback_query.answer()
            
            # Əvvəlcə state'i təmizləyirik
            await state.finish()
            
            # Sonra menu funksiyasına ötürmək əvəzinə, birbaşa menyunu göstəririk
            # Burada show_artisan_menu(callback_query.message) əvəzinə, birbaşa funksiya kodunu yerinə yetiririk
            
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(KeyboardButton("📋 Aktiv sifarişlər"))
            keyboard.add(KeyboardButton("⭐ Rəylər"), KeyboardButton("📊 Statistika"))
            keyboard.add(KeyboardButton("💰 Qiymət ayarları"), KeyboardButton("⚙️ Profil ayarları"))
            keyboard.add(KeyboardButton("🔄 Rol seçiminə qayıt"))
                
            await callback_query.message.answer(
                "👷‍♂️ *Usta Paneli*\n\n"
                "Aşağıdakı əməliyyatlardan birini seçin:",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Error in toggle_artisan_active: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()
            await state.finish()
            
            # Xəta olduğu halda da usta menusuna qayıdaq
            await show_artisan_menu(callback_query.message)



    # Handler for "Price Settings" button
    @dp.message_handler(lambda message: message.text == "💰 Qiymət ayarları")
    async def price_settings(message: types.Message, state: FSMContext):
        """Show price settings for artisan"""
        try:
            # Get artisan ID
            telegram_id = message.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if not artisan_id:
                await message.answer(
                    "❌ Siz hələ usta kimi qeydiyyatdan keçməmisiniz."
                )
                return
            
            # Check if artisan is blocked
            is_blocked, reason, amount = get_artisan_blocked_status(artisan_id)
            if is_blocked:
                await message.answer(
                    f"⛔ Hesabınız bloklanıb. Qiymət ayarlarınızı dəyişmək üçün əvvəlcə bloku açın.\n"
                    f"Səbəb: {reason}\n"
                    f"Ödəniş məbləği: {amount} AZN\n"
                    f"Ödəniş etmək üçün: /pay_fine"
                )
                return
            
            # Get artisan price ranges
            price_ranges = get_artisan_price_ranges(artisan_id)
            
            # Get artisan service and its subservices
            artisan = get_artisan_by_id(artisan_id)
            service = artisan['service']
            subservices = get_subservices(service)
            
            if not subservices:
                await message.answer(
                    f"❌ '{service}' xidməti üçün alt xidmətlər tapılmadı. "
                    f"Zəhmət olmasa, administratorla əlaqə saxlayın."
                )
                return
            
            # Display current price ranges
            if price_ranges:
                await message.answer(
                    "💰 *Mövcud qiymət aralıqlarınız:*",
                    parse_mode="Markdown"
                )
                
                # Group price ranges by subservice
                for price_range in price_ranges:
                    subservice = price_range.get('subservice')
                    min_price = price_range.get('min_price')
                    max_price = price_range.get('max_price')
                    
                    await message.answer(
                        f"🔹 *{subservice}*: {min_price}-{max_price} AZN",
                        parse_mode="Markdown"
                    )
            else:
                await message.answer(
                    "ℹ️ Hələ heç bir qiymət aralığı təyin etməmisiniz. "
                    "Zəhmət olmasa, xidmət növləriniz üçün qiymət aralıqlarını təyin edin."
                )
            
            # Create keyboard for subservice selection
            keyboard = InlineKeyboardMarkup(row_width=1)
            
            for subservice in subservices:
                keyboard.add(InlineKeyboardButton(
                    f"🔸 {subservice}", 
                    callback_data=f"set_price_range_{subservice}"
                ))
            
            keyboard.add(InlineKeyboardButton("🔙 Geri", callback_data="back_to_artisan_menu"))
            
            await message.answer(
                "💰 *Qiymət aralığını təyin etmək istədiyiniz xidməti seçin:*",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            await ArtisanProfileStates.setting_price_ranges.set()
            
        except Exception as e:
            logger.error(f"Error in price_settings: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
    
    # Handler for setup price ranges button from registration completion
    @dp.callback_query_handler(lambda c: c.data == "setup_price_ranges")
    async def setup_price_ranges(callback_query: types.CallbackQuery, state: FSMContext):
        """Setup price ranges after registration"""
        try:
            # Get artisan ID
            telegram_id = callback_query.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if not artisan_id:
                await callback_query.message.answer(
                    "❌ Siz hələ usta kimi qeydiyyatdan keçməmisiniz."
                )
                await callback_query.answer()
                return
            
            # Get artisan service and its subservices
            artisan = get_artisan_by_id(artisan_id)
            service = artisan['service']
            subservices = get_subservices(service)
            
            if not subservices:
                await callback_query.message.answer(
                    f"❌ '{service}' xidməti üçün alt xidmətlər tapılmadı. "
                    f"Zəhmət olmasa, administratorla əlaqə saxlayın."
                )
                await callback_query.answer()
                return
            
            # Create keyboard for subservice selection
            keyboard = InlineKeyboardMarkup(row_width=1)
            
            for subservice in subservices:
                keyboard.add(InlineKeyboardButton(
                    f"🔸 {subservice}", 
                    callback_data=f"set_price_range_{subservice}"
                ))
            
            keyboard.add(InlineKeyboardButton("🔙 Geri", callback_data="back_to_menu"))
            
            await callback_query.message.answer(
                "💰 *Qiymət aralığını təyin etmək istədiyiniz xidməti seçin:*\n\n"
                "Hər bir alt xidmət üçün minimum və maksimum qiyməti təyin etməlisiniz. "
                "Bu, müştərilərə sizin qiymət aralığınız haqqında məlumat verəcək.",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            await ArtisanProfileStates.setting_price_ranges.set()
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in setup_price_ranges: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()
    
    # Handler for selecting subservice to set price range
    @dp.callback_query_handler(
    lambda c: c.data.startswith('set_price_range_'),
    state="*"  # Any state
    )
    async def set_price_range_for_subservice(callback_query: types.CallbackQuery, state: FSMContext):
        """Set price range for a specific subservice"""
        try:
            # Log callback data for debugging
            logger.info(f"Received callback: {callback_query.data}, Current state: {await state.get_state()}")
            
            # Extract subservice from callback data
            selected_subservice = callback_query.data.split('_', 3)[3]
            
            # Clear any previous state and set new one
            await state.finish()
            
            # Store subservice in state
            async with state.proxy() as data:
                data['subservice'] = selected_subservice
            
            # Check if price range already exists
            artisan_id = get_artisan_by_telegram_id(callback_query.from_user.id)
            existing_range = get_artisan_price_ranges(artisan_id, selected_subservice)
            
            info_text = ""
            if existing_range:
                info_text = (
                    f"\n\nMövcud qiymət aralığı: {existing_range['min_price']}-{existing_range['max_price']} AZN\n"
                    f"Yeni qiymət daxil etməklə bu aralığı dəyişə bilərsiniz."
                )
            
            await callback_query.message.answer(
                f"💰 *{selected_subservice}* xidməti üçün qiymət aralığını təyin edin.\n\n"
                f"Zəhmət olmasa, minimum və maksimum qiyməti AZN ilə vergül ilə ayıraraq daxil edin.\n"
                f"Məsələn: <code>30,80</code> - bu, 30 AZN minimum və 80 AZN maksimum qiymət deməkdir.{info_text}",
                parse_mode="HTML"
            )
            
            # Set the state for price entry
            await ArtisanProfileStates.setting_subservice_price.set()
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in set_price_range_for_subservice: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()
            await state.finish()
    
    # Handler for processing price range input
    @dp.message_handler(state=ArtisanProfileStates.setting_subservice_price)
    async def process_price_range(message: types.Message, state: FSMContext):

        try:
            # Get input and validate format
            price_text = message.text.strip()
            
            # Try to split by comma or dash
            if ',' in price_text:
                parts = price_text.split(',')
            elif '-' in price_text:
                parts = price_text.split('-')
            else:
                await message.answer(
                    "❌ Düzgün format deyil. Zəhmət olmasa, minimum və maksimum qiyməti vergül (,) və ya tire (-) ilə ayırın.\n"
                    "Məsələn: <code>30,80</code> və ya <code>30-80</code>",
                    parse_mode="HTML"
                )
                return
            
            if len(parts) != 2:
                await message.answer(
                    "❌ Düzgün format deyil. Zəhmət olmasa, minimum və maksimum qiyməti vergül (,) və ya tire (-) ilə ayırın.\n"
                    "Məsələn: <code>30,80</code> və ya <code>30-80</code>",
                    parse_mode="HTML"
                )
                return
            
            # Parse min and max prices
            try:
                min_price = float(parts[0].strip().replace(',', '.'))
                max_price = float(parts[1].strip().replace(',', '.'))
                
                if min_price <= 0 or max_price <= 0:
                    await message.answer("❌ Qiymətlər müsbət olmalıdır.")
                    return
                    
                if min_price >= max_price:
                    await message.answer("❌ Minimum qiymət maksimum qiymətdən kiçik olmalıdır.")
                    return
            except ValueError:
                await message.answer(
                    "❌ Düzgün rəqəm daxil edin. Zəhmət olmasa, minimum və maksimum qiyməti vergül (,) və ya tire (-) ilə ayırın.\n"
                    "Məsələn: <code>30,80</code> və ya <code>30-80</code>",
                    parse_mode="HTML"
                )
                return
            
            # Get artisan ID and subservice from state
            telegram_id = message.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            data = await state.get_data()
            subservice = data.get('subservice')
            
            if not subservice:
                await message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
                await state.finish()
                return
            
            # Update price range in database
            success = update_artisan_price_range(
                artisan_id=artisan_id,
                subservice=subservice,
                min_price=min_price,
                max_price=max_price
            )
            
            if success:
                await message.answer(
                    f"✅ *{subservice}* xidməti üçün qiymət aralığı uğurla təyin edildi:\n\n"
                    f"Minimum: {min_price:.2f} AZN\n"
                    f"Maksimum: {max_price:.2f} AZN",
                    parse_mode="Markdown"
                )
                
                # Ask if user wants to set more price ranges
                artisan = get_artisan_by_id(artisan_id)
                service = artisan['service']
                
                # Get all subservices for this service
                all_subservices = get_subservices(service)
                
                # Get all subservices that already have prices set
                price_ranges = get_artisan_price_ranges(artisan_id)
                already_set_subservices = [pr['subservice'] for pr in price_ranges]
                
                # Reset state first, then set to price range selection state
                await state.finish()
                await ArtisanProfileStates.setting_price_ranges.set()
                
                # Create keyboard for subservice selection
                keyboard = InlineKeyboardMarkup(row_width=1)
                
                # Only show subservices that don't already have prices set
                remaining_subservices = [
                    sub for sub in all_subservices 
                    if sub not in already_set_subservices and sub != subservice
                ]
                
                # Add buttons for remaining subservices
                for sub in remaining_subservices:
                    keyboard.add(InlineKeyboardButton(
                        f"🔸 {sub}", 
                        callback_data=f"set_price_range_{sub}"
                    ))
                
                # Always add Finish button
                keyboard.add(InlineKeyboardButton("✅ Bitir", callback_data="finish_price_setup"))
                
                if remaining_subservices:
                    await message.answer(
                        "💰 Digər alt xidmətlər üçün qiymət aralığı təyin etmək istəyirsiniz?",
                        reply_markup=keyboard
                    )
                else:
                    await message.answer(
                        "✅ Bütün qiymət aralıqları təyin edildi.",
                        reply_markup=InlineKeyboardMarkup().add(
                            InlineKeyboardButton("✅ Bitir", callback_data="finish_price_setup")
                        )
                    )
            else:
                await message.answer(
                    "❌ Qiymət aralığı təyin edilərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
            
        except Exception as e:
            logger.error(f"Error in process_price_range: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
    
    # Handler for finishing price setup
    @dp.callback_query_handler(lambda c: c.data == "finish_price_setup", state="*")
    async def finish_price_setup(callback_query: types.CallbackQuery, state: FSMContext):
        """Finish price range setup"""
        try:
            # Clear any active state
            current_state = await state.get_state()
            if current_state:
                await state.finish()
            
            await callback_query.message.answer(
                "✅ Qiymət aralıqlarının təyin edilməsi tamamlandı!\n\n"
                "Artıq müştərilər sizin xidmətlərinizi görə və sifariş verə bilərlər."
            )
            
            # Get artisan ID
            telegram_id = callback_query.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if not artisan_id:
                logger.error(f"Artisan ID not found for telegram_id: {telegram_id}")
                await callback_query.message.answer(
                    "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
                return
            
            # Check if this is a new registration based on timestamp
            conn = None
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                # Check when the artisan was created - if recent, consider it initial registration
                cursor.execute(
                    """
                    SELECT created_at, payment_card_number 
                    FROM artisans 
                    WHERE id = %s
                    """,
                    (artisan_id,)
                )
                result = cursor.fetchone()
                
                if not result:
                    raise Exception("Artisan not found in database")
                    
                created_at, payment_card_number = result
                
                # Calculate the time difference in minutes
                from datetime import datetime
                now = datetime.now()
                time_diff = (now - created_at).total_seconds() / 60
                
                # Consider it initial registration if created within the last 30 minutes
                is_initial_registration = time_diff < 30
                has_payment_info = payment_card_number and payment_card_number.strip()
                
            except Exception as e:
                logger.error(f"Database error checking registration status: {e}")
                # Default fallback values
                is_initial_registration = False
                has_payment_info = True
            finally:
                if conn:
                    conn.close()
            
            # For initial registration without payment info, redirect to payment setup
            if is_initial_registration and not has_payment_info:
                # Ask for payment information
                await callback_query.message.answer(
                    "💳 *Ödəniş məlumatlarının tənzimlənməsi*\n\n"
                    "Müştərilərdən kartla ödəniş qəbul etmək üçün kart məlumatlarınızı təqdim edin.\n\n"
                    "Zəhmət olmasa, kart nömrənizi daxil edin (məsələn: 4169 7388 5555 6666):",
                    parse_mode="Markdown"
                )
                
                await ArtisanProfileStates.entering_card_number.set()
                await callback_query.answer()
                return
                
            # Show main menu for non-initial registration or if card info exists
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(KeyboardButton("📋 Aktiv sifarişlər"))
            keyboard.add(KeyboardButton("⭐ Rəylər"), KeyboardButton("📊 Statistika"))
            keyboard.add(KeyboardButton("💰 Qiymət ayarları"), KeyboardButton("⚙️ Profil ayarları"))
            keyboard.add(KeyboardButton("🔄 Rol seçiminə qayıt"))
            
            await callback_query.message.answer(
                "👷‍♂️ *Usta Paneli*\n\n"
                "Aşağıdakı əməliyyatlardan birini seçin:",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in finish_price_setup: {e}", exc_info=True)
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            
            # Show artisan menu even on error
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(KeyboardButton("📋 Aktiv sifarişlər"))
            keyboard.add(KeyboardButton("⭐ Rəylər"), KeyboardButton("📊 Statistika"))
            keyboard.add(KeyboardButton("💰 Qiymət ayarları"), KeyboardButton("⚙️ Profil ayarları"))
            keyboard.add(KeyboardButton("🔄 Rol seçiminə qayıt"))
            
            await callback_query.message.answer(
                "👷‍♂️ *Usta Paneli*\n\n"
                "Aşağıdakı əməliyyatlardan birini seçin:",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            await callback_query.answer()
        
    @dp.callback_query_handler(lambda c: c.data.startswith('confirm_art_payment_'))
    async def confirm_art_payment(callback_query: types.CallbackQuery, state: FSMContext):
        """Confirm admin payment for cash orders"""
        try:
            # Extract order ID from callback data
            order_id = int(callback_query.data.split('_')[-1])
            
            # Save order ID to state
            await state.update_data(order_id=order_id)
            
            # Set state to waiting_for_receipt
            await AdminPaymentStates.waiting_for_receipt.set()
            
            # Ask for receipt
            await callback_query.message.answer(
                "📸 Zəhmət olmasa, admin karta etdiyiniz ödənişin qəbzini şəkil olaraq göndərin.\n\n"
                "Bu, ödənişin təsdiqlənməsi üçün lazımdır. Şəkil aydın və oxunaqlı olmalıdır."
            )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in confirm_art_payment: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()

    from aiogram.types import CallbackQuery

    @dp.callback_query_handler(lambda c: c.data.startswith('confirm_art_payment_'))
    async def confirm_artisan_commission_payment(callback_query: CallbackQuery):
        try:
            order_id = int(callback_query.data.split('_')[-1])
            user_id = callback_query.from_user.id

            from db import set_admin_payment_completed
            success = set_admin_payment_completed(order_id)

            if success:
                await callback_query.answer("✅ Komissiya ödənişi uğurla təsdiqləndi.", show_alert=True)
                await callback_query.message.edit_reply_markup(reply_markup=None)
                await callback_query.message.answer("Təşəkkür edirik! Komissiya ödənişiniz təsdiqləndi.")
            else:
                await callback_query.answer("❌ Xəta baş verdi. Zəhmət olmasa yenidən cəhd edin.", show_alert=True)

        except Exception as e:
            logging.error(f"Xəta: confirm_artisan_commission_payment: {e}")
            await callback_query.answer("❌ Gözlənilməz xəta baş verdi.", show_alert=True)


    # Photo handler for admin payment receipt
    @dp.message_handler(content_types=types.ContentType.PHOTO, state=AdminPaymentStates.waiting_for_receipt)
    async def handle_admin_payment_receipt(message: types.Message, state: FSMContext):
        """Handle admin payment receipt photo"""
        try:
            # Get data from state
            state_data = await state.get_data()
            order_id = state_data.get('order_id')
            
            if not order_id:
                logger.error("No order_id found in state")
                await message.answer("❌ Məlumat tapılmadı. Zəhmət olmasa yenidən cəhd edin.")
                await state.finish()
                return
            
            logger.info(f"Processing admin payment receipt for order {order_id}")
            
            # Get highest quality photo
            photo = message.photo[-1]
            file_id = photo.file_id
            
            # Direct database update
            conn = None
            success = False
            
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                # Update order_payments table
                cursor.execute(
                    """
                    UPDATE order_payments 
                    SET receipt_file_id = %s,
                        receipt_uploaded_at = CURRENT_TIMESTAMP,
                        payment_status = 'completed',
                        payment_date = CURRENT_TIMESTAMP,
                        admin_payment_completed = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE order_id = %s
                    RETURNING id
                    """,
                    (file_id, order_id)
                )
                
                result = cursor.fetchone()
                if result:
                    logger.info(f"Successfully updated order_payments for order {order_id}")
                    success = True
                else:
                    # No existing record, try insert
                    cursor.execute(
                        """
                        INSERT INTO order_payments 
                        (order_id, receipt_file_id, receipt_uploaded_at, payment_status, 
                        payment_date, admin_payment_completed, created_at)
                        VALUES (%s, %s, CURRENT_TIMESTAMP, 'completed', 
                                CURRENT_TIMESTAMP, NULL, CURRENT_TIMESTAMP) /* Değişen satır: TRUE -> NULL */
                        ON CONFLICT (order_id) DO UPDATE 
                        SET receipt_file_id = EXCLUDED.receipt_file_id,
                            receipt_uploaded_at = EXCLUDED.receipt_uploaded_at,
                            payment_status = EXCLUDED.payment_status,
                            payment_date = EXCLUDED.payment_date,
                            admin_payment_completed = EXCLUDED.admin_payment_completed
                        RETURNING id
                        """,
                        (order_id, file_id)
                    )
                    
                    result = cursor.fetchone()
                    if result:
                        logger.info(f"Successfully inserted/updated order_payments for order {order_id}")
                        success = True
                    else:
                        logger.error(f"Failed to update or insert payment record for order {order_id}")
                    
                conn.commit()
            except Exception as db_error:
                logger.error(f"Database error: {db_error}", exc_info=True)
                if conn:
                    conn.rollback()
            finally:
                if conn:
                    conn.close()
            
            # Send confirmation message
            if success:
                await message.answer(
                    "✅ Komissiya ödənişinin qəbzi uğurla yükləndi!\n\n"
                    "Qəbzi aldıq. Əgər ödənişiniz təsdiq olunmazsa, bununla bağlı sizə xəbərdarlıq göndəriləcək.",
                    reply_markup=types.ReplyKeyboardRemove()
                )
                
                # Notify admins if needed
                try:
                    for admin_id in BOT_ADMINS:
                        await bot.send_photo(
                            chat_id=admin_id,
                            photo=file_id,
                            caption=f"💰 *Yeni komissiya ödənişi*\n\n"
                                f"Usta: {message.from_user.id}\n"
                                f"Sifariş: #{order_id}\n\n"
                                f"Zəhmət olmasa yoxlayın və təsdiqləyin.",
                            parse_mode="Markdown"
                        )
                except Exception as admin_error:
                    logger.error(f"Error notifying admin: {admin_error}")
            else:
                await message.answer(
                    "⚠️ Qəbzin yüklənməsi zamanı texniki problem yaşandı, amma şəkli aldıq.\n"
                    "Administratorlar şəkli manuel yolla qeydə alacaqlar.",
                    reply_markup=types.ReplyKeyboardRemove()
                )
            
            # Clear state and show menu
            await state.finish()
            await show_artisan_menu(message)
            
        except Exception as e:
            logger.error(f"Error in handle_admin_payment_receipt: {e}", exc_info=True)
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_artisan_menu(message)
    
    # Handler for payment receipt upload
    @dp.message_handler(content_types=types.ContentType.PHOTO)
    async def handle_receipt_photo(message: types.Message):
        """Process uploaded photos (payment receipts, etc.)"""
        try:
            telegram_id = message.from_user.id
            
            # Get user context
            context = get_user_context(telegram_id)
            
            if not context or not context.get('action'):
                # No context requiring photo, ignore
                return
            
            logger.info(f"Photo upload detected with context: {context}")
            action = context.get('action')
            
            # Unified handling for both admin payment contexts
            
            # Handling for admin commission receipt
            if action == 'admin_commission_receipt':
                order_id = context.get('order_id')
                
                if not order_id:
                    logger.error(f"Missing order_id in context for user {telegram_id}")
                    await message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
                    return
                
                # Log the action
                logger.info(f"Processing new commission receipt for order {order_id}")
                
                # Get the highest quality photo
                photo = message.photo[-1]
                file_id = photo.file_id
                
                # Get artisan ID
                artisan_id = get_artisan_by_telegram_id(telegram_id)
                if not artisan_id:
                    await message.answer("❌ Usta məlumatları tapılmadı.")
                    return
                
                # Get current order details
                order = get_order_details(order_id)
                if not order:
                    await message.answer("❌ Sifariş məlumatları tapılmadı.")
                    return
                
                # Update receipt in database
                conn = None
                success = False
                
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    # Update order_payments record with new receipt
                    cursor.execute(
                        """
                        UPDATE order_payments 
                        SET receipt_file_id = %s,
                            receipt_uploaded_at = CURRENT_TIMESTAMP,
                            receipt_verified = FALSE, 
                            payment_status = 'pending',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE order_id = %s
                        RETURNING id
                        """,
                        (file_id, order_id)
                    )
                    
                    result = cursor.fetchone()
                    
                    if result:
                        # Add entry to receipt_verification_history 
                        cursor.execute(
                            """
                            INSERT INTO receipt_verification_history 
                            (order_id, is_verified, attempt_number, verified_at)
                            VALUES (%s, NULL, (
                                SELECT COALESCE(MAX(attempt_number), 0) + 1 
                                FROM receipt_verification_history 
                                WHERE order_id = %s
                            ), CURRENT_TIMESTAMP)
                            """,
                            (order_id, order_id)
                        )
                        
                        # Clear scheduled block if any (by updating notification_log)
                        cursor.execute(
                            """
                            INSERT INTO notification_log (notification_type, target_id, created_at)
                            VALUES ('commission_resubmitted', %s, CURRENT_TIMESTAMP)
                            """,
                            (order_id,)
                        )
                        
                        success = True
                    
                    conn.commit()
                except Exception as db_error:
                    logger.error(f"Database error in handle_receipt_photo: {db_error}")
                    if conn:
                        conn.rollback()
                finally:
                    if conn:
                        conn.close()
                
                if success:
                    # Send confirmation to artisan
                    await message.answer(
                        "✅ Komissiya qəbzi uğurla göndərildi!\n\n"
                        "Qəbziniz yoxlanma üçün admin heyətinə göndərildi. "
                        "Bloklanma prosesi dayandırıldı, ancaq qəbzin təsdiqlənməsi lazımdır.",
                        reply_markup=types.ReplyKeyboardRemove()
                    )
                    
                    # Send detailed notification to artisan
                    await notify_artisan_commission_receipt_received(artisan_id, order_id)
                    
                    # Notify admins for review
                    for admin_id in BOT_ADMINS:
                        try:
                            await bot.send_photo(
                                chat_id=admin_id,
                                photo=file_id,
                                caption=f"🔄 *Yenidən göndərilmiş komissiya qəbzi*\n\n"
                                    f"Sifariş: #{order_id}\n"
                                    f"Usta ID: {artisan_id}\n\n"
                                    f"Bu qəbz yenidən yoxlanmalıdır. Əvvəlki qəbz rədd edilmişdi.",
                                reply_markup=InlineKeyboardMarkup().add(
                                    InlineKeyboardButton("✅ Təsdiqlə", callback_data=f"verify_receipt_{order_id}_true"),
                                    InlineKeyboardButton("❌ Rədd et", callback_data=f"verify_receipt_{order_id}_false")
                                ),
                                parse_mode="Markdown"
                            )
                        except Exception as admin_error:
                            logger.error(f"Error notifying admin {admin_id}: {admin_error}")
                    
                    # Clear user context
                    clear_user_context(telegram_id)
                else:
                    await message.answer(
                        "❌ Qəbz göndərilərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                    )
            
            elif action == 'order_admin_payment':
                order_id = context.get('order_id')
                
                if not order_id:
                    logger.error(f"Missing order_id in context for user {telegram_id}")
                    await message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
                    return
                
                # Add additional logging
                logger.info(f"Processing receipt for order {order_id} with action {action}")
                
                # Get the highest quality photo
                photo = message.photo[-1]
                file_id = photo.file_id
                
                # Save receipt to database with error checking
                success = save_payment_receipt(order_id, file_id)
                
                if success:
                    # Verify receipt was actually saved
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT receipt_file_id FROM order_payments WHERE order_id = %s", (order_id,))
                    receipt_check = cursor.fetchone()
                    conn.close()
                    
                    if not receipt_check or not receipt_check[0]:
                        logger.error(f"Receipt appears to be saved but not found in database for order {order_id}")
                        # Try alternative update method
                        conn = get_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            """
                            UPDATE order_payments 
                            SET receipt_file_id = %s,
                                receipt_uploaded_at = CURRENT_TIMESTAMP,
                                payment_status = 'completed',
                                payment_date = CURRENT_TIMESTAMP,
                                admin_payment_completed = NULL,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE order_id = %s
                            """,
                            (file_id, order_id)
                        )
                        conn.commit()
                        conn.close()
                    
                    # Clear user context
                    clear_user_context(telegram_id)
                    
                    # Mark order as completed
                    update_order_status(order_id, "completed")
                    
                    # Final verification
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT receipt_file_id FROM order_payments WHERE order_id = %s", 
                        (order_id,)
                    )
                    final_check = cursor.fetchone()
                    conn.close()
                    
                    if final_check and final_check[0]:
                        await message.answer(
                            "✅ Admin ödənişinin qəbzi uğurla yükləndi!\n\n"
                            "Admin ödənişi təsdiqləndi. Təşəkkür edirik!",
                            reply_markup=types.ReplyKeyboardRemove()
                        )
                        
                        # Restore main menu
                        await show_artisan_menu(message)
                    else:
                        # If verification failed, attempt direct update one last time
                        conn = get_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE order_payments SET receipt_file_id = %s, receipt_uploaded_at = CURRENT_TIMESTAMP WHERE order_id = %s",
                            (file_id, order_id)
                        )
                        conn.commit()
                        conn.close()
                        
                        await message.answer(
                            "⚠️ Qəbzin yüklənməsi zamanı bəzi problemlər yarandı, lakin biz qeyd etdik.\n"
                            "Admin ödənişi qeydə alındı. Təşəkkür edirik!",
                            reply_markup=types.ReplyKeyboardRemove()
                        )
                        
                        # Restore main menu
                        await show_artisan_menu(message)
                        
                    # Notify admins if needed
                    try:
                        for admin_id in BOT_ADMINS:
                            await bot.send_photo(
                                chat_id=admin_id,
                                photo=file_id,
                                caption=f"💰 *Yeni komissiya ödənişi*\n\n"
                                    f"Usta: {telegram_id}\n"
                                    f"Sifariş: #{order_id}\n\n"
                                    f"Zəhmət olmasa yoxlayın və təsdiqləyin.",
                                parse_mode="Markdown"
                            )
                    except Exception as admin_error:
                        logger.error(f"Error notifying admin: {admin_error}")
                else:
                    logger.error(f"Failed to save payment receipt for order {order_id}")
                    
                    # Try a direct database update as last resort
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            """
                            UPDATE order_payments 
                            SET receipt_file_id = %s,
                                receipt_uploaded_at = CURRENT_TIMESTAMP,
                                payment_status = 'completed',
                                payment_date = CURRENT_TIMESTAMP,
                                admin_payment_completed = NULL
                            WHERE order_id = %s
                            """,
                            (file_id, order_id)
                        )
                        rows_updated = cursor.rowcount
                        conn.commit()
                        
                        if rows_updated > 0:
                            logger.info(f"Direct update succeeded for order {order_id}")
                            await message.answer(
                                "✅ Qəbz yükləndi!\n\n"
                                "Admin ödənişi qeydə alındı. Təşəkkür edirik!",
                                reply_markup=types.ReplyKeyboardRemove()
                            )
                            # Clear context and restore menu
                            clear_user_context(telegram_id)
                            await show_artisan_menu(message)
                            return
                    except Exception as db_error:
                        logger.error(f"Direct database update failed: {db_error}")
                    
                    await message.answer(
                        "❌ Qəbz yüklənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                    )
                    # Restore main menu to prevent UI getting stuck
                    await show_artisan_menu(message)
                    
            elif action == 'card_payment_receipt':
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
                            # Send notification to artisan with receipt
                            await bot.send_photo(
                                chat_id=artisan['telegram_id'],
                                photo=file_id,
                                caption=f"💳 *Ödəniş qəbzi*\n\n"
                                        f"Sifariş #{order_id} üçün müştəri ödəniş qəbzini göndərdi.\n"
                                        f"Ödəniş 24 saat ərzində hesabınıza köçürüləcək.",
                                parse_mode="Markdown"
                            )
                else:
                    # Try a direct update
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        UPDATE order_payments 
                        SET receipt_file_id = %s,
                            receipt_uploaded_at = CURRENT_TIMESTAMP,
                            payment_status = 'completed',
                            payment_date = CURRENT_TIMESTAMP
                        WHERE order_id = %s
                        """,
                        (file_id, order_id)
                    )
                    direct_success = cursor.rowcount > 0
                    conn.commit()
                    conn.close()
                    
                    if direct_success:
                        # Clear user context
                        clear_user_context(telegram_id)
                        
                        # Mark order as completed
                        update_order_status(order_id, "completed")
                        
                        await message.answer(
                            "✅ Ödəniş qəbzi uğurla yükləndi!\n\n"
                            "Sifarişiniz tamamlandı. Təşəkkür edirik!",
                            reply_markup=types.ReplyKeyboardRemove()
                        )
                    else:
                        await message.answer(
                            "❌ Qəbz yüklənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                        )
                    
            elif action == 'fine_payment':
                # Handle fine payment receipt
                artisan_id = get_artisan_by_telegram_id(telegram_id)
                
                if not artisan_id:
                    await message.answer("❌ Hesabınız tapılmadı. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
                    return
                
                # Get the highest quality photo
                photo = message.photo[-1]
                file_id = photo.file_id
                
                # Save fine receipt to database
                success = save_fine_receipt(artisan_id, file_id)
                
                if success:
                    await message.answer(
                        "✅ Cərimə ödənişinin qəbzi uğurla yükləndi!\n\n"
                        "Qəbz yoxlanıldıqdan sonra hesabınız blokdan çıxarılacaq. "
                        "Bu, adətən 24 saat ərzində baş verir.",
                        reply_markup=types.ReplyKeyboardRemove()
                    )
                    
                    # Clear user context
                    clear_user_context(telegram_id)
                    
                    # Restore main menu
                    await show_artisan_menu(message)
                else:
                    await message.answer(
                        "❌ Qəbz yüklənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                    )
                    # Restore main menu to prevent UI getting stuck
                    await show_artisan_menu(message)
            
        except Exception as e:
            logger.error(f"Error in handle_receipt_photo: {e}", exc_info=True)
            # Log detailed error for debugging
            import traceback
            logger.error(traceback.format_exc())
            
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            # Always show the main menu if there's an error to prevent UI getting stuck
            try:
                await show_artisan_menu(message)
            except Exception as menu_error:
                logger.error(f"Error showing menu after receipt handling error: {menu_error}")
    
    # Handler for the /pay_fine command
    @dp.message_handler(commands=['pay_fine'])
    async def pay_fine_command(message: types.Message):
        """Handle the pay_fine command for blocked artisans"""
        try:
            telegram_id = message.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if not artisan_id:
                await message.answer(
                    "❌ Siz hələ usta kimi qeydiyyatdan keçməmisiniz."
                )
                return
                
            # Check if artisan is blocked
            is_blocked, reason, amount = get_artisan_blocked_status(artisan_id)
            
            if not is_blocked:
                await message.answer(
                    "✅ Sizin hesabınız bloklanmayıb. Normalde istifadə edə bilərsiniz."
                )
                return
                
            # Show payment instructions
            await message.answer(
                f"💰 *Cərimə ödənişi*\n\n"
                f"Hesabınız aşağıdakı səbəbə görə bloklanıb:\n"
                f"*Səbəb:* {reason}\n\n"
                f"Bloku açmaq üçün {amount} AZN ödəniş etməlisiniz.\n\n"
                f"*Ödəniş təlimatları:*\n"
                f"1. Bu karta ödəniş edin: 4169 7388 5555 6666 (USTABOT LLC)\n"
                f"2. Ödəniş qəbzini saxlayın (şəkil çəkin)\n"
                f"3. Qəbzi göndərmək üçün aşağıdakı düyməni basın\n\n"
                f"⚠️ Qeyd: Ödəniş qəbzi yoxlanıldıqdan sonra hesabınız blokdan çıxarılacaq.",
                parse_mode="Markdown"
            )
            
            # Add button to send receipt
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton(
                "📸 Ödəniş qəbzini göndər", callback_data="send_fine_receipt"
            ))
            
            await message.answer(
                "Ödənişi tamamladıqdan sonra, qəbzi göndərmək üçün bu düyməni basın:",
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"Error in pay_fine_command: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
    
    # Handler for the send fine receipt button
    @dp.callback_query_handler(lambda c: c.data == "send_fine_receipt")
    async def send_fine_receipt(callback_query: types.CallbackQuery):
        """Handle fine receipt upload request"""
        try:
            telegram_id = callback_query.from_user.id
            
            # Set context for receipt upload
            context_data = {
                "action": "fine_payment"
            }
            
            set_user_context(telegram_id, context_data)
            
            await callback_query.message.answer(
                "📸 Zəhmət olmasa, ödəniş qəbzinin şəklini göndərin.\n\n"
                "Şəkil aydın və oxunaqlı olmalıdır. Ödəniş məbləği, tarix və kart məlumatları görünməlidir."
            )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in send_fine_receipt: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()
    
    # Handler for "Back" button in profile or price settings
    @dp.callback_query_handler(lambda c: c.data == "back_to_profile", state="*")
    async def back_to_profile(callback_query: types.CallbackQuery, state: FSMContext):
        """Go back to profile settings"""
        try:
            current_state = await state.get_state()
            if current_state:
                await state.finish()
            
            await profile_settings(callback_query.message, state)
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in back_to_profile: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()
            await state.finish()
            await show_artisan_menu(callback_query.message)
    
    @dp.callback_query_handler(lambda c: c.data == "back_to_artisan_menu", state="*")
    async def back_to_artisan_menu(callback_query: types.CallbackQuery, state: FSMContext):
        """Return to artisan menu"""
        try:
            current_state = await state.get_state()
            if current_state:
                await state.finish()
            
            # Birbaşa usta menyusuna qayıdırıq
            await show_artisan_menu(callback_query.message)
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in back_to_artisan_menu: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_artisan_menu(callback_query.message)



    # Handler for returning to menu
    @dp.callback_query_handler(lambda c: c.data == "back_to_menu", state="*")
    async def back_to_menu_handler(callback_query: types.CallbackQuery, state: FSMContext):
        """Handle back to menu button from any state"""
        try:
            current_state = await state.get_state()
            if current_state:
                await state.finish()
            
            # İstifadəçinin rolunu yoxlayırıq - artisan_id varsa, usta menyusuna qayıt
            telegram_id = callback_query.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if artisan_id:
                # Usta kimi qeydiyyatlıdır, usta menyusuna qayıt
                await show_artisan_menu(callback_query.message)
            else:
                # Usta kimi qeydiyyatlı deyil, customer menyusuna qayıt
                await show_customer_menu(callback_query.message)
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in back_to_menu_handler: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_artisan_menu(callback_query.message)

    @dp.callback_query_handler(lambda c: c.data == "setup_payment_info", state="*")
    async def setup_payment_info(callback_query: types.CallbackQuery, state: FSMContext):
        """Setup payment card information"""
        try:
            # Clear any active state
            current_state = await state.get_state()
            if current_state:
                await state.finish()
            
            await callback_query.message.answer(
                "💳 *Ödəniş məlumatlarının tənzimlənməsi*\n\n"
                "Müştərilərdən kartla ödəniş qəbul etmək üçün kart məlumatlarınızı təqdim edin.\n\n"
                "Zəhmət olmasa, kart nömrənizi daxil edin (məsələn: 4169 7388 5555 6666):",
                parse_mode="Markdown"
            )
            
            await ArtisanProfileStates.entering_card_number.set()
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in setup_payment_info: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()
            await state.finish()
            await show_artisan_menu(callback_query.message)


    # Handler for entering card number
    @dp.message_handler(state=ArtisanProfileStates.entering_card_number)
    async def process_card_number(message: types.Message, state: FSMContext):
        """Process card number input"""
        try:
            card_number = message.text.strip()
            
            # Simple validation: make sure it's 16-19 digits, possibly with spaces
            card_number_clean = card_number.replace(' ', '')
            if not card_number_clean.isdigit() or not (16 <= len(card_number_clean) <= 19):
                await message.answer(
                    "❌ Düzgün kart nömrəsi daxil edin (16-19 rəqəm). "
                    "Məsələn: 4169 7388 5555 6666"
                )
                return
            
            # Store card number in state
            async with state.proxy() as data:
                data['card_number'] = card_number
            
            # Ask for card holder name
            await message.answer(
                "👤 İndi isə kart sahibinin adını daxil edin (Ad Soyad şəklində):"
            )
            
            await ArtisanProfileStates.entering_card_holder.set()
            
        except Exception as e:
            logger.error(f"Error in process_card_number: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_artisan_menu(message)


    # Handler for entering card holder name
    @dp.message_handler(state=ArtisanProfileStates.entering_card_holder)
    async def process_card_holder(message: types.Message, state: FSMContext):
        """Process card holder name input"""
        try:
            card_holder = message.text.strip()
            
            # Simple validation: make sure it's at least 5 characters
            if len(card_holder) < 5:
                await message.answer(
                    "❌ Kart sahibinin tam adını daxil edin (Ad Soyad şəklində)."
                )
                return
            
            # Get data from state
            data = await state.get_data()
            card_number = data.get('card_number')
            
            if not card_number:
                await message.answer(
                    "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
                await state.finish()
                await show_artisan_menu(message)
                return
            
            # Get artisan ID
            telegram_id = message.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if not artisan_id:
                await message.answer(
                    "❌ Siz hələ usta kimi qeydiyyatdan keçməmisiniz."
                )
                await state.finish()
                return
            
            # Update artisan information in database
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE artisans 
                SET payment_card_number = %s, 
                    payment_card_holder = %s
                WHERE id = %s
                """,
                (card_number, card_holder, artisan_id)
            )
            conn.commit()
            conn.close()
            
            await message.answer(
                "✅ Ödəniş məlumatlarınız uğurla qeydə alındı!\n\n"
                f"Kart nömrəsi: {card_number}\n"
                f"Kart sahibi: {card_holder}\n\n"
                "İndi müştərilər sizdən sifariş verərkən kartla ödəniş edə bilərlər.",
                reply_markup=types.ReplyKeyboardRemove()
            )
            
            # Return to main menu
            await state.finish()
            await show_artisan_menu(message)
            
        except Exception as e:
            logger.error(f"Error in process_card_holder: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_artisan_menu(message)


    # Handler for "Reviews" button
    @dp.message_handler(lambda message: message.text == "⭐ Rəylər")
    async def view_reviews(message: types.Message):
        """Show reviews for the artisan"""
        try:
            # Get artisan ID
            telegram_id = message.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if not artisan_id:
                await message.answer(
                    "❌ Siz hələ usta kimi qeydiyyatdan keçməmisiniz."
                )
                return
            
            # Check if artisan is blocked
            is_blocked, reason, amount = get_artisan_blocked_status(artisan_id)
            if is_blocked:
                await message.answer(
                    f"⛔ Hesabınız bloklanıb. Rəylərinizi görmək üçün əvvəlcə bloku açın.\n"
                    f"Səbəb: {reason}\n"
                    f"Ödəniş məbləği: {amount} AZN\n"
                    f"Ödəniş etmək üçün: /pay_fine"
                )
                return
            
            # Get reviews
            reviews = get_artisan_reviews(artisan_id)
            
            if not reviews:
                await message.answer(
                    "📭 Hal-hazırda heç bir rəyiniz yoxdur.\n\n"
                    "Rəylər sifarişlər tamamlandıqdan sonra müştərilər tərəfindən verilir. "
                    "Xidmətinizi yaxşılaşdırmaq üçün müştəriləri rəy verməyə həvəsləndirin."
                )
                return
            
            await message.answer(
                f"⭐ *Rəylər ({len(reviews)}):*",
                parse_mode="Markdown"
            )
            
            # Display each review
            for review in reviews:
                # Ensure review is a dictionary
                if isinstance(review, dict):
                    review_id = review.get('id')
                    rating = review.get('rating')
                    comment = review.get('comment')
                    customer_name = review.get('customer_name')
                    service = review.get('service')
                else:
                    # If it's a tuple (old implementation), extract values
                    review_id = review[0]
                    rating = review[4]
                    comment = review[5]
                    customer_name = review[7] 
                    service = review[8]
                
                # Create star rating display
                stars = "⭐" * rating if rating else ""
                
                review_text = (
                    f"📝 *Rəy #{review_id}*\n"
                    f"👤 *Müştəri:* {customer_name}\n"
                    f"🛠 *Xidmət:* {service}\n"
                    f"⭐ *Qiymətləndirmə:* {stars} ({rating}/5)\n"
                )
                
                if comment:
                    review_text += f"💬 *Şərh:* {comment}\n"
                
                await message.answer(
                    review_text,
                    parse_mode="Markdown"
                )
            
            avg_rating = get_artisan_average_rating(artisan_id)
        
            if avg_rating:
                avg_stars = "⭐" * round(avg_rating)
                await message.answer(
                    f"📊 *Ümumi qiymətləndirməniz:* {avg_stars} ({avg_rating:.1f}/5)\n\n"
                    f"Yaxşı rəylər müştərilərin sizi seçməsinə kömək edir. Xidmətinizi yüksək səviyyədə "
                    f"saxlayın və müştəriləri rəy verməyə həvəsləndirin!",
                    parse_mode="Markdown"
                )
        
        except Exception as e:
            logger.error(f"Error in view_reviews: {e}")
            await message.answer(
                "❌ Rəylər yüklənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )


    # Handler for "Active Orders" button
    @dp.message_handler(lambda message: message.text == "📋 Aktiv sifarişlər")
    async def view_active_orders(message: types.Message):
        """Show active orders for the artisan"""
        try:
            # Get artisan ID
            telegram_id = message.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if not artisan_id:
                await message.answer(
                    "❌ Siz hələ usta kimi qeydiyyatdan keçməmisiniz."
                )
                return
            
            # Check if artisan is blocked
            is_blocked, reason, amount = get_artisan_blocked_status(artisan_id)
            if is_blocked:
                await message.answer(
                    f"⛔ Hesabınız bloklanıb. Sifarişlərinizi görmək üçün əvvəlcə bloku açın.\n"
                    f"Səbəb: {reason}\n"
                    f"Ödəniş məbləği: {amount} AZN\n"
                    f"Ödəniş etmək üçün: /pay_fine"
                )
                return
            
            # Get active orders
            orders = get_artisan_active_orders(artisan_id)
            
            if not orders:
                await message.answer(
                    "📭 Hal-hazırda heç bir aktiv sifarişiniz yoxdur."
                )
                return
            
            await message.answer(
                f"📋 *Aktiv sifarişlər ({len(orders)}):*",
                parse_mode="Markdown"
            )
            
            # Display each order
            for order in orders:
                # Ensure order is a dictionary
                if isinstance(order, dict):
                    order_id = order.get('id')
                    customer_id = order.get('customer_id')
                    service = order.get('service')
                    subservice = order.get('subservice', '')
                    date_time = order.get('date_time')
                    note = order.get('note')
                    latitude = order.get('latitude')
                    longitude = order.get('longitude')
                    customer_name = order.get('customer_name')
                    customer_phone = order.get('customer_phone')
                else:
                    # If it's a tuple (old implementation), extract values
                    order_id = order[0]
                    customer_id = order[1]
                    service = order[3]
                    subservice = order.get('subservice', '')
                    date_time = order[4]
                    note = order[5]
                    latitude = order[6]
                    longitude = order[7]
                    customer_name = order[8]
                    customer_phone = order[9]
                
                # Format date and time
                try:
                    import datetime
                    dt_obj = datetime.datetime.strptime(str(date_time), "%Y-%m-%d %H:%M:%S")
                    formatted_date = dt_obj.strftime("%d.%m.%Y")
                    formatted_time = dt_obj.strftime("%H:%M")
                except Exception as e:
                    logger.error(f"Error formatting date: {e}")
                    formatted_date = str(date_time).split(" ")[0]
                    formatted_time = str(date_time).split(" ")[1] if " " in str(date_time) else ""
                
                # Build service text with subservice if available
                service_text = service
                if subservice:
                    service_text += f" ({subservice})"
                
                order_text = (
                    f"🔹 *Sifariş #{order_id}*\n"
                    f"👤 *Müştəri:* {customer_name}\n"
                    f"📞 *Əlaqə:* {customer_phone}\n"
                    f"🛠 *Xidmət:* {service_text}\n"
                    f"📅 *Tarix:* {formatted_date}\n"
                    f"🕒 *Saat:* {formatted_time}\n"
                    f"📝 *Qeyd:* {note}\n"
                )
                
                # Add action buttons
                keyboard = InlineKeyboardMarkup(row_width=1)
                keyboard.add(
                    InlineKeyboardButton("📍 Yeri göstər", callback_data=f"show_location_{order_id}"),
                    InlineKeyboardButton("💰 Qiymət təyin et", callback_data=f"set_price_{order_id}"),
                    InlineKeyboardButton("✅ Sifarişi tamamla", callback_data=f"complete_order_{order_id}"),
                    InlineKeyboardButton("❌ Sifarişi ləğv et", callback_data=f"cancel_order_{order_id}")
                )
                
                await message.answer(
                    order_text,
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
            
        except Exception as e:
            logger.error(f"Error in view_active_orders: {e}")
            await message.answer(
                "❌ Sifarişlər yüklənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )


    # Və "Rol seçiminə qayıt" düyməsi üçün handler əlavə edirik
    @dp.message_handler(lambda message: message.text == "🔄 Rol seçiminə qayıt")
    async def return_to_role_selection(message: types.Message, state: FSMContext):
        """Return to role selection menu"""
        try:
            # Clear any active state
            current_state = await state.get_state()
            if current_state:
                await state.finish()
            
            # Return to role selection menu
            await show_role_selection(message)
            
        except Exception as e:
            logger.error(f"Error in return_to_role_selection: {e}")
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_role_selection(message)


    @dp.callback_query_handler(lambda c: c.data.startswith('accept_order_'))
    async def accept_order(callback_query: types.CallbackQuery, state: FSMContext):
        """Ustanın siparişi kabul etmesini işler"""
        try:
            # Extract order ID from callback data
            order_id = int(callback_query.data.split('_')[-1])
            
            # Get order details
            order = get_order_details(order_id)
            
            if not order:
                await callback_query.message.answer(
                    "❌ Sifariş tapılmadı. Silinmiş və ya ləğv edilmiş ola bilər."
                )
                try:
                    await callback_query.answer()
                except Exception as e:
                    logger.warning(f"Could not answer callback query: {e}")
                return
            
            # Get artisan ID
            telegram_id = callback_query.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if not artisan_id:
                await callback_query.message.answer(
                    "❌ Siz hələ usta kimi qeydiyyatdan keçməmisiniz."
                )
                try:
                    await callback_query.answer()
                except Exception as e:
                    logger.warning(f"Could not answer callback query: {e}")
                return
            
            # Check if the order is assigned to this artisan
            if order['artisan_id'] != artisan_id:
                await callback_query.message.answer(
                    "❌ Bu sifariş sizə təyin edilməyib."
                )
                try:
                    await callback_query.answer()
                except Exception as e:
                    logger.warning(f"Could not answer callback query: {e}")
                return
            
            # Check if the order is still pending
            if order['status'] != 'pending':
                await callback_query.message.answer(
                    f"❌ Bu sifariş artıq '{order['status']}' statusundadır və dəyişdirilə bilməz."
                )
                try:
                    await callback_query.answer()
                except Exception as e:
                    logger.warning(f"Could not answer callback query: {e}")
                return
            
            # Update order status to "accepted" in database
            logger.info(f"Updating order {order_id} status to: accepted")
            success = update_order_status(order_id, "accepted")
            
            if success:
                # Import notification service
                from notification_service import notify_customer_about_order_status
                
                # Notify customer that the order has been accepted
                await notify_customer_about_order_status(order_id, "accepted")
                
                # Send confirmation to the artisan
                customer_info = get_customer_by_id(order['customer_id'])
                customer_name = customer_info.get('name', 'Müştəri')
                customer_phone = customer_info.get('phone', 'Telefon məlumatı yoxdur')
                
                await callback_query.message.answer(
                    f"✅ Sifariş #{order_id} uğurla qəbul edildi!\n\n"
                    f"👤 *Müştəri:* {customer_name}\n"
                    f"📞 *Telefon:* {customer_phone}\n\n"
                    f"Zəhmət olmasa, müştəri ilə əlaqə saxlayın və sifarişin detallarını dəqiqləşdirin.",
                    parse_mode="Markdown"
                )
                
                # Schedule arrival checks based on the order date/time
                from order_status_service import schedule_arrival_check
                
                # Get order date/time
                date_time = order['date_time']
                try:
                    import datetime
                    # Convert date_time to a string if it's a datetime object
                    if isinstance(date_time, datetime.datetime):
                        date_time_str = date_time.strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        date_time_str = str(date_time)
                    
                    dt_obj = datetime.datetime.strptime(date_time_str, "%Y-%m-%d %H:%M:%S")
                    formatted_date = dt_obj.strftime("%d.%m.%Y")
                    formatted_time = dt_obj.strftime("%H:%M")
                    
                    # Execute in a separate task to avoid blocking
                    asyncio.create_task(schedule_arrival_check(order_id, artisan_id, date_time_str))
                    
                    await callback_query.message.answer(
                        f"ℹ️ *Sifariş vaxtı:* {formatted_date}, {formatted_time}\n\n"
                        f"Təyin olunmuş vaxtda müştərinin ünvanında olacağınız gözlənilir. "
                        f"Vaxt çatdıqda, sizə bildiriş göndəriləcək.",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Error in scheduling arrival check: {e}", exc_info=True)
                    
                    # Still inform about appointment time even if scheduling fails
                    await callback_query.message.answer(
                        f"ℹ️ *Sifariş vaxtı:* {date_time}\n\n"
                        f"Təyin olunmuş vaxtda müştərinin ünvanında olacağınız gözlənilir.",
                        parse_mode="Markdown"
                    )
                
            else:
                await callback_query.message.answer(
                    "❌ Sifariş qəbul edilərkən xəta baş verdi. Zəhmət olmasa, bir az sonra yenidən cəhd edin."
                )
            
            # Try to answer the callback query, but don't fail if it's expired
            try:
                await callback_query.answer()
            except Exception as e:
                logger.warning(f"Could not answer callback query: {e}")
            
        except Exception as e:
            logger.error(f"Error in accept_order: {e}", exc_info=True)
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            try:
                await callback_query.answer()
            except Exception as e:
                logger.warning(f"Could not answer callback query: {e}")

    @dp.callback_query_handler(lambda c: c.data.startswith('reject_order_'))
    async def reject_order(callback_query: types.CallbackQuery, state: FSMContext):
        """Ustanın siparişi reddetmesini işler"""
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
            
            # Get artisan ID
            telegram_id = callback_query.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if not artisan_id:
                await callback_query.message.answer(
                    "❌ Siz hələ usta kimi qeydiyyatdan keçməmisiniz."
                )
                await callback_query.answer()
                return
            
            # Check if the order is assigned to this artisan
            if order['artisan_id'] != artisan_id:
                await callback_query.message.answer(
                    "❌ Bu sifariş sizə təyin edilməyib."
                )
                await callback_query.answer()
                return
            
            # Update order status to "rejected_by_artisan" in database
            # We'll need to add this status to the system
            # For now, let's assume we can use "rejected" status
            success = update_order_status(order_id, "rejected")
            
            if success:
                # Import notification service
                from notification_service import notify_customer_about_order_status
                
                # Notify customer that the order has been rejected
                await notify_customer_about_order_status(order_id, "rejected")
                
                # Find another nearby artisan and reassign the order
                # This should be handled by a separate function
                # For now, we'll just inform the artisan that the order has been rejected
                
                await callback_query.message.answer(
                    f"❌ Sifariş #{order_id} imtina edildi.\n\n"
                    f"Sifariş sistemimizdə başqa bir ustaya yönləndiriləcək."
                )
                
                # Here we need to implement the logic to find another artisan
                # and reassign the order
                # For now, this is a placeholder
                
                # Find another artisan for this order
                # This function would need to be implemented
                await find_and_assign_new_artisan(order_id)
                
            else:
                await callback_query.message.answer(
                    "❌ Sifariş imtina edilərkən xəta baş verdi. Zəhmət olmasa, bir az sonra yenidən cəhd edin."
                )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in reject_order: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()


    async def find_and_assign_new_artisan(order_id):
        try:
            # Get order details
            order = get_order_details(order_id)
            
            if not order:
                logger.error(f"Order not found for reassignment: {order_id}")
                return False
            
            # Get customer information
            customer = get_customer_by_id(order['customer_id'])
            customer_telegram_id = customer.get('telegram_id')
            
            if not customer_telegram_id:
                logger.error(f"Customer telegram_id not found for order: {order_id}")
                return False
            
            # Find available artisans for this service
            artisans = get_nearby_artisans(
                latitude=order['latitude'], 
                longitude=order['longitude'],
                radius=10, 
                service=order['service'],
                subservice=order.get('subservice')
            )
            
            # Safely extract artisan ID for filtering
            def get_artisan_id(artisan):
                if isinstance(artisan, dict):
                    return artisan.get('id')
                elif isinstance(artisan, (list, tuple)) and len(artisan) > 0:
                    return artisan[0]
                return None
            
            # Exclude the previous artisan
            previous_artisan_id = order['artisan_id']
            filtered_artisans = []
            for artisan in artisans:
                artisan_id = get_artisan_id(artisan)
                if artisan_id is not None and artisan_id != previous_artisan_id:
                    filtered_artisans.append(artisan)
            
            artisans = filtered_artisans
            
            if not artisans:
                # No artisans found, increase search radius
                artisans = get_nearby_artisans(
                    latitude=order['latitude'], 
                    longitude=order['longitude'],
                    radius=30,  # Increased radius
                    service=order['service'],
                    subservice=order.get('subservice')
                )
                
                # Exclude the previous artisan again
                filtered_artisans = []
                for artisan in artisans:
                    artisan_id = get_artisan_id(artisan)
                    if artisan_id is not None and artisan_id != previous_artisan_id:
                        filtered_artisans.append(artisan)
                
                artisans = filtered_artisans
                
                if not artisans:
                    # Still no artisans, notify customer
                    from notification_service import notify_customer_no_artisan
                    await notify_customer_no_artisan(customer_telegram_id, order_id)
                    return False
            
            # Find the nearest artisan
            nearest_artisan = None
            min_distance = float('inf')
            
            for artisan in artisans:
                # Extract artisan details safely
                artisan_id = None
                artisan_latitude = None
                artisan_longitude = None
                
                if isinstance(artisan, dict):
                    artisan_id = artisan.get('id')
                    artisan_latitude = artisan.get('latitude')
                    artisan_longitude = artisan.get('longitude')
                elif isinstance(artisan, (list, tuple)):
                    if len(artisan) > 0:
                        artisan_id = artisan[0]
                    if len(artisan) > 5:
                        artisan_latitude = artisan[5]
                    if len(artisan) > 6:
                        artisan_longitude = artisan[6]
                
                if artisan_id and artisan_latitude and artisan_longitude:
                    from geo_helpers import calculate_distance
                    try:
                        distance = calculate_distance(
                            order['latitude'], order['longitude'], 
                            artisan_latitude, artisan_longitude
                        )
                        
                        if distance < min_distance:
                            min_distance = distance
                            nearest_artisan = artisan
                    except Exception as calc_error:
                        logger.error(f"Error calculating distance: {calc_error}")
            
            # If no nearest found, just take the first one
            if not nearest_artisan and artisans:
                nearest_artisan = artisans[0]
            
            if nearest_artisan:
                # Extract artisan ID safely
                artisan_id = None
                if isinstance(nearest_artisan, dict):
                    artisan_id = nearest_artisan.get('id')
                elif isinstance(nearest_artisan, (list, tuple)) and len(nearest_artisan) > 0:
                    artisan_id = nearest_artisan[0]
                
                if artisan_id:
                    # Update order with new artisan
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE orders SET artisan_id = %s, status = 'pending' WHERE id = %s",
                        (artisan_id, order_id)
                    )
                    conn.commit()
                    conn.close()
                    
                    # Notify the new artisan
                    from notification_service import notify_artisan_about_new_order
                    try:
                        await notify_artisan_about_new_order(order_id, artisan_id)
                    except Exception as notify_error:
                        logger.error(f"Error notifying new artisan: {notify_error}")
                    
                    return True
                else:
                    logger.error(f"Could not extract artisan ID from nearest artisan")
            
            return False
            
        except Exception as e:
            logger.error(f"Error in find_and_assign_new_artisan: {e}", exc_info=True)
            return False

    @dp.callback_query_handler(lambda c: c.data.startswith('arrived_'))
    async def artisan_arrived(callback_query: types.CallbackQuery):
        """Ustanın varış yaptığını bildirir"""
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
            
            # Get artisan ID
            telegram_id = callback_query.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if not artisan_id:
                await callback_query.message.answer(
                    "❌ Siz hələ usta kimi qeydiyyatdan keçməmisiniz."
                )
                await callback_query.answer()
                return
            
            # Check if the order is assigned to this artisan
            if order['artisan_id'] != artisan_id:
                await callback_query.message.answer(
                    "❌ Bu sifariş sizə təyin edilməyib."
                )
                await callback_query.answer()
                return
            
            # Import notification service
            from order_status_service import notify_customer_about_arrival
            
            # Notify customer about artisan arrival
            await notify_customer_about_arrival(order_id, "arrived")
            
            await callback_query.message.answer(
                f"✅ Müştəriyə məkana çatdığınız bildirildi.\n\n"
                f"Müştəri təsdiqlədikdən sonra sizə bildiriş göndəriləcək."
            )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in artisan_arrived: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()


    @dp.callback_query_handler(lambda c: c.data.startswith('delayed_'))
    async def artisan_delayed(callback_query: types.CallbackQuery):
        """Ustanın gecikeceğini bildirir"""
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
            
            # Get artisan ID
            telegram_id = callback_query.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if not artisan_id:
                await callback_query.message.answer(
                    "❌ Siz hələ usta kimi qeydiyyatdan keçməmisiniz."
                )
                await callback_query.answer()
                return
            
            # Check if the order is assigned to this artisan
            if order['artisan_id'] != artisan_id:
                await callback_query.message.answer(
                    "❌ Bu sifariş sizə təyin edilməyib."
                )
                await callback_query.answer()
                return
            
            # Import notification service
            from order_status_service import notify_customer_about_arrival, handle_delayed_arrival
            
            # Notify customer about delay
            await notify_customer_about_arrival(order_id, "delayed")
            
            await callback_query.message.answer(
                f"⏱ Müştəriyə 30 dəqiqə ərzində çatacağınız bildirildi.\n\n"
                f"30 dəqiqə sonra bir daha sorğu göndəriləcək."
            )
            
            # Schedule delayed arrival check
            asyncio.create_task(handle_delayed_arrival(order_id))
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in artisan_delayed: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()



    @dp.callback_query_handler(lambda c: c.data.startswith('cannot_arrive_'))
    async def artisan_cannot_arrive(callback_query: types.CallbackQuery):
        """Ustanın gelemeyeceğini bildirir"""
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
            
            # Get artisan ID
            telegram_id = callback_query.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if not artisan_id:
                await callback_query.message.answer(
                    "❌ Siz hələ usta kimi qeydiyyatdan keçməmisiniz."
                )
                await callback_query.answer()
                return
            
            # Check if the order is assigned to this artisan
            if order['artisan_id'] != artisan_id:
                await callback_query.message.answer(
                    "❌ Bu sifariş sizə təyin edilməyib."
                )
                await callback_query.answer()
                return
            
            # Import block function
            from order_status_service import block_artisan_for_no_show
            
            # Block artisan for no-show
            await block_artisan_for_no_show(order_id)
            
            await callback_query.message.answer(
                f"⛔ Sifarişə gələ bilmədiyiniz üçün hesabınız bloklandı.\n\n"
                f"Bloku açmaq üçün /pay_fine əmri ilə cərimə ödəyə bilərsiniz."
            )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in artisan_cannot_arrive: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()



    @dp.callback_query_handler(lambda c: c.data.startswith('artisan_confirm_cash_'))
    async def artisan_confirm_cash_payment(callback_query: types.CallbackQuery):
        """Ustanın nakit ödemeyi aldığını onaylaması"""
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
            
            # Calculate commission
            price = float(order.get('price', 0))
            commission_rate = 0.12  # Default rate (12%)
            
            for tier, info in COMMISSION_RATES.items():
                if price <= info["threshold"]:
                    commission_rate = info["rate"] / 100  # Convert percentage to decimal
                    break
            
            admin_fee = round(price * commission_rate, 2)
            artisan_amount = price - admin_fee
            
            # Create admin payment keyboard
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton(
                "✅ Komissiya ödənişini etdim", 
                callback_data=f"art_payment_made_{order_id}"
            ))
            
            # Notify customer
            customer = get_customer_by_id(order['customer_id'])
            if customer and customer.get('telegram_id'):
                await bot.send_message(
                    chat_id=customer['telegram_id'],
                    text=f"✅ *Ödəniş təsdiqləndi*\n\n"
                        f"Usta sifariş #{order_id} üçün ödənişi aldığını təsdiqlədi.\n"
                        f"Sifarişiniz tamamlandı. Təşəkkür edirik!",
                    parse_mode="Markdown"
                )
            
            # Update order status
            update_order_status(order_id, "completed")

            # Send review request to customer
            try:
                from notification_service import send_review_request_to_customer
                await send_review_request_to_customer(order_id)
                logger.info(f"Review request sent successfully for order {order_id}")
            except Exception as review_error:
                logger.error(f"Error sending review request: {review_error}", exc_info=True)
            
            # Notify artisan about commission payment
            await callback_query.message.answer(
                f"✅ *Ödəniş təsdiqləndi*\n\n"
                f"Sifariş: #{order_id}\n"
                f"Ümumi məbləğ: {price} AZN\n"
                f"Komissiya ({int(commission_rate*100)}%): {admin_fee} AZN\n"
                f"Sizə qalan məbləğ: {artisan_amount} AZN\n\n"
                f"İndi zəhmət olmasa, komissiya məbləğini ({admin_fee} AZN) "
                f"aşağıdakı kart hesabına köçürün:\n\n"
                f"Kart nömrəsi: {ADMIN_CARD_NUMBER}\n"
                f"Sahibi: {ADMIN_CARD_HOLDER}\n\n"
                f"Ödənişi etdikdən sonra 'Komissiya ödənişini etdim' düyməsini basın.",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in artisan_confirm_cash_payment: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith('artisan_deny_cash_'))
    async def artisan_deny_cash_payment(callback_query: types.CallbackQuery):
        """Ustanın nakit ödemeyi almadığını bildirmesi"""
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
            
            # Notify customer
            customer = get_customer_by_id(order['customer_id'])
            if customer and customer.get('telegram_id'):
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton(
                    "🔄 Yenidən cəhd et", 
                    callback_data=f"retry_cash_payment_{order_id}"
                ))
                
                await bot.send_message(
                    chat_id=customer['telegram_id'],
                    text=f"❌ *Ödəniş təsdiqlənmədi*\n\n"
                        f"Usta sifariş #{order_id} üçün ödənişi almadığını bildirdi.\n"
                        f"Zəhmət olmasa, ustaya ödənişi edib yenidən təsdiqləyin.",
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
            
            await callback_query.message.answer(
                f"✅ Ödəniş rədd edildi. Müştəriyə bildiriş göndərildi."
            )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in artisan_deny_cash_payment: {e}")
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()




    @dp.callback_query_handler(lambda c: c.data.startswith('art_payment_made_'))
    async def art_payment_made(callback_query: types.CallbackQuery, state: FSMContext):
        """Handle when artisan indicates payment to admin card"""
        try:
            # Extract order ID from callback data
            order_id = int(callback_query.data.split('_')[-1])
            logger.info(f"Artisan indicated admin payment for order {order_id}")
            
            # Get order details to verify it exists
            order = get_order_details(order_id)
            if not order:
                await callback_query.message.answer(
                    "❌ Sifariş tapılmadı. Silinmiş və ya ləğv edilmiş ola bilər."
                )
                await callback_query.answer()
                return
            
            # Set state for receipt upload
            await PaymentReceiptState.waiting_for_receipt.set()
            
            # Store order ID in state
            async with state.proxy() as data:
                data['order_id'] = order_id
            
            # Ask for payment receipt - clear and direct instruction
            await callback_query.message.answer(
                "📸 Zəhmət olmasa, admin karta etdiyiniz komissiya ödənişinin qəbzini göndərin.\n\n"
                "Bu, ödənişin təsdiqlənməsi üçün lazımdır. Şəkil aydın və oxunaqlı olmalıdır.\n\n"
                "⚠️ QEYD: İndi birbaşa şəkil göndərin, başqa düymə basmayın."
            )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in art_payment_made: {e}", exc_info=True)
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            # Show menu to prevent UI getting stuck
            await show_artisan_menu(callback_query.message)
            await callback_query.answer()

    # Add this handler specifically for payment receipt photos
    @dp.message_handler(content_types=types.ContentType.PHOTO, state=PaymentReceiptState.waiting_for_receipt)
    async def process_payment_receipt(message: types.Message, state: FSMContext):
        """Process payment receipt photos when in waiting_for_receipt state"""
        try:
            # Get order ID from state
            async with state.proxy() as data:
                order_id = data.get('order_id')
            
            if not order_id:
                await message.answer("❌ Xəta baş verdi. Zəhmət olmasa, yenidən başlayın.")
                await state.finish()
                return
            
            # Get the highest quality photo
            photo = message.photo[-1]
            file_id = photo.file_id
            
            logger.info(f"Received payment receipt for order {order_id}, file_id: {file_id}")
            
            # Direct database update for payment receipt
            conn = None
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                # First update the order_payments table
                cursor.execute(
                    """
                    UPDATE order_payments 
                    SET receipt_file_id = %s,
                        receipt_uploaded_at = CURRENT_TIMESTAMP,
                        payment_status = 'pending',
                        payment_date = CURRENT_TIMESTAMP,
                        admin_payment_completed = FALSE,
                        receipt_verified = FALSE
                    WHERE order_id = %s
                    """,
                    (file_id, order_id)
                )
                
                # Also update the order payment status
                cursor.execute(
                    "UPDATE orders SET payment_status = 'paid' WHERE id = %s",
                    (order_id,)
                )
                
                conn.commit()
                logger.info(f"Successfully updated payment receipt for order {order_id}")
                
                # Verify the update worked
                cursor.execute("SELECT receipt_file_id FROM order_payments WHERE order_id = %s", (order_id,))
                receipt_check = cursor.fetchone()
                
                if receipt_check and receipt_check[0]:
                    logger.info(f"Verified receipt_file_id is set for order {order_id}")
                    update_success = True
                else:
                    logger.error(f"Failed to verify receipt_file_id for order {order_id}")
                    update_success = False
                    
            except Exception as db_error:
                if conn:
                    conn.rollback()
                logger.error(f"Database error in process_payment_receipt: {db_error}", exc_info=True)
                update_success = False
            finally:
                if conn:
                    conn.close()
            
            # Send confirmation to user
            if update_success:
                await message.answer(
                    "✅ Ödəniş qəbzi uğurla qeydə alındı!\n\n"
                    "Sizin komissiya ödənişiniz qeydə alındı. Təşəkkür edirik!",
                    reply_markup=types.ReplyKeyboardRemove()
                )
            else:
                await message.answer(
                    "⚠️ Qəbzin qeydə alınmasında problem yaşandı.\n\n"
                    "Amma narahat olmayın, qəbzi aldıq və manuel yolla qeydə alacağıq.",
                    reply_markup=types.ReplyKeyboardRemove()
                )
            
            # Clear state and show main menu
            await state.finish()
            await show_artisan_menu(message)
            
        except Exception as e:
            logger.error(f"Error in process_payment_receipt: {e}", exc_info=True)
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()
            await show_artisan_menu(message)


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


    @dp.callback_query_handler(lambda c: c.data.startswith('resend_commission_'))
    async def resend_commission_receipt(callback_query: types.CallbackQuery, state: FSMContext):
        """Handle commission receipt re-upload request"""
        try:
            # Extract order ID from callback data
            order_id = int(callback_query.data.split('_')[-1])
            
            # Set context for receipt upload
            telegram_id = callback_query.from_user.id
            
            # Get admin fee for the order
            order = get_order_details(order_id)
            if not order:
                await callback_query.message.answer(
                    "❌ Sifariş məlumatları tapılmadı. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
                await callback_query.answer()
                return
                
            admin_fee = order.get('admin_fee', 0)

            # Save order_id to state
            await state.update_data(order_id=order_id)

            # Set state to waiting for receipt
            await PaymentReceiptState.waiting_for_receipt.set()
            
            # Log the state
            logger.info(f"Set state to waiting_for_receipt for user {callback_query.from_user.id}, order {order_id}")
            
            await callback_query.message.answer(
                f"📸 Zəhmət olmasa, komissiya ödənişinin ({admin_fee} AZN) qəbzini yenidən göndərin.\n\n"
                f"Şəkil aydın və oxunaqlı olmalıdır. Ödəniş məbləği, tarix və kart məlumatları görünməlidir."
            )
            
            await callback_query.answer()
            
        except Exception as e:
            logger.error(f"Error in resend_commission_receipt: {e}", exc_info=True)
            await callback_query.message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await callback_query.answer()

    

    # Sonra, spesifik state-li şəkil emalcısı əlavə edək:

    @dp.message_handler(
        content_types=types.ContentType.PHOTO, 
        state=PaymentReceiptState.waiting_for_receipt
    )
    async def process_commission_receipt(message: types.Message, state: FSMContext):
        """Process commission receipt photos when in waiting_for_receipt state"""
        try:
            # Get data from state
            state_data = await state.get_data()
            order_id = state_data.get('order_id')
            
            if not order_id:
                logger.error("No order_id found in state")
                await message.answer("❌ Məlumat tapılmadı. Zəhmət olmasa yenidən cəhd edin.")
                await state.finish()
                return
            
            logger.info(f"Received commission receipt for order {order_id}")
            
            # Get artisan ID
            telegram_id = message.from_user.id
            artisan_id = get_artisan_by_telegram_id(telegram_id)
            
            if not artisan_id:
                logger.error(f"Artisan not found for telegram_id {telegram_id}")
                await message.answer("❌ Usta məlumatları tapılmadı.")
                await state.finish()
                return
            
            # Get the highest quality photo
            photo = message.photo[-1]
            file_id = photo.file_id
            
            # Update database
            conn = None
            success = False
            
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                # Update order_payments table
                cursor.execute(
                    """
                    UPDATE order_payments 
                    SET receipt_file_id = %s,
                        receipt_uploaded_at = CURRENT_TIMESTAMP,
                        receipt_verified = FALSE,  -- Set FALSE for admin visibility
                        payment_status = 'pending',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE order_id = %s
                    RETURNING id
                    """,
                    (file_id, order_id)
                )
                
                result = cursor.fetchone()
                logger.info(f"Database update result: {result}")
                
                if result:
                    # Try to add entry to receipt_verification_history
                    try:
                        cursor.execute(
                            """
                            INSERT INTO receipt_verification_history 
                            (order_id, is_verified, attempt_number, verified_at)
                            VALUES (%s, FALSE, (
                                SELECT COALESCE(MAX(attempt_number), 0) + 1 
                                FROM receipt_verification_history 
                                WHERE order_id = %s
                            ), CURRENT_TIMESTAMP)
                            """,
                            (order_id, order_id)
                        )
                    except Exception as history_error:
                        logger.error(f"Error inserting into receipt_verification_history: {history_error}")
                        # Continue even if history update fails
                    
                    # Clear scheduled block
                    try:
                        cursor.execute(
                            """
                            INSERT INTO notification_log (notification_type, target_id, created_at)
                            VALUES ('commission_resubmitted', %s, CURRENT_TIMESTAMP)
                            """,
                            (order_id,)
                        )
                    except Exception as notify_error:
                        logger.error(f"Error inserting into notification_log: {notify_error}")
                        # Continue even if notification log fails
                    
                    success = True
                
                conn.commit()
                
            except Exception as db_error:
                logger.error(f"Database error in process_commission_receipt: {db_error}", exc_info=True)
                if conn:
                    conn.rollback()
            finally:
                if conn:
                    conn.close()
            
            if success:
                # Send confirmation to artisan
                await message.answer(
                    "✅ Komissiya qəbzi uğurla göndərildi!\n\n"
                    "Qəbziniz yoxlanma üçün admin heyətinə göndərildi. "
                    "Bloklanma prosesi dayandırıldı, ancaq qəbzin təsdiqlənməsi lazımdır.",
                    reply_markup=types.ReplyKeyboardRemove()
                )
                
                # Send detailed notification to artisan
                from notification_service import notify_artisan_commission_receipt_received
                await notify_artisan_commission_receipt_received(artisan_id, order_id)
                
                # Notify admins for review
                for admin_id in BOT_ADMINS:
                    try:
                        await bot.send_photo(
                            chat_id=admin_id,
                            photo=file_id,
                            caption=f"🔄 *Yenidən göndərilmiş komissiya qəbzi*\n\n"
                                f"Sifariş: #{order_id}\n"
                                f"Usta ID: {artisan_id}\n\n"
                                f"Bu qəbz yenidən yoxlanmalıdır. Əvvəlki qəbz rədd edilmişdi.",
                            reply_markup=InlineKeyboardMarkup().add(
                                InlineKeyboardButton("✅ Təsdiqlə", callback_data=f"verify_receipt_{order_id}_true"),
                                InlineKeyboardButton("❌ Rədd et", callback_data=f"verify_receipt_{order_id}_false")
                            ),
                            parse_mode="Markdown"
                        )
                        logger.info(f"Admin notification sent to {admin_id}")
                    except Exception as admin_error:
                        logger.error(f"Error notifying admin {admin_id}: {admin_error}")
            else:
                await message.answer(
                    "❌ Qəbz göndərilərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                )
            
            # Always clear state
            await state.finish()
            
        except Exception as e:
            logger.error(f"Error in process_commission_receipt: {e}", exc_info=True)
            await message.answer(
                "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
            )
            await state.finish()



    # Nakit ödeme onay handler'ları
    dp.register_callback_query_handler(
        artisan_confirm_cash_payment,
        lambda c: c.data.startswith('artisan_confirm_cash_')
    )
    
    dp.register_callback_query_handler(
        artisan_deny_cash_payment,
        lambda c: c.data.startswith('artisan_deny_cash_')
    )
    
    dp.register_callback_query_handler(
        art_payment_made,
        lambda c: c.data.startswith('art_payment_made_')
    )

    dp.register_callback_query_handler(
    confirm_artisan_commission_payment,
    lambda c: c.data.startswith('confirm_art_payment_')
    )

    # register_handlers funksiyasına bu yeni handleri əlavə etməyi unutmayın:

    # Register payment receipt handler for commission
    dp.register_message_handler(
        process_commission_receipt,
        content_types=types.ContentType.PHOTO,
        state=PaymentReceiptState.waiting_for_receipt
    )
    # artisan_handler.py içine ekleyeceğimiz kod:


    # Əmr bələdçisi funksiyasını əlavə et
    dp.register_message_handler(show_command_guide, lambda message: message.text == "ℹ️ Əmr bələdçisi")

    @dp.message_handler(lambda message: True, content_types=types.ContentType.TEXT)
    async def handle_text_input(message: types.Message):
        """Metin girişlerini işler (fiyat girişi vb.)"""
        try:
            telegram_id = message.from_user.id
            
            # Get user context
            from db import get_user_context
            context = get_user_context(telegram_id)
            
            if not context:
                # If no context, pass to other handlers
                return
            
            action = context.get('action')
            
            if action == 'set_price':
                # Handle price input for an order
                order_id = context.get('order_id')
                
                if not order_id:
                    await message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
                    return
                
                # Validate price input
                price_text = message.text.strip()
                
                try:
                    price = float(price_text.replace(',', '.'))
                    if price <= 0:
                        await message.answer("❌ Qiymət müsbət olmalıdır. Zəhmət olmasa, yenidən daxil edin:")
                        return
                except ValueError:
                    await message.answer("❌ Düzgün qiymət daxil edin (məsələn: 50). Zəhmət olmasa, yenidən cəhd edin:")
                    return
                
                # Get order details
                order = get_order_details(order_id)
                
                if not order:
                    await message.answer("❌ Sifariş tapılmadı. Silinmiş və ya ləğv edilmiş ola bilər.")
                    return
                
                # Calculate commission based on price
                commission_rate = 0.12  # Default rate (12%)
                
                for tier, info in COMMISSION_RATES.items():
                    if price <= info["threshold"]:
                        commission_rate = info["rate"] / 100  # Convert percentage to decimal
                        break
                
                admin_fee = price * commission_rate
                artisan_amount = price - admin_fee
                
                # Save price to order in database - Parametreleri sırasıyla gönderin, anahtar kullanmadan
                success = db_set_order_price(
                    order_id,  # order_id=order_id yerine
                    price,     # price=price yerine
                    admin_fee, # admin_fee=admin_fee yerine
                    artisan_amount  # artisan_amount=artisan_amount yerine
                )
                
                if success:
                    # Clear context
                    from db import clear_user_context
                    clear_user_context(telegram_id)
                    
                    # Show confirmation to artisan
                    await message.answer(
                        f"✅ Qiymət uğurla təyin edildi: {price} AZN\n\n"
                        f"Komissiya ({int(commission_rate*100)}%): {admin_fee:.2f} AZN\n"
                        f"Sizə qalacaq məbləğ: {artisan_amount:.2f} AZN\n\n"
                        f"Müştəriyə qiymət təklifi göndərildi. Qəbul edildiyi zaman sizə bildiriş gələcək."
                    )
                    
                    # Notify customer about the price
                    from payment_service import notify_customer_about_price
                    await notify_customer_about_price(order_id, price)
                    
                else:
                    await message.answer(
                        "❌ Qiymət təyin edilərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
                    )
            
        except Exception as e:
            logger.error(f"Error in handle_text_input: {e}")
            # Daha detaylı hata ayıklama için
            import traceback
            logger.error(traceback.format_exc())

    dp.register_callback_query_handler(
        artisan_arrived,
        lambda c: c.data.startswith('arrived_')
    )
    dp.register_callback_query_handler(
        artisan_delayed,
        lambda c: c.data.startswith('delayed_')
    )
    dp.register_callback_query_handler(
        artisan_cannot_arrive,
        lambda c: c.data.startswith('cannot_arrive_')
    )

        



    @dp.callback_query_handler(state="*")
    async def handle_all_callbacks(callback_query: types.CallbackQuery, state: FSMContext):
        """Catch all unhandled callback queries"""
        try:
            callback_data = callback_query.data
            logger.info(f"Unhandled callback received: {callback_data}")
            
            if callback_data.startswith('set_price_range_'):
                # Redirect to the proper handler
                await set_price_range_for_subservice(callback_query, state)
                return
            elif callback_data == "finish_price_setup":
                # Redirect to the proper handler
                await finish_price_setup(callback_query, state)
                return
            elif callback_data == "back_to_menu":
                await state.finish()
                await show_artisan_menu(callback_query.message)
                await callback_query.answer()
                return
            elif callback_data == "setup_payment_info":
                # Redirect to the proper handler
                await setup_payment_info(callback_query, state)
                return
            
            # For any other unhandled callbacks
            await callback_query.answer("Bu əməliyyat hazırda mövcud deyil.")
            
        except Exception as e:
            logger.error(f"Error in handle_all_callbacks: {e}")
            await callback_query.answer()