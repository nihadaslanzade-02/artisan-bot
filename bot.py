#!/usr/bin/env python
"""
Artisan Booking Bot - Main Application
A Telegram bot for connecting customers with artisans/service providers.

This bot allows customers to find and book artisans for various services,
and helps artisans manage their service offerings and customer orders.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
import logging
from aiohttp import web
import json
from admin_service import (
    process_receipt_verification_update,
    process_admin_payment_completed_update
)
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from config import *
import handlers.customer_handler
import handlers.artisan_handler
import db_setup
from db import *
import re
import handlers.start
import html

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Admin FSM States
class AdminSearchState(StatesGroup):
    waiting_for_query = State()

class AdminBlockState(StatesGroup):
    waiting_for_reason = State()
    waiting_for_payment = State()

class AdminContactState(StatesGroup):
    waiting_for_message = State()

class AdminRefundState(StatesGroup):
        waiting_for_amount = State()
        waiting_for_reason = State()


def is_admin(user_id):
    """Check if user is admin"""
    logger.info(f"Checking if user {user_id} is admin. Admin list: {BOT_ADMINS}")
    
    # Əmin olmaq üçün user_id tipini int-ə çevir
    user_id = int(user_id)
    
    # BOT_ADMINS siyahısında int olmayan elementlər varsa, onları int-ə çevir
    admin_list = [int(admin_id) if not isinstance(admin_id, int) else admin_id for admin_id in BOT_ADMINS]
    
    return user_id in admin_list


# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Set up database
async def on_startup(dp):
    """Execute actions on startup"""
    logger.info("Starting bot...")
    
    # Run database setup
    db_setup.setup_database()
    
    # Register all notification and service modules
    try:
        import notification_service
        import payment_service
        import order_status_service
        logger.info("Service modules loaded successfully")
    except Exception as e:
        logger.error(f"Error loading service modules: {e}")
    
    # Start scheduled tasks
    asyncio.create_task(scheduled_tasks())
    
    logger.info("Bot started successfully!")

# Start command handler
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    """
    Handle the /start command
    This is the entry point for new users
    """
    try:
        user_id = message.from_user.id
        is_admin_user = user_id in BOT_ADMINS  # Admin olub-olmadığını yoxla
        
        # Check if user is a blocked customer
        customer = get_customer_by_telegram_id(user_id)
        if customer:
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
        
        # Create welcome keyboard
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(KeyboardButton("👤 Müştəriyəm"), KeyboardButton("🛠 Ustayam"))
        
        # Admin üçün xüsusi düymə əlavə et
        if is_admin_user:
            keyboard.add(KeyboardButton("👨‍💼 Admin"))
        
        # Send welcome message
        await message.answer(
            "👋 *Xoş gəlmisiniz!*\n\n"
            "Bu bot vasitəsilə ehtiyacınız olan xidmət üçün usta tapa və ya "
            "usta olaraq müştərilərə xidmət göstərə bilərsiniz.\n\n"
            "Zəhmət olmasa, rolunuzu seçin:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await message.answer(
            "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
        )

# Help command handler
@dp.message_handler(commands=['help'])
async def help_command(message: types.Message):
    """
    Handle the /help command
    Provides help information to users
    """
    try:
        help_text = (
            "🔍 *Bot haqqında məlumat*\n\n"
            "*Müştərilər üçün:*\n"
            "• 'Müştəriyəm' seçin\n"
            "• 'Yeni sifariş ver' düyməsini klikləyin\n"
            "• Xidmət növünü seçin\n"
            "• Yerinizi paylaşın\n"
            "• Tarix və saat seçin\n"
            "• Probleminiz haqqında qısa məlumat yazın\n"
            "• Sifarişi təsdiqləyin\n\n"
            
            "*Ustalar üçün:*\n"
            "• 'Ustayam' seçin\n"
            "• İlk dəfədirsə, qeydiyyatdan keçin\n"
            "• 'Aktiv sifarişlər' bölməsində müştəri sifarişlərini görün\n"
            "• Sifarişləri qəbul edin və ya ləğv edin\n\n"
            
            "*Əlavə məlumat:*\n"
            "• Əvvəlki sifarişlərə 'Əvvəlki sifarişlərə bax' bölməsindən baxa bilərsiniz\n"
            "• Yaxınlıqdakı ustaları görmək üçün 'Yaxınlıqdakı ustaları göstər' seçin\n"
            "• Bot haqqında məlumat üçün /help yazın\n"
            "• Yenidən başlamaq üçün /start yazın\n\n"
            
            "❓ Suallarınız olarsa, bizə yazın: support@ustabot.az"
        )
        
        await message.answer(
            help_text,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in help command: {e}")
        await message.answer(
            "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
        )

# Admin rolü seçildiğində gösterilecek handler
@dp.message_handler(lambda message: message.text == "👨‍💼 Admin")
async def admin_panel(message: types.Message):
    """Handle when user selects Admin role"""
    user_id = message.from_user.id
    
    # Debug için
    print(f"Admin panel accessed by user ID: {user_id}")
    logger.info(f"Admin panel accessed by user ID: {user_id}")
    
    # Admin kontrolü
    if user_id not in BOT_ADMINS:
        await message.answer("❌ Bu əməliyyat yalnızca admin istifadəçilər üçün əlçatandır.")
        return
    
    # Admin menüsünü oluştur
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("📋 Sifarişləri İdarə Et", callback_data="admin_orders"),
        InlineKeyboardButton("🧾 Ödəniş Qəbzlərini Yoxla", callback_data="admin_receipts"),
        InlineKeyboardButton("👤 İstifadəçiləri İdarə Et", callback_data="admin_users"),
        InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")
    )
    
    await message.answer(
        "👨‍💼 *Admin İdarəetmə Paneli*\n\n"
        "Zəhmət olmasa, aşağıdakı bölmələrdən birini seçin:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.message_handler(commands=['admin'])
async def admin_command(message: types.Message):
    """Admin command handler that shows admin menu"""
    user_id = message.from_user.id
    
    # Debug info
    logger.info(f"Admin command triggered by user ID: {user_id}")
    logger.info(f"BOT_ADMINS list: {BOT_ADMINS}")
    logger.info(f"Is admin check result: {user_id in BOT_ADMINS}")
    
    # Admin kontrolü
    if user_id not in BOT_ADMINS:
        await message.answer("❌ Bu əməliyyat yalnızca admin istifadəçilər üçün əlçatandır.")
        return
    
    # Admin menüsünü oluştur
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("📋 Sifarişləri İdarə Et", callback_data="admin_orders"),
        InlineKeyboardButton("🧾 Ödəniş Qəbzlərini Yoxla", callback_data="admin_receipts"),
        InlineKeyboardButton("👤 İstifadəçiləri İdarə Et", callback_data="admin_users"),
        InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")
    )
    
    await message.answer(
        "👨‍💼 *Admin İdarəetmə Paneli*\n\n"
        "Zəhmət olmasa, aşağıdakı bölmələrdən birini seçin:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


@dp.callback_query_handler(lambda c: c.data.startswith('admin_'))
async def admin_menu_handlers(callback_query: types.CallbackQuery):
    """Handle admin menu options"""
    try:
        if not is_admin(callback_query.from_user.id):
            await callback_query.answer("❌ Bu əməliyyat yalnızca admin istifadəçilər üçün əlçatandır.", show_alert=True)
            return
        
        menu_option = callback_query.data
        
        if menu_option == "admin_orders":
            await show_admin_orders(callback_query.message)
        elif menu_option == "admin_receipts":
            await show_admin_receipts(callback_query.message)
        elif menu_option == "admin_users":
            await show_admin_users(callback_query.message)
        elif menu_option == "admin_stats":
            await show_admin_stats(callback_query.message)
        else:
            await callback_query.answer("Bu funksiya hələ hazır deyil.")
        
        await callback_query.answer()
    
    except Exception as e:
        logger.error(f"Error in admin_menu_handlers: {e}")
        await callback_query.message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")



async def show_admin_receipts(message):
    """Show payment receipts for admin to verify"""
    try:
        # Get unverified and pending receipts
        from db import execute_query, get_artisan_by_id, get_customer_by_id
        from crypto_service import decrypt_data
        from db_encryption_wrapper import decrypt_dict_data
        
        query = """
            SELECT o.id, o.service, o.price, o.payment_method, c.id as customer_id, 
                a.id as artisan_id, op.receipt_file_id, op.receipt_verified,
                op.receipt_uploaded_at, op.payment_method as op_payment_method,
                (SELECT COUNT(*) FROM receipt_verification_history 
                 WHERE order_id = o.id) as attempt_count
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            JOIN artisans a ON o.artisan_id = a.id
            LEFT JOIN order_payments op ON o.id = op.order_id
            WHERE op.receipt_file_id IS NOT NULL 
            AND (op.receipt_verified IS NULL OR op.receipt_verified IS FALSE)
            ORDER BY op.receipt_uploaded_at DESC
            LIMIT 50
        """
        
        receipts = execute_query(query, fetchall=True, dict_cursor=True)
        
        if not receipts:
            await message.answer("📭 Yoxlanılası qəbz tapılmadı.")
            return
        
        await message.answer("🧾 *Yoxlanılmamış Ödəniş Qəbzləri*\n\nYoxlamaq üçün bir qəbz seçin:", parse_mode="Markdown")
        
        # Send each receipt with its details and verification buttons
        for receipt in receipts:
            order_id = receipt['id']
            
            # Şifreleri çözülmüş müşteri ve usta bilgilerini al
            customer_encrypted = get_customer_by_id(receipt['customer_id'])
            artisan_encrypted = get_artisan_by_id(receipt['artisan_id'])
            
            # Şifreleri çöz ve maskele
            customer = decrypt_dict_data(customer_encrypted, mask=True)
            artisan = get_masked_artisan_by_id(receipt['artisan_id'])
            
            # Get verification status
            status_text = ""
            if receipt['receipt_verified'] is True:
                status_text = "✅ Təsdiqlənib"
            elif receipt['receipt_verified'] is False:
                status_text = "❌ Rədd edilib"
            else:
                status_text = "⏳ Gözləyir"
            
            # Payment method info - Fix here: first try op_payment_method, then fallback to payment_method
            payment_method = receipt.get('op_payment_method') or receipt.get('payment_method', 'Təyin edilməyib')
            if payment_method == 'card':
                payment_info = "💳 Müştəri tərəfindən kartla ödəniş"
            elif payment_method == 'cash':
                payment_info = "💵 Usta tərəfindən nağd ödəniş komissiyası"
                
                attempt_count = receipt.get('attempt_count', 0)
                if attempt_count > 1:
                    payment_info += f" (Təkrar göndərilmiş qəbz - {attempt_count} cəhd)"

            else:
                payment_info = f"Ödəniş üsulu: {payment_method}"
                
            # Create verification buttons
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("✅ Təsdiqlə", callback_data=f"verify_receipt_{order_id}_true"),
                InlineKeyboardButton("❌ Rədd et", callback_data=f"verify_receipt_{order_id}_false")
            )
            
            # Create caption with order details
            caption = (
                f"🧾 *Sifariş #{order_id}*\n"
                f"👤 Müştəri: {customer['name']}\n"
                f"👷‍♂️ Usta: {artisan['name']}\n"
                f"🛠 Xidmət: {receipt['service']}\n"
                f"💰 Məbləğ: {receipt['price']} AZN\n"
                f"💳 {payment_info}\n"
                f"📝 Status: {status_text}\n"
                f"📅 Yüklənmə tarixi: {receipt['receipt_uploaded_at']}"
            )
            
            # Send receipt image with caption and buttons
            if receipt['receipt_file_id']:
                await bot.send_photo(
                    chat_id=message.chat.id,
                    photo=receipt['receipt_file_id'],
                    caption=caption,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                # If receipt file ID is missing, send text only
                await message.answer(
                    f"{caption}\n\n⚠️ Qəbz şəkli tapılmadı!",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
    
    except Exception as e:
        logger.error(f"Error in show_admin_receipts: {e}")
        await message.answer("❌ Qəbzlər yüklənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
    



@dp.callback_query_handler(lambda c: c.data.startswith('verify_receipt_'))
async def verify_receipt_handler(callback_query: types.CallbackQuery):
    """Handle receipt verification by admin"""
    try:
        if not is_admin(callback_query.from_user.id):
            await callback_query.answer("❌ Bu əməliyyat yalnızca admin istifadəçilər üçün əlçatandır.", show_alert=True)
            return
        
        # Extract data: format is verify_receipt_ORDER_ID_BOOL
        parts = callback_query.data.split('_')
        order_id = int(parts[2])
        is_verified_str = parts[3]
        
        # Convert string to boolean
        is_verified = (is_verified_str.lower() == 'true')
        
        # Log the verification action for debugging
        logger.info(f"Admin {callback_query.from_user.id} is {'verifying' if is_verified else 'rejecting'} receipt for order {order_id}")
        
        # Update receipt verification status using admin_service function
        from admin_service import process_receipt_verification_update
        success = await process_receipt_verification_update(order_id, is_verified)
        
        if success:
            # Update message to reflect verification
            status_text = "✅ Təsdiqlənib" if is_verified else "❌ Rədd edilib"
            
            # Get original caption
            caption = callback_query.message.caption
            
            # Update status in caption
            new_caption = re.sub(r'📝 Status: .*', f'📝 Status: {status_text}', caption)
            
            # Update message and remove buttons
            await bot.edit_message_caption(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                caption=new_caption,
                reply_markup=None,
                parse_mode="HTML"
            )
            
            # Send confirmation
            action_text = "təsdiqləndi" if is_verified else "rədd edildi"
            await callback_query.message.answer(f"✓ Sifariş #{order_id} üçün qəbz {action_text}.")
            
            # If rejected, inform that notification was sent to customer
            if not is_verified:
                await callback_query.message.answer(
                    f"ℹ️ Müştəri sifariş #{order_id} üçün qəbzin rədd edildiyi haqqında məlumatlandırıldı. "
                    f"1 saat ərzində yeni qəbz göndərməzsə hesabı bloklanacaq."
                )
        else:
            await callback_query.message.answer(f"❌ Sifariş #{order_id} üçün qəbz statusunu yeniləmək mümkün olmadı.")
        
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Error in verify_receipt_handler: {e}")
        await callback_query.message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
        await callback_query.answer()

async def show_admin_orders(message):
    """Show orders for admin to manage"""
    try:
        # Get recent orders
        from db import execute_query, get_artisan_by_id, get_customer_by_id
        from crypto_service import decrypt_data
        from db_encryption_wrapper import decrypt_dict_data
        
        query = """
            SELECT o.id, o.service, o.price, o.status, o.created_at, 
                   c.id as customer_id, a.id as artisan_id
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            JOIN artisans a ON o.artisan_id = a.id
            ORDER BY o.created_at DESC
            LIMIT 10
        """
        
        orders = execute_query(query, fetchall=True, dict_cursor=True)
        
        if not orders:
            await message.answer("📭 Aktiv sifariş tapılmadı.")
            return
        
        # Create filter options
        keyboard = InlineKeyboardMarkup(row_width=3)
        keyboard.add(
            InlineKeyboardButton("🟢 Aktiv", callback_data="filter_orders_active"),
            InlineKeyboardButton("✅ Tamamlanmış", callback_data="filter_orders_completed"),
            InlineKeyboardButton("❌ Ləğv edilmiş", callback_data="filter_orders_cancelled"),
            InlineKeyboardButton("🔄 Hamısı", callback_data="filter_orders_all")
        )
        
        await message.answer(
            "📋 <b>Son Sifarişlər</b>\n\n"
            "Sifarişlər aşağıda göstərilir. Filterləmək üçün bir seçim edin:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        # Display recent orders
        for order in orders:
            # Şifreleri çözülmüş müşteri ve usta bilgilerini al
            customer_encrypted = get_customer_by_id(order['customer_id'])
            artisan_encrypted = get_artisan_by_id(order['artisan_id'])
            
            # Şifreleri çöz ve maskele
            customer = decrypt_dict_data(customer_encrypted, mask=True)
            artisan = get_masked_artisan_by_id(order['artisan_id'])
            
            # Format date
            created_at = order['created_at']
            if isinstance(created_at, str):
                formatted_date = created_at
            else:
                formatted_date = created_at.strftime("%d.%m.%Y %H:%M")
            
            # Format status
            status = order['status']
            if status == 'pending':
                status_text = "⏳ Gözləyir"
            elif status == 'accepted':
                status_text = "🟢 Qəbul edilib"
            elif status == 'completed':
                status_text = "✅ Tamamlanıb"
            elif status == 'cancelled':
                status_text = "❌ Ləğv edilib"
            else:
                status_text = status
            
            # Create order text
            order_text = (
                f"🔹 <b>Sifariş #{order['id']}</b>\n"
                f"📅 Tarix: {formatted_date}\n"
                f"👤 Müştəri: {customer['name']}\n"
                f"👷‍♂️ Usta: {artisan['name']}\n"
                f"🛠 Xidmət: {order['service']}\n"
                f"💰 Məbləğ: {order.get('price', 'Təyin edilməyib')} AZN\n"
                f"🔄 Status: {status_text}"
            )
            
            # Create action buttons for order
            order_keyboard = InlineKeyboardMarkup(row_width=1)
            order_keyboard.add(
                InlineKeyboardButton("ℹ️ Ətraflı Məlumat", callback_data=f"order_details_{order['id']}"),
                InlineKeyboardButton("💰 Ödəniş Detalları", callback_data=f"order_payment_{order['id']}")
            )
            
            # Add status change buttons based on current status
            if status == 'pending':
                order_keyboard.add(
                    InlineKeyboardButton("✅ Qəbul et", callback_data=f"order_accept_{order['id']}"),
                    InlineKeyboardButton("❌ Ləğv et", callback_data=f"order_cancel_{order['id']}")
                )
            elif status == 'accepted':
                order_keyboard.add(
                    InlineKeyboardButton("✅ Tamamla", callback_data=f"order_complete_{order['id']}"),
                    InlineKeyboardButton("❌ Ləğv et", callback_data=f"order_cancel_{order['id']}")
                )
            
            await message.answer(
                order_text,
                reply_markup=order_keyboard,
                parse_mode="HTML"
            )
    
    except Exception as e:
        logger.error(f"Error in show_admin_orders: {e}")
        await message.answer("❌ Sifarişlər yüklənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")

async def show_admin_users(message):
    """Show users for admin to manage"""
    try:
        # Create user type filter buttons
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("👤 Müştərilər", callback_data="show_customers"),
            InlineKeyboardButton("👷‍♂️ Ustalar", callback_data="show_artisans"),
            InlineKeyboardButton("🔍 İstifadəçi Axtar", callback_data="search_user")
        )
        
        await message.answer(
            "👥 *İstifadəçilər*\n\n"
            "Hansı istifadəçi tipini görmək istəyirsiniz?",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in show_admin_users: {e}")
        await message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")

async def show_admin_stats(message):
    """Show system statistics for admin"""
    try:
        # Get basic stats from database
        from db import execute_query
        
        # Total customers
        customers_query = "SELECT COUNT(*) FROM customers"
        total_customers = execute_query(customers_query, fetchone=True)[0]
        
        # Total artisans
        artisans_query = "SELECT COUNT(*) FROM artisans"
        total_artisans = execute_query(artisans_query, fetchone=True)[0]
        
        # Total orders
        orders_query = "SELECT COUNT(*) FROM orders"
        total_orders = execute_query(orders_query, fetchone=True)[0]
        
        # Completed orders
        completed_query = "SELECT COUNT(*) FROM orders WHERE status = 'completed'"
        completed_orders = execute_query(completed_query, fetchone=True)[0]
        
        # Cancelled orders
        cancelled_query = "SELECT COUNT(*) FROM orders WHERE status = 'cancelled'"
        cancelled_orders = execute_query(cancelled_query, fetchone=True)[0]
        
        # Total revenue
        revenue_query = "SELECT COALESCE(SUM(admin_fee), 0) FROM order_payments"
        total_revenue = execute_query(revenue_query, fetchone=True)[0]
        
        # Orders by service
        service_query = """
            SELECT service, COUNT(*) as count
            FROM orders
            GROUP BY service
            ORDER BY count DESC
            LIMIT 5
        """
        service_stats = execute_query(service_query, fetchall=True)
        
        # Format service stats
        service_text = ""
        for service, count in service_stats:
            service_text += f"• {service}: {count} sifariş\n"
        
        # Create statistics message
        stats_text = (
            "📊 *Sistem Statistikaları*\n\n"
            f"👤 *Müştərilər:* {total_customers}\n"
            f"👷‍♂️ *Ustalar:* {total_artisans}\n\n"
            f"📋 *Ümumi sifarişlər:* {total_orders}\n"
            f"✅ *Tamamlanmış sifarişlər:* {completed_orders}\n"
            f"❌ *Ləğv edilmiş sifarişlər:* {cancelled_orders}\n\n"
            f"💰 *Ümumi komissiya gəliri:* {total_revenue:.2f} AZN\n\n"
            f"🔝 *Ən populyar xidmətlər:*\n{service_text}"
        )
        
        # Create options keyboard
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton("📅 Tarixə görə statistika", callback_data="stats_by_date"),
            InlineKeyboardButton("📊 Ətraflı hesabat", callback_data="detailed_stats"),
            InlineKeyboardButton("🔙 Admin Menyusuna Qayıt", callback_data="back_to_admin")
        )
        
        await message.answer(
            stats_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error in show_admin_stats: {e}")
        await message.answer("❌ Statistikalar yüklənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")

@dp.callback_query_handler(lambda c: c.data.startswith(('order_', 'filter_orders_')))
async def order_actions_handler(callback_query: types.CallbackQuery):
    """Handle order-related actions"""
    try:
        if not is_admin(callback_query.from_user.id):
            await callback_query.answer("❌ Bu əməliyyat yalnızca admin istifadəçilər üçün əlçatandır.", show_alert=True)
            return
        
        action = callback_query.data
        
        # Handle filter actions
        if action.startswith('filter_orders_'):
            filter_type = action.split('_')[-1]
            await filter_orders(callback_query.message, filter_type)
            await callback_query.answer()
            return
        
        # Handle order actions
        action_parts = action.split('_')
        action_type = action_parts[1]
        order_id = int(action_parts[2])
        
        if action_type == 'details':
            await show_order_details(callback_query.message, order_id)
        elif action_type == 'payment':
            await show_order_payment(callback_query.message, order_id)
        elif action_type == 'accept':
            await admin_accept_order(callback_query.message, order_id)
        elif action_type == 'cancel':
            await admin_cancel_order(callback_query.message, order_id)
        elif action_type == 'complete':
            await admin_complete_order(callback_query.message, order_id)
        else:
            await callback_query.answer("Bu əməliyyat hələ hazır deyil.")
            return
        
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Error in order_actions_handler: {e}")
        await callback_query.message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
        await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data in ['show_customers', 'show_artisans', 'search_user'])
async def user_actions_handler(callback_query: types.CallbackQuery):
    """Handle user-related actions"""
    try:
        if not is_admin(callback_query.from_user.id):
            await callback_query.answer("❌ Bu əməliyyat yalnızca admin istifadəçilər üçün əlçatandır.", show_alert=True)
            return
        
        action = callback_query.data
        
        if action == 'show_customers':
            await show_customers_list(callback_query.message)
        elif action == 'show_artisans':
            await show_artisans_list(callback_query.message)
        elif action == 'search_user':
            await start_user_search(callback_query.message)
        else:
            await callback_query.answer("Bu əməliyyat hələ hazır deyil.")
            return
        
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Error in user_actions_handler: {e}")
        await callback_query.message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
        await callback_query.answer()

async def filter_orders(message, filter_type):
    """Show filtered orders based on type"""
    try:
        from db import execute_query, get_artisan_by_id, get_customer_by_id
        from crypto_service import decrypt_data
        from db_encryption_wrapper import decrypt_dict_data
        
        # Build query based on filter type
        query = """
            SELECT o.id, o.service, o.price, o.status, o.created_at, 
                   c.id as customer_id, a.id as artisan_id
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            JOIN artisans a ON o.artisan_id = a.id
        """
        
        if filter_type == "active":
            query += " WHERE o.status IN ('pending', 'accepted')"
        elif filter_type == "completed":
            query += " WHERE o.status = 'completed'"
        elif filter_type == "cancelled":
            query += " WHERE o.status = 'cancelled'"
        
        query += " ORDER BY o.created_at DESC LIMIT 10"
        
        orders = execute_query(query, fetchall=True, dict_cursor=True)
        
        if not orders:
            await message.answer(f"📭 Bu filterlə sifariş tapılmadı.")
            return
        
        # Send filter info
        filter_name = {
            "active": "Aktiv",
            "completed": "Tamamlanmış",
            "cancelled": "Ləğv edilmiş",
            "all": "Bütün"
        }.get(filter_type, "Müəyyən edilməmiş")
        
        await message.answer(f"🔍 *{filter_name} Sifarişlər*\n\n{len(orders)} sifariş tapıldı:", parse_mode="Markdown")
        
        # Display filtered orders
        for order in orders:
            # Şifreleri çözülmüş müşteri ve usta bilgilerini al
            customer_encrypted = get_customer_by_id(order['customer_id'])
            artisan_encrypted = get_artisan_by_id(order['artisan_id'])
            
            # Şifreleri çöz ve maskele
            customer = decrypt_dict_data(customer_encrypted, mask=True)
            artisan = get_masked_artisan_by_id(order['artisan_id'])
            
            # Format date
            created_at = order['created_at']
            if isinstance(created_at, str):
                formatted_date = created_at
            else:
                formatted_date = created_at.strftime("%d.%m.%Y %H:%M")
            
            # Format status
            status = order['status']
            if status == 'pending':
                status_text = "⏳ Gözləyir"
            elif status == 'accepted':
                status_text = "🟢 Qəbul edilib"
            elif status == 'completed':
                status_text = "✅ Tamamlanıb"
            elif status == 'cancelled':
                status_text = "❌ Ləğv edilib"
            else:
                status_text = status
            
            # Create order text
            order_text = (
                f"🔹 <b>Sifariş #{order['id']}</b>\n"
                f"📅 Tarix: {formatted_date}\n"
                f"👤 Müştəri: {customer['name']}\n"
                f"👷‍♂️ Usta: {artisan['name']}\n"
                f"🛠 Xidmət: {order['service']}\n"
                f"💰 Məbləğ: {order.get('price', 'Təyin edilməyib')} AZN\n"
                f"🔄 Status: {status_text}"
            )
            
            # Create action buttons for order
            order_keyboard = InlineKeyboardMarkup(row_width=1)
            order_keyboard.add(
                InlineKeyboardButton("ℹ️ Ətraflı Məlumat", callback_data=f"order_details_{order['id']}"),
                InlineKeyboardButton("💰 Ödəniş Detalları", callback_data=f"order_payment_{order['id']}")
            )
            
            await message.answer(
                order_text,
                reply_markup=order_keyboard,
                parse_mode="HTML"
            )
    
    except Exception as e:
        logger.error(f"Error in filter_orders: {e}")
        await message.answer("❌ Sifarişlər yüklənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")

async def show_order_details(message, order_id):
    """Show detailed information about an order"""
    try:
        # Get comprehensive order details - gerçek veriler için düzeltme
        from db import get_order_details, get_customer_by_id, get_artisan_by_id
        from crypto_service import decrypt_data
        from db_encryption_wrapper import decrypt_dict_data
        
        order_encrypted = get_order_details(order_id)
        
        if not order_encrypted:
            await message.answer(f"❌ Sifariş #{order_id} tapılmadı.")
            return
        
        # Müşteri ve usta bilgilerini al ve şifrelerini çöz
        customer_encrypted = get_customer_by_id(order_encrypted.get('customer_id'))
        artisan_encrypted = get_artisan_by_id(order_encrypted.get('artisan_id'))
        
        # Şifreleri çöz ve maskele
        customer = decrypt_dict_data(customer_encrypted, mask=True)
        artisan = get_masked_artisan_by_id(order_encrypted.get('artisan_id'))
        
        # Sipariş verisinin şifresini çöz ve maskele
        order = decrypt_dict_data(order_encrypted, mask=True)
        
        # Format date
        date_time = order.get('date_time')
        if isinstance(date_time, str):
            formatted_date = date_time
        else:
            formatted_date = date_time.strftime("%d.%m.%Y %H:%M")
        
        # Format status
        status = order.get('status')
        if status == 'pending':
            status_text = "⏳ Gözləyir"
        elif status == 'accepted':
            status_text = "🟢 Qəbul edilib"
        elif status == 'completed':
            status_text = "✅ Tamamlanıb"
        elif status == 'cancelled':
            status_text = "❌ Ləğv edilib"
        else:
            status_text = status
        
        # Format payment status
        payment_status = order.get('payment_status')
        if payment_status == 'pending':
            payment_text = "⏳ Gözləyir"
        elif payment_status == 'completed':
            payment_text = "✅ Tamamlanıb"
        elif payment_status == 'paid':
            payment_text = "💰 Ödənilib"
        elif payment_status == 'unpaid':
            payment_text = "❌ Ödənilməyib"
        else:
            payment_text = payment_status
        
        # Create detailed order text with real data
        details_text = (
            f"📋 *Sifariş #{order_id} Detalları*\n\n"
            f"📅 *Tarix və saat:* {formatted_date}\n"
            f"🔄 *Status:* {status_text}\n\n"
            f"👤 *Müştəri:* {customer.get('name')}\n"
            f"📞 *Müştəri telefonu:* {customer.get('phone')}\n\n"
            f"👷‍♂️ *Usta:* {artisan.get('name')}\n"
            f"📞 *Usta telefonu:* {artisan.get('phone')}\n\n"
            f"🛠 *Xidmət:* {order.get('service')}\n"
            f"🔍 *Alt xidmət:* {order.get('subservice', 'Yoxdur')}\n"
            f"📝 *Qeyd:* {order.get('note', 'Yoxdur')}\n\n"
            f"💰 *Məbləğ:* {order.get('price', 'Təyin edilməyib')} AZN\n"
            f"💳 *Ödəniş üsulu:* {order.get('payment_method', 'Təyin edilməyib')}\n"
            f"💸 *Ödəniş statusu:* {payment_text}\n"
        )
        
        # Add location information if available
        if order.get('latitude') and order.get('longitude'):
            details_text += f"\n📍 *Yer:* {order.get('location_name', 'Təyin edilməyib')}"
        
        # Create action buttons based on current status
        keyboard = InlineKeyboardMarkup(row_width=2)
        
        if status == 'pending':
            keyboard.add(
                InlineKeyboardButton("✅ Qəbul et", callback_data=f"order_accept_{order_id}"),
                InlineKeyboardButton("❌ Ləğv et", callback_data=f"order_cancel_{order_id}")
            )
        elif status == 'accepted':
            keyboard.add(
                InlineKeyboardButton("✅ Tamamla", callback_data=f"order_complete_{order_id}"),
                InlineKeyboardButton("❌ Ləğv et", callback_data=f"order_cancel_{order_id}")
            )
        
        # Add general action buttons
        keyboard.add(
            InlineKeyboardButton("💰 Ödəniş Detalları", callback_data=f"order_payment_{order_id}"),
            InlineKeyboardButton("📍 Yeri Göstər", callback_data=f"order_location_{order_id}"),
            InlineKeyboardButton("💸 Ödəniş Qaytarılması", callback_data=f"request_refund_{order_id}")
        )
        
        keyboard.add(
            InlineKeyboardButton("🔙 Sifarişlərə Qayıt", callback_data="admin_orders")
        )
        
        await message.answer(
            details_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in show_order_details: {e}")
        await message.answer("❌ Sifariş detalları yüklənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")

async def show_order_payment(message, order_id):
    """Show payment details for an order"""
    try:
        # Get payment details
        from db import debug_order_payment, get_order_details
        
        payment_details = debug_order_payment(order_id)
        order = get_order_details(order_id)
        
        if not payment_details:
            await message.answer(f"❌ Sifariş #{order_id} üçün ödəniş məlumatları tapılmadı.")
            return
        
        if not order:
            await message.answer(f"❌ Sifariş #{order_id} tapılmadı.")
            return
        
        # Format payment verification status
        receipt_verified = payment_details.get('receipt_verified')
        if receipt_verified is True:
            verification_text = "✅ Təsdiqlənib"
        elif receipt_verified is False:
            verification_text = "❌ Rədd edilib"
        else:
            verification_text = "⏳ Gözləyir"
        
        # Format admin payment status
        admin_payment = payment_details.get('admin_payment_completed')
        admin_payment_text = "✅ Tamamlanıb" if admin_payment else "⏳ Gözləyir"
        
        # Create payment details text
        payment_text = (
            f"💰 *Sifariş #{order_id} Ödəniş Detalları*\n\n"
            f"💵 *Ümumi məbləğ:* {payment_details.get('amount', 'Yoxdur')} AZN\n"
            f"🏢 *Komissiya:* {payment_details.get('admin_fee', 'Yoxdur')} AZN\n"
            f"👷‍♂️ *Ustaya qalan:* {payment_details.get('artisan_amount', 'Yoxdur')} AZN\n\n"
            f"💳 *Ödəniş üsulu:* {payment_details.get('payment_method', 'Yoxdur')}\n"
            f"🔄 *Ödəniş statusu:* {payment_details.get('payment_status', 'Yoxdur')}\n"
            f"📝 *Qəbz statusu:* {verification_text}\n"
            f"🏢 *Admin ödənişi:* {admin_payment_text}\n"
        )
        
        # Create action buttons
        keyboard = InlineKeyboardMarkup(row_width=2)
        
        # Add verification buttons if receipt exists but not verified
        receipt_file_id = payment_details.get('receipt_file_id')
        if receipt_file_id and receipt_verified is not False:
            keyboard.add(
                InlineKeyboardButton("✅ Qəbzi Təsdiqlə", callback_data=f"verify_receipt_{order_id}_true"),
                InlineKeyboardButton("❌ Qəbzi Rədd Et", callback_data=f"verify_receipt_{order_id}_false")
            )
        
        # Add admin payment buttons if applicable
        if payment_details.get('payment_method') == 'cash' and not admin_payment:
            keyboard.add(
                InlineKeyboardButton("✅ Admin ödənişini təsdiqlə", callback_data=f"admin_payment_{order_id}_true")
            )
        
        # Always add back button
        keyboard.add(
            InlineKeyboardButton("🔙 Sifarişə Qayıt", callback_data=f"order_details_{order_id}")
        )
        
        # If there's a receipt, send it with payment details
        if receipt_file_id:
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=receipt_file_id,
                caption=payment_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        else:
            # Otherwise just send text
            await message.answer(
                payment_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        
    except Exception as e:
        logger.error(f"Error in show_order_payment: {e}")
        await message.answer("❌ Ödəniş detalları yüklənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")

async def admin_accept_order(message, order_id):
    """Admin accepts an order"""
    try:
        from db import update_order_status
        
        # Update order status
        success = update_order_status(order_id, "accepted")
        
        if success:
            await message.answer(f"✅ Sifariş #{order_id} qəbul edildi.")
            
            # Notify customer and artisan
            await notify_about_order_status_change(order_id, "accepted")
        else:
            await message.answer(f"❌ Sifariş #{order_id} statusu yenilənərkən xəta baş verdi.")
            
    except Exception as e:
        logger.error(f"Error in admin_accept_order: {e}")
        await message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")

async def admin_cancel_order(message, order_id):
    """Admin cancels an order"""
    try:
        from db import update_order_status
        
        # Update order status
        success = update_order_status(order_id, "cancelled")
        
        if success:
            await message.answer(f"❌ Sifariş #{order_id} ləğv edildi.")
            
            # Notify customer and artisan
            await notify_about_order_status_change(order_id, "cancelled")
        else:
            await message.answer(f"❌ Sifariş #{order_id} statusu yenilənərkən xəta baş verdi.")
            
    except Exception as e:
        logger.error(f"Error in admin_cancel_order: {e}")
        await message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")

async def admin_complete_order(message, order_id):
    """Admin completes an order"""
    try:
        from db import update_order_status
        
        # Update order status
        success = update_order_status(order_id, "completed")
        
        if success:
            await message.answer(f"✅ Sifariş #{order_id} tamamlandı.")
            
            # Notify customer and artisan
            await notify_about_order_status_change(order_id, "completed")
        else:
            await message.answer(f"❌ Sifariş #{order_id} statusu yenilənərkən xəta baş verdi.")
            
    except Exception as e:
        logger.error(f"Error in admin_complete_order: {e}")
        await message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")

async def notify_about_order_status_change(order_id, status):
    """Notify customer and artisan about order status change"""
    try:
        from notification_service import notify_customer_about_order_status
        from db import get_order_details, get_artisan_by_id
        
        # Get order details
        order = get_order_details(order_id)
        
        if not order:
            logger.error(f"Order {order_id} not found for notification")
            return
        
        # Notify customer
        await notify_customer_about_order_status(order_id, status)
        
        # Notify artisan
        artisan = get_artisan_by_id(order['artisan_id'])
        
        if artisan and artisan.get('telegram_id'):
            # Prepare status text
            if status == "accepted":
                status_text = "✅ *Sifariş qəbul edildi*"
                explanation = "Admin tərəfindən qəbul edildi."
            elif status == "cancelled":
                status_text = "❌ *Sifariş ləğv edildi*"
                explanation = "Admin tərəfindən ləğv edildi."
            elif status == "completed":
                status_text = "✅ *Sifariş tamamlandı*"
                explanation = "Admin tərəfindən tamamlandı."
            else:
                status_text = f"🔄 *Sifariş statusu dəyişdirildi*"
                explanation = f"Yeni status: {status}"
            
            # Send notification to artisan
            await bot.send_message(
                chat_id=artisan['telegram_id'],
                text=f"{status_text}\n\n"
                     f"Sifariş #{order_id}\n"
                     f"{explanation}",
                parse_mode="Markdown"
            )
        
    except Exception as e:
        logger.error(f"Error in notify_about_order_status_change: {e}")

async def show_customers_list(message):
    """Show list of customers"""
    try:
        from db import execute_query
        
        # Get recent customers with ratings
        query = """
            SELECT id, name, phone, city, created_at, active
            FROM customers
            ORDER BY created_at DESC
            LIMIT 20
        """
        
        customers = execute_query(query, fetchall=True, dict_cursor=True)
        
        if not customers:
            await message.answer("📭 Müştəri tapılmadı.")
            return
        
        await message.answer(f"👤 *Müştərilər ({len(customers)})*\n\nSon qeydiyyatdan keçən müştərilər:", parse_mode="Markdown")
        
        # Send each customer as a separate message with options
        for customer in customers:
            # Həssas məlumatları maskalanmış şəkildə al
            from db_encryption_wrapper import wrap_get_dict_function
            from db import get_customer_by_id
            
            masked_customer = wrap_get_dict_function(get_customer_by_id, mask=True)(customer['id'])
            
            # Format date
            created_at = customer['created_at']
            if isinstance(created_at, str):
                formatted_date = created_at
            else:
                formatted_date = created_at.strftime("%d.%m.%Y")
            
            # Format status
            status_emoji = "🟢" if customer.get('active', True) else "🔴"
            status_text = "Aktiv" if customer.get('active', True) else "Bloklanıb"
            
        
            
            # Markdown özel karakterleri kaçışla (escape)
            masked_name = masked_customer['name'].replace('*', '\\*')
            masked_phone = masked_customer['phone'].replace('*', '\\*')
            city = customer.get('city', 'Təyin edilməyib')
            if city and isinstance(city, str):
                city = city.replace('*', '\\*')

            # Create customer text with masked data
            customer_text = (
                f"👤 *Müştəri #{customer['id']}*\n"
                f"Ad: {masked_name}\n"
                f"Telefon: {masked_phone}\n"
                f"Şəhər: {city}\n"
                f"Qeydiyyat tarixi: {formatted_date}\n"
                f"Status: {status_emoji} {status_text}"
            )
            
            # Create action buttons
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("📋 Sifarişləri", callback_data=f"customer_orders_{customer['id']}"),
                InlineKeyboardButton("📞 Əlaqə saxla", callback_data=f"contact_customer_{customer['id']}")
            )
            
            # Add block/unblock button based on current status
            if customer.get('active', True):
                keyboard.add(InlineKeyboardButton("🔒 Blokla", callback_data=f"block_customer_{customer['id']}"))
            else:
                keyboard.add(InlineKeyboardButton("🔓 Bloku aç", callback_data=f"unblock_customer_{customer['id']}"))
            
            await message.answer(
                customer_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        
        # Add filter options
        filter_keyboard = InlineKeyboardMarkup(row_width=2)
        filter_keyboard.add(
            InlineKeyboardButton("🟢 Aktiv", callback_data="filter_customers_active"),
            InlineKeyboardButton("🔴 Bloklanmış", callback_data="filter_customers_blocked"),
            InlineKeyboardButton("🔍 Axtar", callback_data="search_customer"),
            InlineKeyboardButton("🔙 Admin Menyusuna Qayıt", callback_data="back_to_admin")
        )
        
        await message.answer(
            "Filterləmək üçün seçim edin:",
            reply_markup=filter_keyboard
        )
        
    except Exception as e:
        logger.error(f"Error in show_customers_list: {e}")
        await message.answer("❌ Müştərilər yüklənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
        
async def show_artisans_list(message):
    """Show list of artisans"""
    try:
        from db import execute_query
        
        # Get recent artisans
        query = """
            SELECT id, name, phone, city, service, rating, created_at, active
            FROM artisans
            ORDER BY created_at DESC
            LIMIT 20
        """
        
        artisans = execute_query(query, fetchall=True, dict_cursor=True)
        
        if not artisans:
            await message.answer("📭 Usta tapılmadı.")
            return
        
        await message.answer(f"👷‍♂️ *Ustalar ({len(artisans)})*\n\nSon qeydiyyatdan keçən ustalar:", parse_mode="Markdown")
        
        # Send each artisan as a separate message with options
        for artisan in artisans:
            # Həssas məlumatları maskalanmış şəkildə al
            from db_encryption_wrapper import wrap_get_dict_function
            from db import get_artisan_by_id
            
            masked_artisan = wrap_get_dict_function(get_artisan_by_id, mask=True)(artisan['id'])
            
            # Format date
            created_at = artisan['created_at']
            if isinstance(created_at, str):
                formatted_date = created_at
            else:
                formatted_date = created_at.strftime("%d.%m.%Y")
            
            # Format status
            status_emoji = "🟢" if artisan.get('active', True) else "🔴"
            status_text = "Aktiv" if artisan.get('active', True) else "Bloklanıb"
            
            # Format rating
            rating = artisan.get('rating', 0)
            if rating:
                rating_text = f"{rating:.1f}/5"
                rating_stars = "⭐" * round(rating)
            else:
                rating_text = "Qiymətləndirilməyib"
                rating_stars = ""
            
            # Önce değişkenleri hazırlayalım
            masked_name = masked_artisan['name'].replace('*', '\\*')
            masked_phone = masked_artisan['phone'].replace('*', '\\*')
            masked_city = artisan.get('city', 'Təyin edilməyib').replace('*', '\\*')
            masked_service = artisan['service'].replace('*', '\\*')
            
            # Sonra f-string içinde kullanalım
            artisan_text = (
                f"👷‍♂️ *Usta #{artisan['id']}*\n"
                f"Ad: {masked_name}\n"
                f"Telefon: {masked_phone}\n"
                f"Şəhər: {masked_city}\n"
                f"Xidmət: {masked_service}\n"
                f"Reytinq: {rating_text} {rating_stars}\n"
                f"Qeydiyyat tarixi: {formatted_date}\n"
                f"Status: {status_emoji} {status_text}"
            )
            
            # Create action buttons
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("📋 Sifarişləri", callback_data=f"artisan_orders_{artisan['id']}"),
                InlineKeyboardButton("📞 Əlaqə saxla", callback_data=f"contact_artisan_{artisan['id']}")
            )
            
            # Add block/unblock button based on current status
            if artisan.get('active', True):
                keyboard.add(InlineKeyboardButton("🔒 Blokla", callback_data=f"block_artisan_{artisan['id']}"))
            else:
                keyboard.add(InlineKeyboardButton("🔓 Bloku aç", callback_data=f"unblock_artisan_{artisan['id']}"))
            
            await message.answer(
                artisan_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        
        # Add filter options
        filter_keyboard = InlineKeyboardMarkup(row_width=2)
        filter_keyboard.add(
            InlineKeyboardButton("🟢 Aktiv", callback_data="filter_artisans_active"),
            InlineKeyboardButton("🔴 Bloklanmış", callback_data="filter_artisans_blocked"),
            InlineKeyboardButton("🔍 Axtar", callback_data="search_artisan"),
            InlineKeyboardButton("🔙 Admin Menyusuna Qayıt", callback_data="back_to_admin")
        )
        
        await message.answer(
            "Filterləmək üçün seçim edin:",
            reply_markup=filter_keyboard
        )
        
    except Exception as e:
        logger.error(f"Error in show_artisans_list: {e}")
        await message.answer("❌ Ustalar yüklənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")

async def start_user_search(message):
    """Start user search process"""
    try:
        await message.answer(
            "🔍 *İstifadəçi Axtarışı*\n\n"
            "Zəhmət olmasa, axtarmaq istədiyiniz istifadəçinin növünü seçin:",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("👤 Müştəri", callback_data="search_type_customer"),
                InlineKeyboardButton("👷‍♂️ Usta", callback_data="search_type_artisan")
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in start_user_search: {e}")
        await message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")

@dp.callback_query_handler(lambda c: c.data.startswith('search_type_'))
async def select_search_type(callback_query: types.CallbackQuery, state: FSMContext):
    """Handle search type selection"""
    try:
        if not is_admin(callback_query.from_user.id):
            await callback_query.answer("❌ Bu əməliyyat yalnızca admin istifadəçilər üçün əlçatandır.", show_alert=True)
            return
        
        search_type = callback_query.data.split('_')[-1]
        
        # Store search type in state
        async with state.proxy() as data:
            data['search_type'] = search_type
        
        # Ask for search query
        await callback_query.message.answer(
            f"🔍 {'Müştəri' if search_type == 'customer' else 'Usta'} axtarışı\n\n"
            f"Zəhmət olmasa, axtarış sorğusunu daxil edin (ad, telefon, ID):"
        )
        
        await AdminSearchState.waiting_for_query.set()
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Error in select_search_type: {e}")
        await callback_query.message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
        await callback_query.answer()

@dp.message_handler(state=AdminSearchState.waiting_for_query)
async def process_search_query(message: types.Message, state: FSMContext):
    """Process search query"""
    try:
        # Get search query
        query = message.text.strip()
        
        if len(query) < 2:
            await message.answer("❌ Axtarış sorğusu ən azı 2 simvol olmalıdır. Zəhmət olmasa, yenidən daxil edin:")
            return
        
        # Get search type from state
        data = await state.get_data()
        search_type = data.get('search_type')
        
        # Execute search based on type
        if search_type == 'customer':
            await search_customers(message, query)
        elif search_type == 'artisan':
            await search_artisans(message, query)
        else:
            await message.answer("❌ Namə'lum axtarış növü. Zəhmət olmasa, yenidən cəhd edin.")
        
        # Clear state
        await state.finish()
        
    except Exception as e:
        logger.error(f"Error in process_search_query: {e}")
        await message.answer("❌ Axtarış zamanı xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
        await state.finish()

async def search_customers(message, query):
    """Search for customers"""
    try:
        from db import execute_query
        
        # Build search query
        search_query = """
            SELECT id, name, phone, city, created_at, active
            FROM customers
            WHERE LOWER(name) LIKE LOWER(%s)
               OR phone LIKE %s
               OR id::text = %s
            LIMIT 10
        """
        
        # Execute search
        results = execute_query(
            search_query, 
            (f"%{query}%", f"%{query}%", query), 
            fetchall=True,
            dict_cursor=True
        )
        
        if not results:
            await message.answer(f"🔍 '{query}' üçün heç bir müştəri tapılmadı.")
            return
        
        await message.answer(f"🔍 '{query}' üçün {len(results)} müştəri tapıldı:")
        
        # Show results
        for customer in results:
            # Format date
            created_at = customer['created_at']
            if isinstance(created_at, str):
                formatted_date = created_at
            else:
                formatted_date = created_at.strftime("%d.%m.%Y")
            
            # Format status
            status_emoji = "🟢" if customer.get('active', True) else "🔴"
            status_text = "Aktiv" if customer.get('active', True) else "Bloklanıb"
            
            # Create customer text
            customer_text = (
                f"👤 *Müştəri #{customer['id']}*\n"
                f"Ad: {customer['name']}\n"
                f"Telefon: {customer['phone']}\n"
                f"Şəhər: {customer.get('city', 'Təyin edilməyib')}\n"
                f"Qeydiyyat tarixi: {formatted_date}\n"
                f"Status: {status_emoji} {status_text}"
            )
            
            # Create action buttons
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("📋 Sifarişləri", callback_data=f"customer_orders_{customer['id']}"),
                InlineKeyboardButton("📞 Əlaqə saxla", callback_data=f"contact_customer_{customer['id']}")
            )
            
            # Add block/unblock button based on current status
            if customer.get('active', True):
                keyboard.add(InlineKeyboardButton("🔒 Blokla", callback_data=f"block_customer_{customer['id']}"))
            else:
                keyboard.add(InlineKeyboardButton("🔓 Bloku aç", callback_data=f"unblock_customer_{customer['id']}"))
            
            await message.answer(
                customer_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        
    except Exception as e:
        logger.error(f"Error in search_customers: {e}")
        await message.answer("❌ Axtarış zamanı xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")

async def search_artisans(message, query):
    """Search for artisans"""
    try:
        from db import execute_query
        
        # Build search query
        search_query = """
            SELECT id, name, phone, city, service, rating, created_at, active
            FROM artisans
            WHERE LOWER(name) LIKE LOWER(%s)
               OR phone LIKE %s
               OR id::text = %s
               OR LOWER(service) LIKE LOWER(%s)
            LIMIT 10
        """
        
        # Execute search
        results = execute_query(
            search_query, 
            (f"%{query}%", f"%{query}%", query, f"%{query}%"), 
            fetchall=True,
            dict_cursor=True
        )
        
        if not results:
            await message.answer(f"🔍 '{query}' üçün heç bir usta tapılmadı.")
            return
        
        await message.answer(f"🔍 '{query}' üçün {len(results)} usta tapıldı:")
        
        # Show results
        for artisan in results:
            # Format date
            created_at = artisan['created_at']
            if isinstance(created_at, str):
                formatted_date = created_at
            else:
                formatted_date = created_at.strftime("%d.%m.%Y")
            
            # Format status
            status_emoji = "🟢" if artisan.get('active', True) else "🔴"
            status_text = "Aktiv" if artisan.get('active', True) else "Bloklanıb"
            
            # Format rating
            rating = artisan.get('rating', 0)
            if rating:
                rating_text = f"{rating:.1f}/5"
                rating_stars = "⭐" * round(rating)
            else:
                rating_text = "Qiymətləndirilməyib"
                rating_stars = ""
            
            # Create artisan text
            artisan_text = (
                f"👷‍♂️ *Usta #{artisan['id']}*\n"
                f"Ad: {artisan['name']}\n"
                f"Telefon: {artisan['phone']}\n"
                f"Şəhər: {artisan.get('city', 'Təyin edilməyib')}\n"
                f"Xidmət: {artisan['service']}\n"
                f"Reytinq: {rating_text} {rating_stars}\n"
                f"Qeydiyyat tarixi: {formatted_date}\n"
                f"Status: {status_emoji} {status_text}"
            )
            
            # Create action buttons
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("📋 Sifarişləri", callback_data=f"artisan_orders_{artisan['id']}"),
                InlineKeyboardButton("📞 Əlaqə saxla", callback_data=f"contact_artisan_{artisan['id']}")
            )
            
            # Add block/unblock button based on current status
            if artisan.get('active', True):
                keyboard.add(InlineKeyboardButton("🔒 Blokla", callback_data=f"block_artisan_{artisan['id']}"))
            else:
                keyboard.add(InlineKeyboardButton("🔓 Bloku aç", callback_data=f"unblock_artisan_{artisan['id']}"))
            
            await message.answer(
                artisan_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        
    except Exception as e:
        logger.error(f"Error in search_artisans: {e}")
        await message.answer("❌ Axtarış zamanı xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")

@dp.callback_query_handler(lambda c: c.data.startswith(('block_customer_', 'unblock_customer_', 'block_artisan_', 'unblock_artisan_')))
async def user_block_actions(callback_query: types.CallbackQuery):
    """Handle user blocking and unblocking actions"""
    try:
        if not is_admin(callback_query.from_user.id):
            await callback_query.answer("❌ Bu əməliyyat yalnızca admin istifadəçilər üçün əlçatandır.", show_alert=True)
            return
        
        # Parse action
        action_parts = callback_query.data.split('_')
        action = action_parts[0]  # block or unblock
        user_type = action_parts[1]  # customer or artisan
        user_id = int(action_parts[2])
        
        if action == "block":
            if user_type == "customer":
                await show_block_customer_form(callback_query.message, user_id)
            else:  # artisan
                await show_block_artisan_form(callback_query.message, user_id)
        else:  # unblock
            if user_type == "customer":
                await unblock_customer_action(callback_query.message, user_id)
            else:  # artisan
                await unblock_artisan_action(callback_query.message, user_id)
        
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Error in user_block_actions: {e}")
        await callback_query.message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
        await callback_query.answer()

async def show_block_customer_form(message, customer_id):
    """Show form to block a customer"""
    try:
        from db import get_customer_by_id
        
        # Get customer info
        customer = get_customer_by_id(customer_id)
        
        if not customer:
            await message.answer(f"❌ Müştəri #{customer_id} tapılmadı.")
            return
        
        # Store customer ID in state
        async with dp.current_state().proxy() as data:
            data['user_type'] = 'customer'
            data['user_id'] = customer_id
        
        # Ask for block reason
        await message.answer(
            f"🔒 *Müştəri Bloklama*\n\n"
            f"Müştəri: {customer['name']} (ID: {customer_id})\n\n"
            f"Zəhmət olmasa, bloklanma səbəbini daxil edin:",
            parse_mode="Markdown"
        )
        
        await AdminBlockState.waiting_for_reason.set()
        
    except Exception as e:
        logger.error(f"Error in show_block_customer_form: {e}")
        await message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")

async def show_block_artisan_form(message, artisan_id):
    """Show form to block an artisan"""
    try:
        from db import get_artisan_by_id
        
        # Get artisan info
        artisan = get_artisan_by_id(artisan_id)
        
        if not artisan:
            await message.answer(f"❌ Usta #{artisan_id} tapılmadı.")
            return
        
        # Store artisan ID in state
        async with dp.current_state().proxy() as data:
            data['user_type'] = 'artisan'
            data['user_id'] = artisan_id
        
        # Ask for block reason
        await message.answer(
            f"🔒 *Usta Bloklama*\n\n"
            f"Usta: {artisan['name']} (ID: {artisan_id})\n\n"
            f"Zəhmət olmasa, bloklanma səbəbini daxil edin:",
            parse_mode="Markdown"
        )
        
        await AdminBlockState.waiting_for_reason.set()
        
    except Exception as e:
        logger.error(f"Error in show_block_artisan_form: {e}")
        await message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")

@dp.message_handler(state=AdminBlockState.waiting_for_reason)
async def process_block_reason(message: types.Message, state: FSMContext):
    """Process block reason input"""
    try:
        # Get and validate reason
        reason = message.text.strip()
        
        if len(reason) < 3:
            await message.answer("❌ Səbəb ən azı 3 simvol olmalıdır. Zəhmət olmasa, yenidən daxil edin:")
            return
        
        # Store reason in state
        async with state.proxy() as data:
            data['block_reason'] = reason
        
        # Ask for required payment amount
        await message.answer(
            "💰 Zəhmət olmasa, bloku açmaq üçün tələb olunan ödəniş məbləğini AZN ilə daxil edin (məsələn: 25):"
        )
        
        await AdminBlockState.waiting_for_payment.set()
        
    except Exception as e:
        logger.error(f"Error in process_block_reason: {e}")
        await message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
        await state.finish()

@dp.message_handler(state=AdminBlockState.waiting_for_payment)
async def process_block_payment(message: types.Message, state: FSMContext):
    """Process block payment amount input"""
    try:
        # Get and validate payment amount
        payment_text = message.text.strip()
        
        try:
            payment_amount = float(payment_text.replace(',', '.'))
            if payment_amount <= 0:
                await message.answer("❌ Məbləğ müsbət olmalıdır. Zəhmət olmasa, yenidən daxil edin:")
                return
        except ValueError:
            await message.answer("❌ Düzgün məbləğ daxil edin (məsələn: 25). Zəhmət olmasa, yenidən cəhd edin:")
            return
        
        # Get data from state
        data = await state.get_data()
        user_type = data.get('user_type')
        user_id = data.get('user_id')
        block_reason = data.get('block_reason')
        
        # Block user based on type
        if user_type == 'customer':
            from db import block_customer
            success = block_customer(user_id, block_reason, payment_amount)
            user_label = "Müştəri"
        else:  # artisan
            from db import block_artisan
            success = block_artisan(user_id, block_reason, payment_amount)
            user_label = "Usta"
        
        if success:
            await message.answer(
                f"✅ {user_label} #{user_id} uğurla bloklandı.\n\n"
                f"Səbəb: {block_reason}\n"
                f"Açılma məbləği: {payment_amount} AZN"
            )
            
            # Notify user about being blocked
            await notify_user_about_block(user_type, user_id, block_reason, payment_amount)
        else:
            await message.answer(f"❌ {user_label} bloklama zamanı xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
        
        # Clear state
        await state.finish()
        
    except Exception as e:
        logger.error(f"Error in process_block_payment: {e}")
        await message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
        await state.finish()

async def notify_user_about_block(user_type, user_id, reason, amount):
    """Notify user about being blocked"""
    try:
        if user_type == 'customer':
            from db import get_customer_by_id
            user = get_customer_by_id(user_id)
            command = "/pay_customer_fine"
        else:  # artisan
            from db import get_artisan_by_id
            user = get_artisan_by_id(user_id)
            command = "/pay_fine"
        
        if not user or not user.get('telegram_id'):
            logger.error(f"User {user_id} not found or missing telegram_id")
            return
        
        # Send notification
        await bot.send_message(
            chat_id=user['telegram_id'],
            text=f"⛔ *Hesabınız bloklandı*\n\n"
                 f"Səbəb: {reason}\n\n"
                 f"Bloku açmaq üçün {amount} AZN ödəniş etməlisiniz.\n"
                 f"Ödəniş etmək üçün: {command} komandası ilə ətraflı məlumat ala bilərsiniz.",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in notify_user_about_block: {e}")

async def unblock_customer_action(message, customer_id):
    """Unblock a customer"""
    try:
        from db import unblock_customer, get_customer_by_id
        
        # Get customer info
        customer = get_customer_by_id(customer_id)
        
        if not customer:
            await message.answer(f"❌ Müştəri #{customer_id} tapılmadı.")
            return
        
        # Unblock customer
        success = unblock_customer(customer_id)
        
        if success:
            await message.answer(f"✅ Müştəri #{customer_id} ({customer['name']}) blokdan çıxarıldı.")
            
            # Notify customer
            if customer.get('telegram_id'):
                await bot.send_message(
                    chat_id=customer['telegram_id'],
                    text="🔓 *Hesabınız blokdan çıxarıldı*\n\n"
                         "Admin tərəfindən hesabınız blokdan çıxarıldı. "
                         "İndi normal şəkildə xidmətlərimizi istifadə edə bilərsiniz.",
                    parse_mode="Markdown"
                )
        else:
            await message.answer(f"❌ Müştəri blokdan çıxarılarkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
            
    except Exception as e:
        logger.error(f"Error in unblock_customer_action: {e}")
        await message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")

async def unblock_artisan_action(message, artisan_id):
    """Unblock an artisan"""
    try:
        from db import unblock_artisan, get_artisan_by_id
        
        # Get artisan info
        artisan = get_artisan_by_id(artisan_id)
        
        if not artisan:
            await message.answer(f"❌ Usta #{artisan_id} tapılmadı.")
            return
        
        # Unblock artisan
        success = unblock_artisan(artisan_id)
        
        if success:
            await message.answer(f"✅ Usta #{artisan_id} ({artisan['name']}) blokdan çıxarıldı.")
            
            # Notify artisan
            if artisan.get('telegram_id'):
                await bot.send_message(
                    chat_id=artisan['telegram_id'],
                    text="🔓 *Hesabınız blokdan çıxarıldı*\n\n"
                         "Admin tərəfindən hesabınız blokdan çıxarıldı. "
                         "İndi normal şəkildə xidmətlərimizi istifadə edə bilərsiniz.",
                    parse_mode="Markdown"
                )
        else:
            await message.answer(f"❌ Usta blokdan çıxarılarkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
            
    except Exception as e:
        logger.error(f"Error in unblock_artisan_action: {e}")
        await message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")

@dp.callback_query_handler(lambda c: c.data.startswith(('contact_customer_', 'contact_artisan_')))
async def contact_user_actions(callback_query: types.CallbackQuery):
    """Handle contacting users"""
    try:
        if not is_admin(callback_query.from_user.id):
            await callback_query.answer("❌ Bu əməliyyat yalnızca admin istifadəçilər üçün əlçatandır.", show_alert=True)
            return
        
        # Parse action
        action_parts = callback_query.data.split('_')
        user_type = action_parts[1]  # customer or artisan
        user_id = int(action_parts[2])
        
        # Store user info in state
        async with dp.current_state().proxy() as data:
            data['user_type'] = user_type
            data['user_id'] = user_id
        
        # Get user info
        if user_type == 'customer':
            from db import get_customer_by_id
            user = get_customer_by_id(user_id)
            user_label = "Müştəri"
        else:  # artisan
            from db import get_artisan_by_id
            user = get_artisan_by_id(user_id)
            user_label = "Usta"
        
        if not user:
            await callback_query.message.answer(f"❌ {user_label} #{user_id} tapılmadı.")
            await callback_query.answer()
            return
        
        # Ask for message to send
        await callback_query.message.answer(
            f"📞 *{user_label} ilə əlaqə*\n\n"
            f"{user_label}: {user['name']} (ID: {user_id})\n"
            f"Telefon: {user['phone']}\n\n"
            f"Zəhmət olmasa, göndərmək istədiyiniz mesajı daxil edin:\n\n"
            f"⚠️ Mesaj birbaşa {user_label.lower()}ya bot vasitəsilə göndəriləcək!",
            parse_mode="Markdown"
        )
        
        await AdminContactState.waiting_for_message.set()
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Error in contact_user_actions: {e}")
        await callback_query.message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
        await callback_query.answer()

@dp.message_handler(state=AdminContactState.waiting_for_message)
async def process_admin_message(message: types.Message, state: FSMContext):
    """Process admin message to user"""
    try:
        # Get message content
        admin_message = message.text.strip()
        
        if len(admin_message) < 1:
            await message.answer("❌ Mesaj boş ola bilməz. Zəhmət olmasa, yenidən daxil edin:")
            return
        
        # Get data from state
        data = await state.get_data()
        user_type = data.get('user_type')
        user_id = data.get('user_id')
        
        # Get user info
        if user_type == 'customer':
            from db import get_customer_by_id
            user = get_customer_by_id(user_id)
            user_label = "Müştəri"
        else:  # artisan
            from db import get_artisan_by_id
            user = get_artisan_by_id(user_id)
            user_label = "Usta"
        
        if not user or not user.get('telegram_id'):
            await message.answer(f"❌ {user_label} #{user_id} tapılmadı və ya telegram ID yoxdur.")
            await state.finish()
            return
        
        # Send message to user
        try:
            await bot.send_message(
                chat_id=user['telegram_id'],
                text=f"📢 *Admin Mesajı*\n\n{admin_message}\n\n"
                     f"Bu mesaj sistemin admin heyəti tərəfindən göndərilib. "
                     f"Cavab vermək üçün müştəri dəstəyinə yazın: {SUPPORT_PHONE}",
                parse_mode="Markdown"
            )
            
            # Confirm to admin
            await message.answer(
                f"✅ Mesaj uğurla {user_label.lower()}ya göndərildi!\n\n"
                f"{user_label}: {user['name']} (ID: {user_id})\n"
                f"Mesaj: {admin_message}"
            )
        except Exception as e:
            logger.error(f"Error sending message to user: {e}")
            await message.answer(f"❌ Mesaj göndərilmədi. İstifadəçi botu bloklamış ola bilər.")
        
        # Clear state
        await state.finish()
        
    except Exception as e:
        logger.error(f"Error in process_admin_message: {e}")
        await message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
        await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith(('customer_orders_', 'artisan_orders_')))
async def user_orders_actions(callback_query: types.CallbackQuery):
    """Handle user orders viewing"""
    try:
        if not is_admin(callback_query.from_user.id):
            await callback_query.answer("❌ Bu əməliyyat yalnızca admin istifadəçilər üçün əlçatandır.", show_alert=True)
            return
        
        # Parse action
        action_parts = callback_query.data.split('_')
        user_type = action_parts[0]  # customer or artisan
        user_id = int(action_parts[2])
        
        if user_type == 'customer':
            await show_customer_orders(callback_query.message, user_id)
        else:  # artisan
            await show_artisan_orders(callback_query.message, user_id)
        
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Error in user_orders_actions: {e}")
        await callback_query.message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
        await callback_query.answer()

async def show_customer_orders(message, customer_id):
    """Show orders for a specific customer"""
    try:
        from db import get_customer_by_id, get_customer_orders, get_artisan_by_id
        from crypto_service import decrypt_data
        from db_encryption_wrapper import decrypt_dict_data
        
        # Get customer info
        customer_encrypted = get_customer_by_id(customer_id)
        
        if not customer_encrypted:
            await message.answer(f"❌ Müştəri #{customer_id} tapılmadı.")
            return
        
        # Şifreleri çöz ve maskele
        customer = decrypt_dict_data(customer_encrypted, mask=True)
        
        # Get customer orders
        orders_encrypted = get_customer_orders(customer_id)
        
        if not orders_encrypted:
            await message.answer(f"📭 Müştəri #{customer_id} ({customer['name']}) üçün hələ heç bir sifariş yoxdur.")
            return
        
        await message.answer(
            f"📋 *Müştəri #{customer_id} ({customer['name']}) sifarişləri*\n\n"
            f"Tapılmış sifarişlər: {len(orders_encrypted)}",
            parse_mode="Markdown"
        )
        
        # Display each order
        for order_encrypted in orders_encrypted:
            # Siparişin şifresini çöz
            order = decrypt_dict_data(order_encrypted, mask=False)
            
            # Usta bilgilerini al ve şifresini çöz
            if order.get('artisan_id'):
                artisan = get_artisan_by_id(order.get('artisan_id'))
                artisan_name = artisan.get('name', 'Təyin edilməyib') if artisan else 'Təyin edilməyib'
            else:
                artisan_name = 'Təyin edilməyib'
            
            # Format date
            date_time = order.get('date_time')
            if isinstance(date_time, str):
                formatted_date = date_time
            else:
                formatted_date = date_time.strftime("%d.%m.%Y %H:%M") if date_time else "Bilinmiyor"
            
            # Format status
            status = order.get('status')
            if status == 'pending':
                status_text = "⏳ Gözləyir"
            elif status == 'accepted':
                status_text = "🟢 Qəbul edilib"
            elif status == 'completed':
                status_text = "✅ Tamamlanıb"
            elif status == 'cancelled':
                status_text = "❌ Ləğv edilib"
            else:
                status_text = status
            
            # Create order text
            order_text = (
                f"🔹 *Sifariş #{order.get('id')}*\n"
                f"📅 Tarix: {formatted_date}\n"
                f"👷‍♂️ Usta: {artisan_name}\n"
                f"🛠 Xidmət: {order.get('service', 'Təyin edilməyib')}\n"
                f"💰 Məbləğ: {order.get('price', 'Təyin edilməyib')} AZN\n"
                f"🔄 Status: {status_text}\n"
                f"📝 Qeyd: {order.get('note', '')}"
            )
            
            # Create action buttons
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                InlineKeyboardButton("ℹ️ Ətraflı Məlumat", callback_data=f"order_details_{order.get('id')}")
            )
            
            await message.answer(
                order_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        
    except Exception as e:
        logger.error(f"Error in show_customer_orders: {e}")
        await message.answer("❌ Sifarişlər yüklənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")

async def show_artisan_orders(message, artisan_id):
    """Show orders for a specific artisan"""
    try:
        from db import get_artisan_by_id, execute_query, get_customer_by_id
        from crypto_service import decrypt_data
        from db_encryption_wrapper import decrypt_dict_data
        
        # Get artisan info
        artisan_encrypted = get_artisan_by_id(artisan_id)
        
        if not artisan_encrypted:
            await message.answer(f"❌ Usta #{artisan_id} tapılmadı.")
            return
        
        # Şifreleri çöz ve maskele
        artisan = get_masked_artisan_by_id(order['artisan_id'])
        
        # Get artisan orders
        query = """
            SELECT o.*, c.id as customer_id
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            WHERE o.artisan_id = %s
            ORDER BY o.created_at DESC
        """
        
        orders = execute_query(query, (artisan_id,), fetchall=True, dict_cursor=True)
        
        if not orders:
            await message.answer(f"📭 Usta #{artisan_id} ({artisan['name']}) üçün hələ heç bir sifariş yoxdur.")
            return
        
        await message.answer(
            f"📋 *Usta #{artisan_id} ({artisan['name']}) sifarişləri*\n\n"
            f"Tapılmış sifarişlər: {len(orders)}",
            parse_mode="Markdown"
        )
        
        # Display each order
        for order in orders:
            # Müşteri bilgilerini al ve şifresini çöz
            customer_encrypted = get_customer_by_id(order.get('customer_id'))
            customer = decrypt_dict_data(customer_encrypted, mask=False) if customer_encrypted else None
            customer_name = customer.get('name', 'Təyin edilməyib') if customer else 'Təyin edilməyib'
            
            # Format date
            date_time = order.get('date_time')
            if isinstance(date_time, str):
                formatted_date = date_time
            else:
                formatted_date = date_time.strftime("%d.%m.%Y %H:%M") if date_time else "Bilinmiyor"
            
            # Format status
            status = order.get('status')
            if status == 'pending':
                status_text = "⏳ Gözləyir"
            elif status == 'accepted':
                status_text = "🟢 Qəbul edilib"
            elif status == 'completed':
                status_text = "✅ Tamamlanıb"
            elif status == 'cancelled':
                status_text = "❌ Ləğv edilib"
            else:
                status_text = status
            
            # Create order text
            order_text = (
                f"🔹 *Sifariş #{order.get('id')}*\n"
                f"📅 Tarix: {formatted_date}\n"
                f"👤 Müştəri: {customer_name}\n"
                f"🛠 Xidmət: {order.get('service', 'Təyin edilməyib')}\n"
                f"💰 Məbləğ: {order.get('price', 'Təyin edilməyib')} AZN\n"
                f"🔄 Status: {status_text}\n"
                f"📝 Qeyd: {order.get('note', '')}"
            )
            
            # Create action buttons
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                InlineKeyboardButton("ℹ️ Ətraflı Məlumat", callback_data=f"order_details_{order.get('id')}")
            )
            
            await message.answer(
                order_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        
    except Exception as e:
        logger.error(f"Error in show_artisan_orders: {e}")
        await message.answer("❌ Sifarişlər yüklənərkən xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")

@dp.callback_query_handler(lambda c: c.data == "back_to_admin")
async def back_to_admin_menu(callback_query: types.CallbackQuery):
    """Return to admin main menu"""
    try:
        if not is_admin(callback_query.from_user.id):
            await callback_query.answer("❌ Bu əməliyyat yalnızca admin istifadəçilər üçün əlçatandır.", show_alert=True)
            return
        
        # Create admin menu
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton("📋 Sifarişləri İdarə Et", callback_data="admin_orders"),
            InlineKeyboardButton("🧾 Ödəniş Qəbzlərini Yoxla", callback_data="admin_receipts"),
            InlineKeyboardButton("👤 İstifadəçiləri İdarə Et", callback_data="admin_users"),
            InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")
        )
        
        await callback_query.message.answer(
            "👨‍💼 *Admin İdarəetmə Paneli*\n\n"
            "Zəhmət olmasa, aşağıdakı bölmələrdən birini seçin:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Error in back_to_admin_menu: {e}")
        await callback_query.message.answer(
            "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
        )
        await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == "pay_customer_fine")
async def pay_customer_fine_callback(callback_query: types.CallbackQuery):
    """Handle pay fine button click"""
    try:
        # Butonun tıklandığını bildirin
        await callback_query.answer()
        
        # Telegram ID'yi alalım
        telegram_id = callback_query.from_user.id
        
        # Kullanıcı bilgilerini kontrol edelim
        customer = get_customer_by_telegram_id(telegram_id)
        
        if not customer:
            await callback_query.message.answer(
                "❌ Siz hələ müştəri kimi qeydiyyatdan keçməmisiniz."
            )
            return
                
        # Blok durumunu kontrol edelim
        is_blocked, reason, amount, block_until = get_customer_blocked_status(customer['id'])
        
        if not is_blocked:
            await callback_query.message.answer(
                "✅ Sizin hesabınız bloklanmayıb. Bütün xidmətlərdən istifadə edə bilərsiniz."
            )
            return
                
        # Ödeme talimatlarını gösterelim
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
        
        # Makbuz gönderme butonu ekleyin
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

@dp.callback_query_handler(lambda c: c.data.startswith('decline_refund_'))
async def decline_refund(callback_query: types.CallbackQuery):
    """Handle declining a refund by customer"""
    try:
        # Extract refund ID from callback data
        refund_id = int(callback_query.data.split('_')[-1])
        
        # Update refund status to declined
        from db import update_refund_request
        update_refund_request(refund_id, {
            'status': 'declined'
        })
        
        # Send confirmation to customer
        await callback_query.message.answer(
            "❌ Ödəniş qaytarılmasından imtina etdiniz."
        )
        
        # Get refund details
        from db import get_refund_request
        refund = get_refund_request(refund_id)
        
        if refund:
            # Notify admins about the declined refund
            for admin_id in BOT_ADMINS:
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=f"❌ *Ödəniş qaytarılmasından imtina*\n\n"
                             f"Sifariş #{refund.get('order_id')} üçün {refund.get('amount')} AZN "
                             f"məbləğində ödəniş qaytarılmasından müştəri imtina etdi.",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify admin {admin_id} about declined refund: {e}")
        
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Error in decline_refund: {e}")
        await callback_query.message.answer(
            "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
        )
        await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data.startswith('refund_completed_'))
async def mark_refund_completed(callback_query: types.CallbackQuery):
    """Handle marking refund as completed by admin"""
    try:
        # Check if user is admin
        if not is_admin(callback_query.from_user.id):
            await callback_query.answer("❌ Bu əməliyyat yalnızca admin istifadəçilər üçün əlçatandır.", show_alert=True)
            return
        
        # Extract refund ID from callback data
        refund_id = int(callback_query.data.split('_')[-1])
        admin_id = callback_query.from_user.id
        
        # Mark refund as completed
        from admin_service import complete_refund_process
        success = await complete_refund_process(refund_id, admin_id)
        
        if success:
            # Update message to reflect completion
            await bot.edit_message_text(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                text=callback_query.message.text + "\n\n✅ *Ödəniş tamamlandı!*",
                reply_markup=None,
                parse_mode="Markdown"
            )
            
            await callback_query.answer("Ödəniş tamamlandı və müştəriyə bildiriş göndərildi!")
        else:
            await callback_query.answer("❌ Ödəniş tamamlanarkən xəta baş verdi.", show_alert=True)
        
    except Exception as e:
        logger.error(f"Error in mark_refund_completed: {e}")
        await callback_query.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.", show_alert=True)

# Handle card details input from customer
@dp.message_handler(lambda message: len(message.text) >= 16 and re.match(r'^\d[\d\s]{14,}', message.text))
async def process_card_number_input(message: types.Message):
    """Process card number input from customer"""
    try:
        # Get user context
        telegram_id = message.from_user.id
        context = get_user_context(telegram_id)
        
        # Check if context is for providing card details
        if not context or context.get('action') != 'provide_card_details':
            # Not waiting for card details, ignore
            return
        
        # Clean and validate card number
        card_number = re.sub(r'\s', '', message.text)
        
        # Basic validation (this can be enhanced)
        if not re.match(r'^\\d{16,19}$', card_number):
            await message.answer(
                "❌ Düzgün kart nömrəsi daxil edin (16-19 rəqəm). Zəhmət olmasa, yenidən cəhd edin:"
            )
            return
        
        # Get refund ID from context
        refund_id = context.get('refund_id')
        if not refund_id:
            await message.answer(
                "❌ Kart məlumatlarınızı hazırda qəbul edə bilmirik. Zəhmət olmasa, sonra yenidən cəhd edin."
            )
            return
        
        # Get customer ID
        customer = get_customer_by_telegram_id(telegram_id)
        if not customer:
            await message.answer(
                "❌ Müştəri məlumatlarınız tapılmadı."
            )
            return
        
        # Process card details
        from admin_service import process_customer_card_details
        success = await process_customer_card_details(customer['id'], card_number, refund_id)
        
        if not success:
            await message.answer(
                "❌ Kart məlumatlarınız qeydə alınarkən xəta baş verdi. Zəhmət olmasa, sonra yenidən cəhd edin."
            )
            return
        
        # Clear user context
        clear_user_context(telegram_id)
        
    except Exception as e:
        logger.error(f"Error in process_card_number_input: {e}")
        await message.answer(
            "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
        )

@dp.message_handler(lambda message: message.text == "ℹ️ Əmr bələdçisi")
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
        keyboard.add("🏠 Əsas menyuya qayıt")
        
        await message.answer(guide_text, reply_markup=keyboard, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error in show_command_guide: {e}")
        await message.answer(
            "❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin."
        )

async def show_role_selection(message: types.Message):
    """Show role selection menu"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("👤 Müştəriyəm", "👷 Ustayam")
    keyboard.row("ℹ️ Əmr bələdçisi")
    
    if message.from_user.id in BOT_ADMINS:
        keyboard.add("👨‍💼 Admin")
    
    await message.answer(
        "Xoş gəldiniz! Rolunuzu seçin:",
        reply_markup=keyboard
    )
    
