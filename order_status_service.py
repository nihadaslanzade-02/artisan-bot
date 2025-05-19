# order_status_service.py dosyasını oluşturalım

import asyncio
import datetime
from aiogram import Bot, types
from aiogram.types import *
from dispatcher import bot, dp
from db import (
    get_artisan_by_id, get_customer_by_id, get_order_details,
    update_order_status, set_order_price, update_payment_method,
    get_connection
)
import logging
from db_encryption_wrapper import wrap_get_dict_function

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)



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

async def schedule_arrival_check(order_id, artisan_id, scheduled_time):
    """Belirli bir sipariş için varış kontrolü planlar"""
    try:
        # Calculate time until scheduled arrival
        now = datetime.datetime.now()
        
        # Convert scheduled_time to datetime if it's a string
        if isinstance(scheduled_time, str):
            try:
                scheduled_time = datetime.datetime.strptime(scheduled_time, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    # Try alternative format
                    scheduled_time = datetime.datetime.strptime(scheduled_time, "%Y-%m-%d %H:%M")
                except ValueError:
                    logger.error(f"Could not parse scheduled_time format for order {order_id}: {scheduled_time}")
                    # Use a default delay of 60 seconds
                    scheduled_time = now + datetime.timedelta(minutes=1)
        
        # Check if scheduled time is in the past
        time_diff = (scheduled_time - now).total_seconds()
        if time_diff < 0:
            # If less than 30 minutes in the past, send notification soon
            if abs(time_diff) < 1800:  # 30 minutes
                logger.warning(f"Scheduled time is slightly in the past for order {order_id}. Sending notification soon.")
                delay = 10  # Send notification after 10 seconds
            else:
                logger.warning(f"Scheduled time is too far in the past for order {order_id}. Using short delay.")
                delay = 30  # Use a short delay for testing
        else:
            delay = time_diff
            
            # For testing: uncomment to use a short delay
            # if delay > 60:
            #    logger.info(f"Using shortened delay for testing (original: {delay:.1f}s)")
            #    delay = 60
        
        # Schedule arrival check notification
        logger.info(f"Scheduling arrival check for order {order_id} in {delay} seconds")
        
        # Wait until scheduled time
        await asyncio.sleep(delay)
        
        # Check if order is still active
        order = get_order_details(order_id)
        if not order:
            logger.info(f"Order {order_id} not found for arrival check. Skipping.")
            return
            
        if order['status'] != 'accepted':
            logger.info(f"Order {order_id} is not in 'accepted' state (current: {order['status']}). Skipping arrival check.")
            return
        
        # Get artisan details
        artisan = wrap_get_dict_function(get_artisan_by_id)(order['artisan_id'])
        if not artisan:
            logger.error(f"Artisan {artisan_id} not found for arrival check")
            return
        
        telegram_id = artisan.get('telegram_id')
        if not telegram_id:
            logger.error(f"Telegram ID not found for artisan {artisan_id}")
            return
        
        # Create arrival confirmation keyboard
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("✅ Bəli, çatmışam", callback_data=f"arrived_{order_id}"),
            InlineKeyboardButton("⏱ 30 dəq. çatacam", callback_data=f"delayed_{order_id}")
        )
        
        # Send arrival check message
        try:
            await bot.send_message(
                chat_id=telegram_id,
                text=f"🕒 *Sifariş #{order_id} vaxtı çatdı*\n\n"
                     f"Müştərinin məkanına çatmısınızmı?",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            logger.info(f"Arrival check notification sent for order {order_id} to artisan {artisan_id}")
        except Exception as send_error:
            logger.error(f"Failed to send arrival notification: {send_error}")
        
    except Exception as e:
        logger.error(f"Error in schedule_arrival_check: {e}", exc_info=True)

async def check_order_acceptance(order_id, customer_id, timeout_seconds):
    """Sifarişin müəyyən müddət ərzində qəbul edilib-edilmədiyini yoxlayan funksiya"""
    try:
        if not order_id:
            logger.error("check_order_acceptance called with None order_id")
            return
            
        logger.info(f"Waiting {timeout_seconds} seconds to check order {order_id}")
        
        # Belirtilen süre kadar bekle
        await asyncio.sleep(timeout_seconds)
        
        # Siparişin güncel durumunu kontrol et
        order = get_order_details(order_id)
        
        if not order:
            logger.error(f"Order {order_id} not found in check_order_acceptance")
            return
            
        logger.info(f"Checking acceptance for order {order_id}, current status: {order['status']}")
            
        # Hala "searching" durumundaysa, siparişi iptal et
        if order['status'] == "searching":
            logger.info(f"Order {order_id} is still in 'searching' status, canceling")
            
            # Siparişi iptal et
            update_order_status(order_id, "cancelled")
            
            # Müşteriye bildir
            customer = get_customer_by_id(customer_id)
            if customer and customer.get('telegram_id'):
                # Müştəriyə bildiriş göndərmək
                await bot.send_message(
                    chat_id=customer['telegram_id'],
                    text=f"ℹ️ *Sifariş ləğv edildi*\n\n"
                         f"Təəssüf ki, yaxınlıqda uyğun usta tapılmadı.\n"
                         f"Zəhmət olmasa, yeni bir sifariş verin və ya daha sonra yenidən cəhd edin.",
                    parse_mode="Markdown"
                )
                logger.info(f"Customer notification sent about cancellation for order {order_id}")
                
                # Müştəri menyusunu göstər
                fake_message = types.Message.to_object({
                    'message_id': 0, 
                    'date': 0, 
                    'chat': {'id': customer['telegram_id'], 'type': 'private'}, 
                    'from': {'id': customer['telegram_id']}, 
                    'content_type': 'text', 
                    'text': ''
                })
                await show_customer_menu(fake_message)
            else:
                logger.error(f"Customer {customer_id} not found or telegram_id missing")
        else:
            logger.info(f"Order {order_id} status is {order['status']}, no need to cancel")
            
    except Exception as e:
        logger.error(f"Error in check_order_acceptance: {e}", exc_info=True)

async def notify_customer_about_arrival(order_id, status):
    """Müşteriye ustanın varış durumu hakkında bildirim gönderir"""
    try:
        # Get order details
        order = get_order_details(order_id)
        if not order:
            logger.error(f"Order {order_id} not found for arrival notification")
            return False
        
        # Get customer details
        customer = get_customer_by_id(order['customer_id'])
        if not customer:
            logger.error(f"Customer not found for order {order_id}")
            return False
        
        customer_telegram_id = customer.get('telegram_id')
        if not customer_telegram_id:
            logger.error(f"Customer telegram ID not found for order {order_id}")
            return False
        
        # Get artisan details
        artisan = wrap_get_dict_function(get_artisan_by_id)(order['artisan_id'])
        if not artisan:
            logger.error(f"Artisan not found for order {order_id}")
            return False
        
        artisan_name = artisan.get('name', 'Usta')
        
        # Prepare message based on status
        if status == "arrived":
            # Create confirmation keyboard
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("✅ Bəli, usta burdadır", callback_data=f"confirm_arrival_{order_id}"),
                InlineKeyboardButton("❌ Xeyr, usta yoxdur", callback_data=f"deny_arrival_{order_id}")
            )
            
            message_text = (
                f"📍 *Usta gəldi*\n\n"
                f"*{artisan_name}* sifarişinizin yerinə çatdığını bildirir. "
                f"Zəhmət olmasa, təsdiqləyin."
            )
            
            await bot.send_message(
                chat_id=customer_telegram_id,
                text=message_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
        elif status == "delayed":
            message_text = (
                f"⏱ *Usta gecikir*\n\n"
                f"*{artisan_name}* 30 dəqiqə ərzində sifarişinizin yerinə çatacağını bildirir."
            )
            
            await bot.send_message(
                chat_id=customer_telegram_id,
                text=message_text,
                parse_mode="Markdown"
            )
        
        return True
        
    except Exception as e:
        logger.error(f"Error in notify_customer_about_arrival: {e}")
        return False

async def handle_delayed_arrival(order_id):
    """Ustanın gecikmesi durumunu yönetir"""
    try:
        # Wait for 30 minutes
        await asyncio.sleep(30 * 60)  # 30 minutes
        
        # Check if order is still active
        order = get_order_details(order_id)
        if not order or order['status'] != 'accepted':
            logger.info(f"Order {order_id} is no longer active or not in accepted state. Skipping delayed arrival check.")
            return
        
        # Get artisan details
        artisan = wrap_get_dict_function(get_artisan_by_id)(order['artisan_id'])
        if not artisan:
            logger.error(f"Artisan not found for order {order_id}")
            return
        
        telegram_id = artisan.get('telegram_id')
        if not telegram_id:
            logger.error(f"Telegram ID not found for artisan {order_id}")
            return
        
        # Create arrival confirmation keyboard
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton("✅ Bəli, çatmışam", callback_data=f"arrived_{order_id}"),
            InlineKeyboardButton("❌ Çata bilmirəm", callback_data=f"cannot_arrive_{order_id}")
        )
        
        # Send arrival check message
        await bot.send_message(
            chat_id=telegram_id,
            text=f"⚠️ *Müddət bitdi*\n\n"
                 f"Sifariş #{order_id} üçün 30 dəqiqəlik müddət bitdi.\n"
                 f"Müştərinin məkanına çatmısınızmı?",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in handle_delayed_arrival: {e}")

async def handle_arrival_warning(order_id):
    """Ustanın varış uyarısını yönetir"""
    try:
        # Wait for 5 minutes
        await asyncio.sleep(5 * 60)  # 5 minutes
        
        # Check if order is still active
        order = get_order_details(order_id)
        if not order or order['status'] != 'accepted':
            logger.info(f"Order {order_id} is no longer active or not in accepted state. Skipping arrival warning.")
            return
        
        # Get customer details to ask again
        customer = get_customer_by_id(order['customer_id'])
        if not customer:
            logger.error(f"Customer not found for order {order_id}")
            return
        
        customer_telegram_id = customer.get('telegram_id')
        if not customer_telegram_id:
            logger.error(f"Customer telegram ID not found for order {order_id}")
            return
        
        # Create confirmation keyboard
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("✅ Bəli, usta indi burdadır", callback_data=f"confirm_arrival_{order_id}"),
            InlineKeyboardButton("❌ Xeyr, usta hələ də yoxdur", callback_data=f"final_deny_arrival_{order_id}")
        )
        
        # Ask customer one more time
        await bot.send_message(
            chat_id=customer_telegram_id,
            text=f"⚠️ *Son yoxlama*\n\n"
                 f"Usta sifarişinizin yerinə çatıbmı? Bu son xəbərdarlıqdır.",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error in handle_arrival_warning: {e}")

async def block_artisan_for_no_show(order_id):
    """Ustayı varış yapmaması nedeniyle bloklar"""
    try:
        # Get order details
        order = get_order_details(order_id)
        if not order:
            logger.error(f"Order {order_id} not found for blocking artisan")
            return False
        
        # Get artisan details
        artisan_id = order['artisan_id']
        artisan = wrap_get_dict_function(get_artisan_by_id)(artisan_id)
        if not artisan:
            logger.error(f"Artisan not found for order {order_id}")
            return False
        
        telegram_id = artisan.get('telegram_id')
        if not telegram_id:
            logger.error(f"Telegram ID not found for artisan {artisan_id}")
            return False
        
        # Get customer details
        customer = get_customer_by_id(order['customer_id'])
        if not customer:
            logger.error(f"Customer not found for order {order_id}")
            return False
        
        customer_telegram_id = customer.get('telegram_id')
        if not customer_telegram_id:
            logger.error(f"Customer telegram ID not found for order {order_id}")
            return False
        
        # Block artisan
        from db import block_artisan
        block_reason = f"Sifariş #{order_id} üçün məkana gəlmədiniz"
        required_payment = 30.0  # Default penalty amount
        
        success = block_artisan(artisan_id, block_reason, required_payment)
        
        if success:
            # Cancel the order
            update_order_status(order_id, "cancelled")
            
            # Notify artisan
            await bot.send_message(
                chat_id=telegram_id,
                text=f"⛔ *Hesabınız bloklandı*\n\n"
                     f"Səbəb: {block_reason}\n\n"
                     f"Bloku açmaq üçün {required_payment} AZN ödəniş etməlisiniz.\n"
                     f"Ödəniş etmək üçün: /pay_fine komandası ilə ətraflı məlumat ala bilərsiniz.",
                parse_mode="Markdown"
            )
            
            # Notify customer
            await bot.send_message(
                chat_id=customer_telegram_id,
                text=f"🎁 *Endirim qazandınız*\n\n"
                     f"Təəssüf ki, usta sifarişiniz üçün gəlmədi. Üzrxahlıq olaraq "
                     f"növbəti sifarişinizdə 10 AZN endirim qazandınız.\n\n"
                     f"Zəhmət olmasa, yeni bir sifariş verin.",
                parse_mode="Markdown"
            )
            
            # Save discount for the customer
            # This would need to be implemented in a new database table
            # For now, we'll just log it
            logger.info(f"Customer {customer['id']} received a 10 AZN discount for next order due to artisan no-show")
            
            return True
        else:
            logger.error(f"Failed to block artisan {artisan_id} for no-show")
            return False
        
    except Exception as e:
        logger.error(f"Error in block_artisan_for_no_show: {e}")
        return False

async def request_price_from_artisan(order_id):
    """Ustadan fiyat girişi ister"""
    try:
        # Get order details
        order = get_order_details(order_id)
        if not order:
            logger.error(f"Order {order_id} not found for price request")
            return False
        
        # Get artisan details
        artisan_id = order['artisan_id']
        artisan = wrap_get_dict_function(get_artisan_by_id)(artisan_id)
        if not artisan:
            logger.error(f"Artisan not found for order {order_id}")
            return False
        
        telegram_id = artisan.get('telegram_id')
        if not telegram_id:
            logger.error(f"Telegram ID not found for artisan {artisan_id}")
            return False
        
        # Send price request message
        await bot.send_message(
            chat_id=telegram_id,
            text=f"💰 *Qiymət təyin edin*\n\n"
                 f"Sifariş #{order_id} üçün qiymət təyin edin.\n"
                 f"Xidmətiniz üçün nə qədər ödəniş tələb edirsiniz?\n\n"
                 f"Zəhmət olmasa, qiyməti AZN ilə daxil edin (məsələn: 50):",
            parse_mode="Markdown"
        )
        
        # Set context to handle price input
        import datetime
        from db import set_user_context
        set_user_context(telegram_id, {
            "action": "set_price",
            "order_id": order_id,
            "deadline": datetime.datetime.now() + datetime.timedelta(minutes=30)
        })
        
        # Schedule reminder after 25 minutes
        asyncio.create_task(remind_price_setting(telegram_id, order_id, 25))
        
        return True
        
    except Exception as e:
        logger.error(f"Error in request_price_from_artisan: {e}")
        return False

async def remind_price_setting(telegram_id, order_id, minutes):
    """Ustaya fiyat belirlemesi için hatırlatma gönderir"""
    try:
        # Wait for specified minutes
        await asyncio.sleep(minutes * 60)
        
        # Check if price has been set
        order = get_order_details(order_id)
        if not order:
            logger.error(f"Order {order_id} not found for price reminder")
            return
        
        # If price is already set, skip reminder
        if order.get('price'):
            logger.info(f"Price already set for order {order_id}, skipping reminder")
            return
        
        # Get user context to check if still waiting for price
        from db import get_user_context
        context = get_user_context(telegram_id)
        
        if not context or context.get('action') != 'set_price' or context.get('order_id') != order_id:
            logger.info(f"User context changed, not waiting for price for order {order_id}")
            return
        
        # Send reminder
        await bot.send_message(
            chat_id=telegram_id,
            text=f"⚠️ *Xəbərdarlıq*\n\n"
                 f"Sifariş #{order_id} üçün qiyməti təyin etməyiniz xahiş olunur.\n"
                 f"5 dəqiqə ərzində qiyməti təyin etməsəniz, hesabınız bloklanacaq.",
            parse_mode="Markdown"
        )
        
        # Schedule final warning after 5 more minutes
        asyncio.create_task(final_price_warning(telegram_id, order_id))
        
    except Exception as e:
        logger.error(f"Error in remind_price_setting: {e}")

async def final_price_warning(telegram_id, order_id):
    """Ustaya fiyat belirlemesi için son uyarı gönderir"""
    try:
        # Wait for 5 minutes
        await asyncio.sleep(5 * 60)
        
        # Check if price has been set
        order = get_order_details(order_id)
        if not order:
            logger.error(f"Order {order_id} not found for final price warning")
            return
        
        # If price is already set, skip warning
        if order.get('price'):
            logger.info(f"Price already set for order {order_id}, skipping final warning")
            return
        
        # Get user context to check if still waiting for price
        from db import get_user_context
        context = get_user_context(telegram_id)
        
        if not context or context.get('action') != 'set_price' or context.get('order_id') != order_id:
            logger.info(f"User context changed, not waiting for price for order {order_id}")
            return
        
        # Clear context
        from db import clear_user_context
        clear_user_context(telegram_id)
        
        # Block artisan
        artisan_id = order['artisan_id']
        from db import block_artisan
        block_reason = f"Sifariş #{order_id} üçün qiyməti təyin etmədiniz"
        required_payment = 30.0  # Default penalty amount
        
        success = block_artisan(artisan_id, block_reason, required_payment)
        
        if success:
            # Cancel the order
            update_order_status(order_id, "cancelled")
            
            # Notify artisan
            await bot.send_message(
                chat_id=telegram_id,
                text=f"⛔ *Hesabınız bloklandı*\n\n"
                     f"Səbəb: {block_reason}\n\n"
                     f"Bloku açmaq üçün {required_payment} AZN ödəniş etməlisiniz.\n"
                     f"Ödəniş etmək üçün: /pay_fine komandası ilə ətraflı məlumat ala bilərsiniz.",
                parse_mode="Markdown"
            )
            
            # Notify customer
            customer = get_customer_by_id(order['customer_id'])
            if customer and customer.get('telegram_id'):
                await bot.send_message(
                    chat_id=customer['telegram_id'],
                    text=f"❌ *Sifariş ləğv edildi*\n\n"
                         f"Təəssüf ki, usta sifariş #{order_id} üçün qiyməti təyin etmədi.\n"
                         f"Sifarişiniz ləğv edildi. Zəhmət olmasa, yeni bir sifariş verin.",
                    parse_mode="Markdown"
                )
        
    except Exception as e:
        logger.error(f"Error in final_price_warning: {e}")