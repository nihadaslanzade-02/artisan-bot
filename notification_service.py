# notification_service.py

import asyncio
from config import *
import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dispatcher import bot, dp
from db import *

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def notify_artisan_about_new_order(order_id, artisan_id):
    """Ustaya yeni sipariş hakkında bildirim gönderir"""
    try:
        # Usta bilgilerini doğru almak için düzeltme
        artisan = get_artisan_by_id(artisan_id)
        order = get_order_details(order_id)
        
        if not artisan or not order:
            logger.error(f"Artisan or order not found. Artisan ID: {artisan_id}, Order ID: {order_id}")
            return False
        
        # Telegram ID'yi doğrudan kullanmak yerine dict'ten alıyoruz
        telegram_id = artisan.get('telegram_id')
        if not telegram_id:
            logger.error(f"Artisan telegram_id not found for artisan ID: {artisan_id}")
            return False
        
        # Müşteri bilgilerini al
        customer = get_customer_by_id(order.get('customer_id'))
        customer_name = customer.get('name', 'Müştəri') if customer else 'Müştəri'
        
        # Sipariş bilgilerini hazırla
        service = order.get('service', '')
        subservice = order.get('subservice', '')
        service_text = f"{service} ({subservice})" if subservice else service
        location_name = order.get('location_name', 'Müəyyən edilməmiş')
        
        # Format date and time
        date_time = order.get('date_time')
        try:
            import datetime
            dt_obj = datetime.datetime.strptime(str(date_time), "%Y-%m-%d %H:%M:%S")
            formatted_date = dt_obj.strftime("%d.%m.%Y")
            formatted_time = dt_obj.strftime("%H:%M")
        except Exception as e:
            print(f"Error formatting date: {e}")
            formatted_date = str(date_time).split(" ")[0] if date_time else "Bilinmiyor"
            formatted_time = str(date_time).split(" ")[1] if date_time and " " in str(date_time) else "Bilinmiyor"
        
        # Kabul/Ret düğmeli InlineKeyboard oluştur
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("✅ Qəbul et", callback_data=f"accept_order_{order_id}"),
            InlineKeyboardButton("❌ İmtina et", callback_data=f"reject_order_{order_id}")
        )
        
        # Bildirim mesajını hazırla
        message_text = (
            f"🔔 *Yeni sifariş #{order_id}*\n\n"
            f"👤 *Müştəri:* {customer_name}\n"
            f"🛠 *Xidmət:* {service_text}\n"
            f"📍 *Yer:* {location_name}\n"
            f"📅 *Tarix:* {formatted_date}\n"
            f"🕒 *Saat:* {formatted_time}\n"
            f"📝 *Qeyd:* {order.get('note', '')}\n\n"
            f"Zəhmət olmasa, sifarişi qəbul və ya imtina edin."
        )
        
        # Ustaya mesaj gönder
        await bot.send_message(
            chat_id=telegram_id,
            text=message_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        return True
    
    except Exception as e:
        logger.error(f"Error in notify_artisan_about_new_order: {e}", exc_info=True)
        return False

async def notify_customer_about_order_status(order_id, status):
    """Müşteriye sipariş durumu hakkında bildirim gönderir"""
    try:
        # Sipariş bilgilerini al
        order = get_order_details(order_id)
        if not order:
            logger.error(f"Error: Order not found. Order ID: {order_id}")
            return False
        
        # Müşteri ve usta bilgilerini al
        customer = get_customer_by_id(order.get('customer_id'))
        artisan = get_artisan_by_id(order.get('artisan_id'))
        
        if not customer or not artisan:
            logger.error(f"Error: Customer or artisan not found for order ID: {order_id}")
            return False
        
        customer_telegram_id = customer.get('telegram_id')
        if not customer_telegram_id:
            logger.error(f"Error: Customer telegram_id not found for customer ID: {order.get('customer_id')}")
            return False
        
        # Status mesajını hazırla
        message_text = ""
        reply_markup = None
        
        if status == "accepted":
            from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
            message_text = (
                f"✅ *Sifarişiniz qəbul edildi!*\n\n"
                f"Sifariş #{order_id} *{artisan.get('name')}* tərəfindən qəbul edildi.\n"
                f"📞 *Usta ilə əlaqə:* {artisan.get('phone')}\n\n"
                f"Usta sizinlə qısa zamanda əlaqə saxlayacaq."
            )
            
            # Ana menüye dönüş düğmesi
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(KeyboardButton("✅ Yeni sifariş ver"))
            keyboard.add(KeyboardButton("📜 Əvvəlki sifarişlərə bax"))
            keyboard.add(KeyboardButton("🌍 Yaxınlıqdakı ustaları göstər"))
            reply_markup = keyboard
            
        elif status == "rejected":
            message_text = (
                f"ℹ️ *Sifarişiniz təəssüf ki, usta tərəfindən imtina edildi*\n\n"
                f"Sifariş #{order_id} üçün yeni bir usta axtarışı aparılır.\n"
                f"Sizə tezliklə məlumat veriləcək."
            )
            
        # Müşteriye mesaj gönder
        await bot.send_message(
            chat_id=customer_telegram_id,
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
        return True
    
    except Exception as e:
        logger.error(f"Error in notify_customer_about_order_status: {e}")
        return False

async def notify_customer_no_artisan(customer_telegram_id, order_id):
    """Müşteriye usta bulunamadığı bildirimini gönderir"""
    try:
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        
        message_text = (
            f"❌ *Təəssüf ki, sifariş üçün usta tapılmadı*\n\n"
            f"Sifariş #{order_id} üçün yaxınlıqda uyğun usta tapılmadı.\n"
            f"Zəhmət olmasa, bir az sonra yenidən cəhd edin."
        )
        
        # Ana menüye dönüş düğmesi
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(KeyboardButton("✅ Yeni sifariş ver"))
        keyboard.add(KeyboardButton("📜 Əvvəlki sifarişlərə bax"))
        keyboard.add(KeyboardButton("🌍 Yaxınlıqdakı ustaları göstər"))
        
        # Müşteriye mesaj gönder
        await bot.send_message(
            chat_id=customer_telegram_id,
            text=message_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        return True
    
    except Exception as e:
        logger.error(f"Error in notify_customer_no_artisan: {e}")
        return False
    

# notification_service.py faylına bu funksiyəvi əlavə edin
async def notify_artisan_about_price_acceptance(order_id):
    """Notify artisan that customer has accepted the price"""
    try:
        # Get order details
        order = get_order_details(order_id)
        if not order:
            logger.error(f"Order {order_id} not found for price acceptance notification")
            return False
        
        # Fiyat kontrolünü sağlamlaştıralım
        price = order.get('price')
        if price is None:
            logger.error(f"Price not set for order {order_id}")
            return False
            
        try:
            # Fiyatı güvenli bir şekilde float'a dönüştürelim
            price_float = float(price)
        except (TypeError, ValueError):
            logger.error(f"Cannot convert price to float for order {order_id}. Price value: {price}")
            return False
        
        # Get artisan details
        artisan_id = order['artisan_id']
        artisan = get_artisan_by_id(artisan_id)
        
        if not artisan or not artisan.get('telegram_id'):
            logger.error(f"Artisan not found or telegram_id missing for order {order_id}")
            return False
        
        # Get customer details for the message
        customer = get_customer_by_id(order['customer_id'])
        customer_name = customer.get('name', 'Müştəri') if customer else 'Müştəri'
        
        # Send notification
        await bot.send_message(
            chat_id=artisan['telegram_id'],
            text=f"✅ *Qiymət qəbul edildi*\n\n"
                 f"Sifariş #{order_id} üçün təyin etdiyiniz {price_float:.2f} AZN məbləğindəki qiymət "
                 f"*{customer_name}* tərəfindən qəbul edildi.\n\n"
                 f"Müştəri indi ödəniş üsulunu seçir.",
            parse_mode="Markdown"
        )
        
        # Log successful notification
        logger.info(f"Price acceptance notification sent to artisan for order {order_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error in notify_artisan_about_price_acceptance: {e}", exc_info=True)
        return False
    

# Add or update the notify_customer_about_invalid_receipt function in notification_service.py

# notification_service.py - notify_customer_about_invalid_receipt funksiyasını düzəlt

async def notify_customer_about_invalid_receipt(order_id):
    """Notify customer about invalid receipt"""
    try:
        # Get order details
        order = get_order_details(order_id)
        if not order:
            logger.error(f"Order {order_id} not found for invalid receipt notification")
            return False
        
        # Get customer details
        customer = get_customer_by_id(order.get('customer_id'))
        if not customer:
            logger.error(f"Customer not found for order {order_id}")
            return False
        
        customer_telegram_id = customer.get('telegram_id')
        if not customer_telegram_id:
            logger.error(f"Customer telegram ID not found for order {order_id}")
            return False
        
        # Calculate required payment (total price, not 50%)
        price = float(order.get('price', 0))
        
        # Create payment keyboard
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton(
            "📸 Ödəniş qəbzini göndər", 
            callback_data=f"resend_receipt_{order_id}"
        ))
        
        # Send warning message with 1 hour deadline
        await bot.send_message(
            chat_id=customer_telegram_id,
            text=f"⚠️ *Xəbərdarlıq: Qəbz təsdiqlənmədi!*\n\n"
                 f"Sifariş #{order_id} üçün göndərdiyiniz ödəniş qəbzi doğrulanmadı.\n\n"
                 f"Zəhmət olmasa, 1 saat ərzində aşağıdakı karta {price:.2f} AZN məbləğində ödəniş edin:\n"
                 f"Kart nömrəsi: {ADMIN_CARD_NUMBER}\n"
                 f"Sahibi: {ADMIN_CARD_HOLDER}\n\n"
                 f"⚠️ *Diqqət*: 1 saat ərzində ödəniş edilməzsə, hesabınız bloklanacaq və ümumi məbləğin 50%-i həcmində cərimə tətbiq ediləcək.\n\n"
                 f"Ödənişi etdikdən sonra qəbzi göndərmək üçün aşağıdakı düyməni istifadə edin:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        # Schedule blocking after 1 hour if not paid
        import asyncio
        asyncio.create_task(block_customer_after_timeout(order_id, customer.get('id'), price))
        
        return True
    except Exception as e:
        logger.error(f"Error in notify_customer_about_invalid_receipt: {e}", exc_info=True)
        return False

async def block_customer_after_timeout(order_id, customer_id, required_payment):
    """Block customer after timeout if payment not made"""
    try:
        # Wait 1 hour
        await asyncio.sleep(60 * 60)  # 60 seconds * 60 minutes = 1 hour
        
        # Check again if receipt has been verified
        status = check_receipt_verification_status(order_id)
        
        if status == 'invalid':
            # Still not verified, block customer
            block_reason = f"Sifariş #{order_id} üçün etibarsız ödəniş qəbzi"

            penalty_amount = required_payment * 1.5

            success = block_customer(customer_id, block_reason, penalty_amount)
            
            if success:
                # Get customer telegram ID
                customer = get_customer_by_id(customer_id)
                if customer and customer.get('telegram_id'):
                    await bot.send_message(
                        chat_id=customer['telegram_id'],
                        text=f"⛔ *Hesabınız bloklandı*\n\n"
                             f"Səbəb: {block_reason}\n\n"
                             f"Bloku açmaq üçün {required_payment:.2f} AZN ödəniş etməlisiniz.\n"
                             f"Ödəniş etmək üçün: /pay_customer_fine komandası ilə ətraflı məlumat ala bilərsiniz.",
                        parse_mode="Markdown"
                    )
                    logger.info(f"Customer {customer_id} blocked for invalid receipt on order {order_id}")
                else:
                    logger.error(f"Could not notify customer {customer_id} about being blocked")
            else:
                logger.error(f"Failed to block customer {customer_id} after invalid receipt timeout")
    except Exception as e:
        logger.error(f"Error in block_customer_after_timeout: {e}", exc_info=True)


async def notify_artisan_about_payment_transfer(order_id):
    """Notify artisan about payment transfer"""
    try:
        # Get order details
        order = get_order_details(order_id)
        if not order:
            logger.error(f"Order {order_id} not found for payment transfer notification")
            return False
        
        # Get artisan details
        artisan_id = order.get('artisan_id')
        artisan = get_artisan_by_id(artisan_id)
        if not artisan:
            logger.error(f"Artisan not found for order {order_id}")
            return False
        
        telegram_id = artisan.get('telegram_id')
        if not telegram_id:
            logger.error(f"Telegram ID not found for artisan {artisan_id}")
            return False
        
        # Get payment amount
        artisan_amount = 0
        try:
            from db import execute_query
            query = "SELECT artisan_amount FROM order_payments WHERE order_id = %s"
            result = execute_query(query, (order_id,), fetchone=True)
            if result:
                artisan_amount = float(result[0])
        except Exception as e:
            logger.error(f"Error getting artisan_amount: {e}")
        
        # Send payment notification
        await bot.send_message(
            chat_id=telegram_id,
            text=f"💰 *Ödəniş köçürüldü*\n\n"
                 f"Sifariş #{order_id} üçün ödəniş hesabınıza köçürüldü.\n"
                 f"Məbləğ: {artisan_amount:.2f} AZN\n\n"
                 f"Yeni sifarişlər qəbul etməyə davam edə bilərsiniz. Təşəkkür edirik!",
            parse_mode="Markdown"
        )
        
        return True
    except Exception as e:
        logger.error(f"Error in notify_artisan_about_payment_transfer: {e}")
        return False
    

# Add this to notification_service.py

async def send_review_request_to_customer(order_id):
    """Send a review request to the customer after order completion"""
    try:
        # Get order details
        order = get_order_details(order_id)
        if not order:
            logger.error(f"Order {order_id} not found for review request")
            return False
        
        # Get customer and artisan information
        customer = get_customer_by_id(order.get('customer_id'))
        artisan = get_artisan_by_id(order.get('artisan_id'))
        
        if not customer or not artisan:
            logger.error(f"Customer or artisan not found for order {order_id}")
            return False
            
        telegram_id = customer.get('telegram_id')
        if not telegram_id:
            logger.error(f"Customer telegram ID not found for order {order_id}")
            return False
        
        # Create keyboard with rating options
        keyboard = InlineKeyboardMarkup(row_width=5)
        rating_buttons = []
        for i in range(1, 6):  # 1 to 5 stars
            stars = "⭐" * i
            rating_buttons.append(InlineKeyboardButton(
                stars, callback_data=f"rate_{order_id}_{i}"
            ))

        keyboard.row(*rating_buttons[:3])  # First row with 1-3 stars
        keyboard.row(*rating_buttons[3:])  # Second row with 4-5 stars
        
        # Add skip button
        keyboard.add(InlineKeyboardButton(
            "⏭️ Keçin", callback_data=f"skip_rating_{order_id}"
        ))
        
        # Send review request
        await bot.send_message(
            chat_id=telegram_id,
            text=f"✅ *Sifarişiniz tamamlandı!*\n\n"
                 f"*{artisan.get('name')}* tərəfindən göstərilən xidməti qiymətləndirməyinizi xahiş edirik.\n\n"
                 f"*Sifariş:* #{order_id}\n"
                 f"*Xidmət:* {order.get('service')}\n\n"
                 f"Zəhmət olmasa, 1-dən 5-ə qədər ulduz seçin:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        logger.info(f"Review request sent to customer for order {order_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error in send_review_request_to_customer: {e}", exc_info=True)
        return False
    
# notification_service.py içine bu fonksiyonu ekleyelim

async def notify_artisan_about_invalid_commission(order_id):
    """Notify artisan about invalid commission receipt"""
    try:
        # Get order details
        order = get_order_details(order_id)
        if not order:
            logger.error(f"Order {order_id} not found for invalid commission notification")
            return False
        
        # Get artisan details
        artisan = get_artisan_by_id(order.get('artisan_id'))
        if not artisan:
            logger.error(f"Artisan not found for order {order_id}")
            return False
        
        artisan_telegram_id = artisan.get('telegram_id')
        if not artisan_telegram_id:
            logger.error(f"Artisan telegram ID not found for order {order_id}")
            return False
        
        # Calculate required payment (admin fee plus penalty)
        admin_fee = float(order.get('admin_fee', 0))
        penalty_percentage = 0.15  # 15% penalty
        total_amount = admin_fee * (1 + penalty_percentage)
        
        # Create payment keyboard
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton(
            "📸 Ödəniş qəbzini göndər", 
            callback_data=f"resend_commission_{order_id}"
        ))
        
        # Send warning message with 1 hour deadline
        await bot.send_message(
            chat_id=artisan_telegram_id,
            text=f"⚠️ *Xəbərdarlıq: Komissiya qəbzi təsdiqlənmədi!*\n\n"
                 f"Sifariş #{order_id} üçün göndərdiyiniz komissiya ödənişi qəbzi doğrulanmadı.\n\n"
                 f"Zəhmət olmasa, 18 saat ərzində aşağıdakı karta {admin_fee:.2f} AZN məbləğində ödəniş edin:\n"
                 f"Kart nömrəsi: {ADMIN_CARD_NUMBER}\n"
                 f"Sahibi: {ADMIN_CARD_HOLDER}\n\n"
                 f"⚠️ *Diqqət*: 18 saat ərzində ödəniş edilməzsə, hesabınız bloklanacaq və əlavə cərimə tətbiq ediləcək.\n\n"
                 f"Ödənişi etdikdən sonra qəbzi göndərmək üçün aşağıdakı düyməni istifadə edin:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        # Schedule blocking after delay if not paid
        import asyncio
        asyncio.create_task(block_artisan_after_timeout(order_id, artisan.get('id'), total_amount))
        
        return True
    except Exception as e:
        logger.error(f"Error in notify_artisan_about_invalid_commission: {e}", exc_info=True)
        return False

# notification_service.py içindeki block_artisan_after_timeout fonksiyonunu güncelleyelim

async def block_artisan_after_timeout(order_id, artisan_id, required_payment):
    """Block artisan after timeout if payment not made"""
    try:
        # Wait 24 hours
        await asyncio.sleep(18 * 60 * 60)  # 24 hours
        
        # Check if artisan has resubmitted a receipt
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT COUNT(*) FROM notification_log
            WHERE notification_type = 'commission_resubmitted'
            AND target_id = %s
            AND created_at > NOW() - INTERVAL '18 hours'
            """,
            (order_id,)
        )
        
        resubmitted = cursor.fetchone()[0] > 0
        conn.close()
        
        if resubmitted:
            logger.info(f"Blocking cancelled for artisan {artisan_id} on order {order_id} - receipt resubmitted")
            return
        
        # Check again if receipt has been verified
        status = check_receipt_verification_status(order_id)
        
        if status == 'invalid':
            # Still not verified, block artisan
            block_reason = f"Sifariş #{order_id} üçün etibarsız komissiya ödənişi qəbzi"
            
            # Add additional penalty
            penalty_amount = required_payment * 1.5  # 50% additional penalty
            
            success = block_artisan(artisan_id, block_reason, penalty_amount)
            
            if success:
                # Get artisan telegram ID
                artisan = get_artisan_by_id(artisan_id)
                if artisan and artisan.get('telegram_id'):
                    await bot.send_message(
                        chat_id=artisan['telegram_id'],
                        text=f"⛔ *Hesabınız bloklandı*\n\n"
                             f"Səbəb: {block_reason}\n\n"
                             f"Bloku açmaq üçün {penalty_amount:.2f} AZN ödəniş etməlisiniz.\n"
                             f"Ödəniş etmək üçün: /pay_fine komandası ilə ətraflı məlumat ala bilərsiniz.",
                        parse_mode="Markdown"
                    )
                    logger.info(f"Artisan {artisan_id} blocked for invalid commission receipt on order {order_id}")
                else:
                    logger.error(f"Could not notify artisan {artisan_id} about being blocked")
            else:
                logger.error(f"Failed to block artisan {artisan_id} after invalid receipt timeout")
    except Exception as e:
        logger.error(f"Error in block_artisan_after_timeout: {e}", exc_info=True)

# notification_service.py içinde yeni bir fonksiyon ekleyelim

async def notify_artisan_commission_receipt_received(artisan_id, order_id):
    """Notify artisan that commission receipt was received and will be reviewed"""
    try:
        # Get artisan details
        artisan = get_artisan_by_id(artisan_id)
        if not artisan:
            logger.error(f"Artisan {artisan_id} not found for receipt notification")
            return False
        
        telegram_id = artisan.get('telegram_id')
        if not telegram_id:
            logger.error(f"Telegram ID not found for artisan {artisan_id}")
            return False
        
        # Send notification to artisan
        await bot.send_message(
            chat_id=telegram_id,
            text=f"✅ *Komissiya qəbzi qəbul edildi*\n\n"
                f"Sifariş #{order_id} üçün göndərdiyiniz yeni komissiya ödənişi qəbzi qəbul edildi və yoxlanılması üçün göndərildi.\n\n"
                f"Qəbz təsdiqlənənə qədər bloklanma prosesi dayandırıldı. Ədalətli iş mühiti üçün gələcəkdə düzgün ödəniş qəbzləri göndərdiyinizə əmin olun.\n\n"
                f"Təşəkkür edirik!",
            parse_mode="Markdown"
        )
        
        return True
    except Exception as e:
        logger.error(f"Error in notify_artisan_commission_receipt_received: {e}")
        return False