# Add to order_details view in bot.py
@dp.callback_query_handler(lambda c: c.data.startswith('request_refund_'))
async def initiate_refund_request(callback_query: types.CallbackQuery, state: FSMContext):
    """Initiate refund request as admin"""
    try:
        if not is_admin(callback_query.from_user.id):
            await callback_query.answer("❌ Bu əməliyyat yalnızca admin istifadəçilər üçün əlçatandır.", show_alert=True)
            return
        
        # Extract order ID from callback data
        order_id = int(callback_query.data.split('_')[-1])
        
        # Store order ID in state
        async with state.proxy() as data:
            data['refund_order_id'] = order_id
        
        # Ask for refund amount
        await callback_query.message.answer(
            f"💰 *Ödəniş qaytarılması başlat*\n\n"
            f"Sifariş #{order_id} üçün qaytarılacaq məbləği AZN ilə daxil edin (məs: 25):",
            parse_mode="Markdown"
        )
        
        # Set state to wait for amount
        await AdminRefundState.waiting_for_amount.set()
        
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Error in initiate_refund_request: {e}")
        await callback_query.message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
        await callback_query.answer()

@dp.message_handler(state=AdminRefundState.waiting_for_amount)
async def process_refund_amount(message: types.Message, state: FSMContext):
    """Process refund amount input"""
    try:
        # Get and validate amount
        amount_text = message.text.strip()
        
        try:
            refund_amount = float(amount_text.replace(',', '.'))
            if refund_amount <= 0:
                await message.answer("❌ Məbləğ müsbət olmalıdır. Zəhmət olmasa, yenidən daxil edin:")
                return
        except ValueError:
            await message.answer("❌ Düzgün məbləğ daxil edin (məsələn: 25). Zəhmət olmasa, yenidən cəhd edin:")
            return
        
        # Store amount in state
        async with state.proxy() as data:
            data['refund_amount'] = refund_amount
        
        # Ask for refund reason
        await message.answer(
            f"🔍 *Ödəniş qaytarılması səbəbi*\n\n"
            f"Zəhmət olmasa, ödəniş qaytarılmasının səbəbini daxil edin:",
            parse_mode="Markdown"
        )
        
        # Set state to wait for reason
        await AdminRefundState.waiting_for_reason.set()
        
    except Exception as e:
        logger.error(f"Error in process_refund_amount: {e}")
        await message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
        await state.finish()

