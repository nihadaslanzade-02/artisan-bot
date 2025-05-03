# payment_service.py dosyasını oluşturalım

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dispatcher import bot, dp
from db import (
    get_artisan_by_id, get_customer_by_id, get_order_details,
    set_order_price, update_payment_method, save_payment_receipt,
    get_connection, set_user_context, clear_user_context
)
import logging
import asyncio
import datetime
from config import COMMISSION_RATES, ADMIN_CARD_NUMBER, ADMIN_CARD_HOLDER

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def notify_customer_about_price(order_id, price):
    """Müşteriye belirlenen fiyat hakkında bildirim gönderir"""
    try:
        # Get order details
        order = get_order_details(order_id)
        if not order:
            logger.error(f"Order {order_id} not found for price notification")
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
        artisan = get_artisan_by_id(order['artisan_id'])
        if not artisan:
            logger.error(f"Artisan not found for order {order_id}")
            return False
        
        artisan_name = artisan.get('name', 'Usta')
        
        # Create confirmation keyboard
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("✅ Qəbul edirəm", callback_data=f"accept_price_{order_id}"),
            InlineKeyboardButton("❌ Qəbul etmirəm", callback_data=f"reject_price_{order_id}")
        )
        
        # Send price notification to customer
        await bot.send_message(
            chat_id=customer_telegram_id,
            text=f"💰 *Təyin edilmiş qiymət*\n\n"
                 f"Usta *{artisan_name}* sifariş #{order_id} üçün "
                 f"*{price} AZN* məbləğində qiymət təyin etdi.\n\n"
                 f"Bu qiyməti qəbul edirsinizmi?",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error in notify_customer_about_price: {e}")
        return False

# In payment_service.py - modify notify_customer_about_payment_options
# payment_service.py faylında notify_customer_about_payment_options funksiyasını düzəldin

async def notify_customer_about_payment_options(order_id):
    """Müşteriye ödeme seçeneklerini gösterir"""
    try:
        # Get order details with proper error checking
        order = get_order_details(order_id)
        
        if not order:
            logger.error(f"Order {order_id} not found")
            return False
        
        # Ensure price exists and is valid
        price_value = order.get('price')
        if price_value is None:
            logger.error(f"Order {order_id} price not set")
            return False
            
        # Ensure price is a valid number
        try:
            price = float(price_value)
        except (TypeError, ValueError):
            logger.error(f"Invalid price value for order {order_id}: {price_value}")
            return False
        
        # Calculate commission
        commission_rate = 0.12  # Default rate (12%)
        for tier, info in COMMISSION_RATES.items():
            if price <= info["threshold"]:
                commission_rate = info["rate"] / 100
                break
        
        admin_fee = round(price * commission_rate, 2)
        artisan_amount = price - admin_fee
        
        # Update values in database to ensure consistency
        set_order_price(order_id, price, admin_fee, artisan_amount)
        
        # Create payment method keyboard
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("💳 Kartla ödəniş", callback_data=f"pay_card_{order_id}"),
            InlineKeyboardButton("💵 Nağd ödəniş", callback_data=f"pay_cash_{order_id}")
        )
        
        # Send payment options to customer
        customer_id = order.get('customer_id')
        customer = get_customer_by_id(customer_id)
        
        if not customer or not customer.get('telegram_id'):
            logger.error(f"Customer not found or missing telegram_id for order {order_id}")
            return False
            
        await bot.send_message(
            chat_id=customer['telegram_id'],
            text=f"💰 *Ödəniş üsulunu seçin*\n\n"
                 f"Sifariş #{order_id} üçün ödəniş məbləği: *{price:.2f} AZN*\n\n"
                 f"Zəhmət olmasa, ödəniş üsulunu seçin:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        # Log successful notification
        logger.info(f"Payment options notification sent for order {order_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error in notify_customer_about_payment_options: {e}", exc_info=True)
        return False
    

async def notify_artisan_about_payment_method(order_id, payment_method):
    """Ustaya seçilen ödeme yöntemi hakkında bildirim gönderir"""
    try:
        # Get order details
        order = get_order_details(order_id)
        if not order:
            logger.error(f"Order {order_id} not found for payment method notification")
            return False
        
        # Get artisan details
        artisan_id = order['artisan_id']
        artisan = get_artisan_by_id(artisan_id)
        if not artisan:
            logger.error(f"Artisan not found for order {order_id}")
            return False
        
        telegram_id = artisan.get('telegram_id')
        if not telegram_id:
            logger.error(f"Telegram ID not found for artisan {artisan_id}")
            return False
        
        # Get price information and ensure it's a valid number
        price = float(order.get('price', 0))
        
        # Calculate commission based on price
        commission_rate = 0.12  # Default rate (12%)
        
        for tier, info in COMMISSION_RATES.items():
            threshold = info.get("threshold")
            if threshold is not None and price <= threshold:
                commission_rate = info["rate"] / 100  # Convert percentage to decimal
                break
        
        admin_fee = round(price * commission_rate, 2)
        artisan_amount = price - admin_fee
        
        message_text = ""
        reply_markup = None
        
        if payment_method == "card":
            # Card payment
            message_text = (
                f"💳 *Kartla ödəniş seçildi*\n\n"
                f"Sifariş: #{order_id}\n"
                f"Məbləğ: {price} AZN\n"
                f"Komissiya ({int(commission_rate*100)}%): {admin_fee} AZN\n"
                f"Sizə qalacaq: {artisan_amount} AZN\n\n"
                f"Müştəri ödənişi kart ilə edəcək. "
                f"Ödəniş tamamlandıqdan sonra 24 saat ərzində hesabınıza köçürüləcək."
            )
            reply_markup = None
        else:
            # Cash payment
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton(
                "✅ Ödənişi təsdiqlə", 
                callback_data=f"confirm_art_payment_{order_id}"
            ))
            
            message_text = (
                f"💵 *Nağd ödəniş seçildi*\n\n"
                f"Sifariş: #{order_id}\n"
                f"Ümumi məbləğ: {price} AZN\n"
                f"Komissiya ({int(commission_rate*100)}%): {admin_fee} AZN\n"
                f"Sizə qalacaq: {artisan_amount} AZN\n\n"
                f"Müştəridən ödənişi aldıqdan sonra, 24 saat ərzində komissiya məbləğini "
                f"admin kartına köçürməlisiniz.\n\n"
                f"Admin kart məlumatları:\n"
                f"Kart nömrəsi: {ADMIN_CARD_NUMBER}\n"
                f"Sahibi: {ADMIN_CARD_HOLDER}\n\n"
                f"⚠️ *Diqqət*: 24 saat ərzində komissiya ödənişi edilməzsə, "
                f"hesabınız avtomatik bloklanacaq və məbləğin 15%-i həcmində əlavə cərimə tətbiq ediləcək."
            )
            
            reply_markup = None
        
        # Send notification to artisan
        await bot.send_message(
            chat_id=telegram_id,
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
        # Update payment method in database
        success = update_payment_method(order_id, payment_method)
        if not success:
            logger.error(f"Failed to update payment method for order {order_id}")
        
        # Log successful notification
        logger.info(f"Payment method notification sent to artisan for order {order_id}: {payment_method}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error in notify_artisan_about_payment_method: {e}", exc_info=True)
        return False


async def notify_customer_about_card_payment(order_id):
    """Müşteriye kart ödeme bilgileri gönderir"""
    try:
        # Get order details
        order = get_order_details(order_id)
        if not order:
            logger.error(f"Order {order_id} not found for card payment notification")
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
        artisan = get_artisan_by_id(order['artisan_id'])
        if not artisan:
            logger.error(f"Artisan not found for order {order_id}")
            return False
        
        # Get payment details
        card_number = artisan.get('payment_card_number')
        card_holder = artisan.get('payment_card_holder')
        
        if not card_number:
            # If artisan doesn't have a card set, use admin card
            card_number = ADMIN_CARD_NUMBER
            card_holder = ADMIN_CARD_HOLDER
        
        # Create payment confirmation keyboard
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton(
            "✅ Ödənişi tamamladım", 
            callback_data=f"payment_completed_{order_id}"
        ))
        
        # Send card payment details to customer
        await bot.send_message(
            chat_id=customer_telegram_id,
            text=f"💳 *Kartla ödəniş*\n\n"
                 f"Sifariş: #{order_id}\n"
                 f"Məbləğ: {order.get('price', 0)} AZN\n\n"
                 f"Ödəniş məlumatları:\n"
                 f"Kart nömrəsi: {card_number}\n"
                 f"Kart sahibi: {card_holder}\n\n"
                 f"Zəhmət olmasa, ödənişi tamamladıqdan sonra aşağıdakı düyməni basın və "
                 f"ödəniş qəbzini şəkil olaraq göndərin.",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error in notify_customer_about_card_payment: {e}")
        return False

async def notify_customer_about_cash_payment(order_id):
    """Müşteriye nakit ödeme hakkında bildirim gönderir"""
    try:
        # Get order details
        order = get_order_details(order_id)
        if not order:
            logger.error(f"Order {order_id} not found for cash payment notification")
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
        
        # Create payment confirmation keyboard
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton(
            "✅ Nağd ödənişi etdim", 
            callback_data=f"cash_payment_made_{order_id}"
        ))
        
        # Send cash payment notification to customer
        await bot.send_message(
            chat_id=customer_telegram_id,
            text=f"💵 *Nağd ödəniş*\n\n"
                 f"Sifariş: #{order_id}\n"
                 f"Məbləğ: {order.get('price', 0)} AZN\n\n"
                 f"Zəhmət olmasa, ödənişi ustaya nağd şəkildə edin və "
                 f"ödənişi etdikdən sonra aşağıdakı düyməni basın.\n\n"
                 f"⚠️ Diqqət: Ustadan ödənişi aldığına dair təsdiq istəniləcək.",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error in notify_customer_about_cash_payment: {e}")
        return False

async def handle_admin_payment_deadline(order_id):
    """Ustanın admin ödeme süre sınırını yönetir"""
    try:
        # Wait for 24 hours
        await asyncio.sleep(24 * 60 * 60)  # 24 hours
        
        # Get order details
        order = get_order_details(order_id)
        if not order:
            logger.error(f"Order {order_id} not found for admin payment deadline")
            return
        
        # Check if commission has been paid
        # This would require additional database fields to track commission payment status
        # For now, we'll assume it hasn't been paid
        
        # Get payment details
        payment_method = order.get('payment_method', '')
        if payment_method != 'cash':
            logger.info(f"Order {order_id} is not cash payment, skipping admin payment deadline")
            return
        
        # Get artisan details
        artisan_id = order['artisan_id']
        artisan = get_artisan_by_id(artisan_id)
        if not artisan:
            logger.error(f"Artisan not found for order {order_id}")
            return
        
        telegram_id = artisan.get('telegram_id')
        if not telegram_id:
            logger.error(f"Telegram ID not found for artisan {artisan_id}")
            return
        
        # Calculate fee and fine
        price = order.get('price', 0)
        commission_rate = 0.12  # Default rate (12%)
        
        for tier, info in COMMISSION_RATES.items():
            if price <= info["threshold"]:
                commission_rate = info["rate"] / 100  # Convert percentage to decimal
                break
        
        admin_fee = round(price * commission_rate, 2)
        fine_percentage = 0.15  # 15% fine
        fine_amount = round(admin_fee * fine_percentage, 2)
        total_amount = admin_fee + fine_amount
        
        # Send warning to artisan
        await bot.send_message(
            chat_id=telegram_id,
            text=f"⚠️ *Komissiya ödənişi xəbərdarlığı*\n\n"
                 f"Sifariş #{order_id} üçün komissiya ödənişi müddəti bitdi.\n\n"
                 f"İlkin komissiya: {admin_fee} AZN\n"
                 f"Əlavə cərimə (15%): {fine_amount} AZN\n"
                 f"Ödənilməli məbləğ: {total_amount} AZN\n\n"
                 f"Bu məbləği 6 saat ərzində ödəməsəniz, hesabınız bloklanacaq.\n"
                 f"Ödəniş etmək üçün admin kart məlumatları:\n"
                 f"Kart nömrəsi: {ADMIN_CARD_NUMBER}\n"
                 f"Sahibi: {ADMIN_CARD_HOLDER}",
            parse_mode="Markdown"
        )
        
        # Schedule blocking after 6 more hours if not paid
        asyncio.create_task(block_artisan_for_nonpayment(order_id, artisan_id, total_amount, 6))
        
    except Exception as e:
        logger.error(f"Error in handle_admin_payment_deadline: {e}")

async def block_artisan_for_nonpayment(order_id, artisan_id, amount, hours):
    """Ödeme yapmaması durumunda ustayı bloklar"""
    try:
        # Wait for specified hours
        await asyncio.sleep(hours * 60 * 60)
        
        # Check if payment has been made
        # This would require additional database fields
        # For now, assume it hasn't been paid
        
        # Block artisan
        from db import block_artisan
        block_reason = f"Sifariş #{order_id} üçün komissiya ödənişi edilmədi"
        
        success = block_artisan(artisan_id, block_reason, amount)
        
        if success:
            # Get artisan telegram ID
            artisan = get_artisan_by_id(artisan_id)
            if not artisan or not artisan.get('telegram_id'):
                logger.error(f"Could not get telegram ID for artisan {artisan_id}")
                return
            
            # Notify artisan
            await bot.send_message(
                chat_id=artisan['telegram_id'],
                text=f"⛔ *Hesabınız bloklandı*\n\n"
                     f"Səbəb: {block_reason}\n\n"
                     f"Bloku açmaq üçün {amount} AZN ödəniş etməlisiniz.\n"
                     f"Ödəniş etmək üçün: /pay_fine komandası ilə ətraflı məlumat ala bilərsiniz.",
                parse_mode="Markdown"
            )
        
    except Exception as e:
        logger.error(f"Error in block_artisan_for_nonpayment: {e}")