@dp.message_handler(state=AdminRefundState.waiting_for_reason)
async def process_refund_reason(message: types.Message, state: FSMContext):
    """Process refund reason input and initiate refund request"""
    try:
        # Get reason
        reason = message.text.strip()
        
        if len(reason) < 3:
            await message.answer("❌ Səbəb ən azı 3 simvol olmalıdır. Zəhmət olmasa, yenidən daxil edin:")
            return
        
        # Get data from state
        data = await state.get_data()
        order_id = data.get('refund_order_id')
        refund_amount = data.get('refund_amount')
        
        if not order_id or not refund_amount:
            await message.answer("❌ Ödəniş qaytarılması məlumatları tapılmadı.")
            await state.finish()
            return
        
        # Initiate refund request
        from admin_service import request_customer_card_details
        success = await request_customer_card_details(order_id, refund_amount, reason)
        
        if success:
            await message.answer(
                f"✅ Ödəniş qaytarılması tələbi göndərildi.\n\n"
                f"Sifariş #{order_id} üçün {refund_amount} AZN məbləğində kart məlumatları tələb edildi.\n"
                f"Müştəri kart məlumatlarını göndərdikdən sonra sizə bildiriş ediləcək."
            )
        else:
            await message.answer("❌ Ödəniş qaytarılması tələbi göndərilə bilmədi. Zəhmət olmasa, bir az sonra yenidən cəhd edin.")
        
        # Clear state
        await state.finish()
        
    except Exception as e:
        logger.error(f"Error in process_refund_reason: {e}")
        await message.answer("❌ Xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.")
        await state.finish()

# Register all handlers
def register_all_handlers():
    """Register all message handlers"""

    # Register customer handlers
    handlers.customer_handler.register_handlers(dp)

    # Register artisan handlers
    handlers.artisan_handler.register_handlers(dp)

    dp.register_message_handler(show_command_guide, lambda message: message.text == "ℹ️ Əmr bələdçisi")
    
    # Register admin handlers - basic commands and buttons
    dp.register_message_handler(admin_panel, lambda message: message.text == "👨‍💼 Admin")
    dp.register_message_handler(admin_command, commands=['admin'])
    
    # Admin menu and general navigation
    dp.register_callback_query_handler(admin_menu_handlers, lambda c: c.data.startswith('admin_'))
    dp.register_callback_query_handler(back_to_admin_menu, lambda c: c.data == "back_to_admin")
    
    # Order related handlers
    dp.register_callback_query_handler(order_actions_handler, lambda c: c.data.startswith(('order_', 'filter_orders_')))
    
    # Receipt verification handlers
    dp.register_callback_query_handler(verify_receipt_handler, lambda c: c.data.startswith('verify_receipt_'))
    
    # User management handlers
    dp.register_callback_query_handler(user_actions_handler, lambda c: c.data in ['show_customers', 'show_artisans', 'search_user'])
    dp.register_callback_query_handler(user_block_actions, lambda c: c.data.startswith(('block_customer_', 'unblock_customer_', 'block_artisan_', 'unblock_artisan_')))
    dp.register_callback_query_handler(contact_user_actions, lambda c: c.data.startswith(('contact_customer_', 'contact_artisan_')))
    dp.register_callback_query_handler(user_orders_actions, lambda c: c.data.startswith(('customer_orders_', 'artisan_orders_')))
    
    # Search user handlers
    dp.register_callback_query_handler(select_search_type, lambda c: c.data.startswith('search_type_'), state="*")
    
    # Admin state handlers
    dp.register_message_handler(process_search_query, state=AdminSearchState.waiting_for_query)
    dp.register_message_handler(process_block_reason, state=AdminBlockState.waiting_for_reason)
    dp.register_message_handler(process_block_payment, state=AdminBlockState.waiting_for_payment)
    dp.register_message_handler(process_admin_message, state=AdminContactState.waiting_for_message)
    
    dp.register_callback_query_handler(initiate_refund_request, lambda c: c.data.startswith('request_refund_'), state="*")
    dp.register_message_handler(process_refund_amount, state=AdminRefundState.waiting_for_amount)
    dp.register_message_handler(process_refund_reason, state=AdminRefundState.waiting_for_reason)
    dp.register_callback_query_handler(decline_refund, lambda c: c.data.startswith('decline_refund_'))
    dp.register_callback_query_handler(mark_refund_completed, lambda c: c.data.startswith('refund_completed_'))
    
    logger.info("All handlers registered successfully!")

async def scheduled_tasks():
    """Run scheduled tasks at regular intervals"""
    while True:
        try:
            # Run payment status checks every 5 minutes
            from admin_service import check_payment_status_changes
            await check_payment_status_changes()
            
            # Sleep for 5 minutes
            await asyncio.sleep(5 * 60)  # 5 minutes
        except Exception as e:
            logger.error(f"Error in scheduled tasks: {e}")
            # Sleep for 1 minute in case of error
            await asyncio.sleep(60)

async def admin_webhook_handler(request):
    """Handle webhooks from admin panel"""
    try:
        data = await request.json()
        
        action = data.get('action')
        order_id = data.get('order_id')
        
        if not action or not order_id:
            return web.json_response({'status': 'error', 'message': 'Invalid parameters'})
        
        # Handle different actions
        if action == 'update_receipt_verification':
            is_verified = data.get('is_verified')
            # Convert string values to appropriate types
            if is_verified == 'null':
                is_verified = None
            elif is_verified == 'true':
                is_verified = True
            elif is_verified == 'false':
                is_verified = False
                
            await process_receipt_verification_update(order_id, is_verified)
            return web.json_response({'status': 'success'})
            
        elif action == 'update_admin_payment':
            is_completed = data.get('is_completed', False)
            # Convert string to boolean
            if isinstance(is_completed, str):
                is_completed = (is_completed.lower() == 'true')
                
            await process_admin_payment_completed_update(order_id, is_completed)
            return web.json_response({'status': 'success'})
        
        elif action == 'verify_customer_fine':
            receipt_id = data.get('receipt_id')
            is_verified = data.get('is_verified', False)
            admin_id = data.get('admin_id')
            
            # Convert string to boolean
            if isinstance(is_verified, str):
                is_verified = (is_verified.lower() == 'true')
                
            from admin_service import verify_customer_fine_receipt
            await verify_customer_fine_receipt(receipt_id, is_verified, admin_id)
            return web.json_response({'status': 'success'})
            
        else:
            return web.json_response({'status': 'error', 'message': 'Unknown action'})
            
    except Exception as e:
        logger.error(f"Error in admin webhook handler: {e}")
        return web.json_response({'status': 'error', 'message': str(e)})
    
if __name__ == '__main__':
    # Register all handlers
    register_all_handlers()
    
    # Start the bot
    executor.start_polling(dp, on_startup=on_startup, skip_updates=True)