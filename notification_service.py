# notification_service.py

import asyncio
from config import *
import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dispatcher import bot, dp
from db import *
from db_encryption_wrapper import wrap_get_dict_function

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def notify_artisan_about_new_order(order_id, artisan_id):
    """Ustaya yeni sipariş hakkında bildirim gönderir"""
    try:
        # Use the non-masked version to get the correct telegram_id
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
        customer = wrap_get_dict_function(get_customer_by_id)(order.get('customer_id'))
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

# notification_service.py içindeki notify_customer_about_order_status fonksiyonunu güncelle

async def notify_customer_about_order_status(order_id, status):
    """Müşteriye sipariş durumu hakkında bildirim gönderir"""
    try:
        # Sipariş bilgilerini al
        order = get_order_details(order_id)
        if not order:
            logger.error(f"Error: Order not found. Order ID: {order_id}")
            return False
        
        # Müşteri ve usta bilgilerini al
        customer = wrap_get_dict_function(get_customer_by_id)(order.get('customer_id'))
        
        # Ustanın bilgilerini alıp şifrelerini manuel olarak çöz
        from crypto_service import decrypt_data
        from db_encryption_wrapper import decrypt_dict_data
        artisan = get_artisan_by_id(order.get('artisan_id'))
        
        if not customer or not artisan:
            logger.error(f"Error: Customer or artisan not found for order ID: {order_id}")
            return False
        
        # Kullanıcının Telegram ID'sini al
        telegram_id = customer.get('telegram_id')
        if not telegram_id:
            logger.error(f"Error: Customer has no Telegram ID. Order ID: {order_id}")
            return False
        
        artisan_id = order.get('artisan_id')
        
        # Usta bilgilerini deşifre et
        artisan = get_artisan_by_id(artisan_id)
        artisan_decrypted = decrypt_dict_data(artisan, mask=False)
        artisan_name = artisan_decrypted.get('name', 'Usta')
        artisan_phone = artisan_decrypted.get('phone', 'Telefon')

        # Duruma göre mesajı hazırla
        if status == "accepted":
            # Fiyat aralığını al - YENİ KOD
            price_range_text = ""
            subservice = order.get('subservice')
            if subservice:
                # Alt servis için fiyat aralığını al
                price_range = get_artisan_price_ranges(artisan_id, subservice)
                if price_range:
                    min_price = price_range.get('min_price', 0)
                    max_price = price_range.get('max_price', 0)
                    price_range_text = f"\n💰 Qiymət aralığı: {min_price}-{max_price} AZN"
        
            message_text = (
                f"✅ *Sifarişiniz qəbul edildi!*\n\n"
                f"Sifariş #{order_id}\n"
                f"Usta: {artisan_name}\n"
                f"Əlaqə: {artisan_phone}{price_range_text}\n\n"
                f"Usta sizinlə əlaqə saxlayacaq."
            )
        elif status == "completed":
            message_text = (
                f"✅ *Sifarişiniz tamamlandı!*\n\n"
                f"Sifariş #{order_id}\n"
                f"Xidmət: {order.get('service')}\n"
                f"Usta: {artisan_name}"
            )
        elif status == "cancelled":
            message_text = (
                f"❌ *Sifarişiniz ləğv edildi*\n\n"
                f"Sifariş #{order_id}\n"
                f"Xidmət: {order.get('service')}\n\n"
                f"Təəssüf ki, sifarişiniz ləğv edildi. Yeni bir sifariş vermək üçün *🔄 Rol seçiminə qayıt* düyməsinə basın."
            )
        else:
            message_text = (
                f"ℹ️ *Sifariş statusu yeniləndi*\n\n"
                f"Sifariş #{order_id}\n"
                f"Xidmət: {order.get('service')}\n"
                f"Status: {status}"
            )
        
        # Mesajı gönder
        await bot.send_message(
            chat_id=telegram_id,
            text=message_text,
            parse_mode="Markdown"
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error in notify_customer_about_order_status: {str(e)}")
        return False

async def notify_customer_no_artisan(customer_telegram_id, order_id):
    """Müşteriye usta bulunamadığı bildirimini gönderir"""
    try:
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        
        message_text = (
            f"🕐 *Bu sahədə bütün ustalarımız hazırda məşğuldur*\n\n"
            f"🔥 Yüksək tələbat səbəbindən bu xidmət sahəsindəki bütün peşəkar ustalarımız hazırda digər sifarişlərlə məşğuldur.\n"
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
        
        # Get customer details for the message in a safe way
        customer_name = "Müştəri"  # Default fallback name
        try:
            customer = get_customer_by_id(order['customer_id'])
            if customer:
                # Try to get and decrypt customer name
                from crypto_service import decrypt_data
                encrypted_name = customer.get('name')
                if encrypted_name:
                    decrypted_name = decrypt_data(encrypted_name)
                    if decrypted_name and decrypted_name != encrypted_name:
                        customer_name = decrypted_name
                    else:
                        logger.warning(f"Could not decrypt customer name for order {order_id}")
        except Exception as e:
            logger.error(f"Error getting customer name for price acceptance: {e}")
            # Continue with default name
        
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

# notification_service.py - notify_customer_about_pending_receipt funksiyasını düzəlt

async def notify_customer_about_invalid_receipt(order_id):
    """Notify customer about pending receipt verification"""
    try:
        # Get order details
        order = get_order_details(order_id)
        if not order:
            logger.error(f"Order {order_id} not found for receipt verification notification")
            return False
        
        # Get customer details
        customer = wrap_get_dict_function(get_customer_by_id)(order.get('customer_id'))
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
        
        # Send information message with 24 hour deadline
        await bot.send_message(
            chat_id=customer_telegram_id,
            text=f"⚠️ *Xəbərdarlıq: Qəbz gözləmədədir!*\n\n"
                 f"Sifariş #{order_id} üçün göndərdiyiniz ödəniş qəbzi yoxlanılır.\n\n"
                 f"24 saat ərzində inzibatçı tərəfindən doğrulanmasa, ödəniş qəbziniz avtomatik olaraq etibarsız sayılacaq. Zəhmət olmasa, əmin olun ki, göndərdiyiniz qəbz aşağıdakı karta {price:.2f} AZN məbləğində ödənişi göstərir:\n"
                 f"Kart nömrəsi: {ADMIN_CARD_NUMBER}\n"
                 f"Sahibi: {ADMIN_CARD_HOLDER}\n\n"
                 f"⚠️ *Diqqət*: 24 saat ərzində qəbziniz doğrulanmasa və ya etibarsız hesab edilərsə, hesabınız bloklanacaq və ümumi məbləğin 50%-i həcmində cərimə tətbiq ediləcək.\n\n"
                 f"Başqa qəbziniz varsa, aşağıdakı düyməni istifadə edərək göndərə bilərsiniz:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        # Schedule blocking after 24 hours if not paid
        import asyncio
        asyncio.create_task(block_customer_after_timeout(order_id, customer.get('id'), price))
        
        return True
    except Exception as e:
        logger.error(f"Error in notify_customer_about_invalid_receipt: {e}", exc_info=True)
        return False

async def block_customer_after_timeout(order_id, customer_id, required_payment):
    """Block customer after timeout if payment not made"""
    try:
        # Wait 24 hours
        await asyncio.sleep(24 * 60 * 60)  # 24 hours
        
        # Check again if receipt has been verified
        status = check_receipt_verification_status(order_id)
        
        if status == 'invalid' or status == 'pending':
            # Still not verified, block customer
            block_reason = f"Sifariş #{order_id} üçün etibarsız ödəniş qəbzi"

            penalty_amount = required_payment * 1.5

            success = block_customer(customer_id, block_reason, penalty_amount)
            
            if success:
                # Get customer telegram ID
                customer = get_customer_by_id(customer_id)
                if customer and customer.get('telegram_id'):
                    # Create an inline keyboard with a "Pay Fine" button
                    keyboard = InlineKeyboardMarkup()
                    keyboard.add(InlineKeyboardButton("💰 Cəriməni ödə", callback_data="pay_customer_fine"))

                    await bot.send_message(
                        chat_id=customer['telegram_id'],
                        text=f"⛔ <b>Hesabınız bloklandı</b>\n\n"
                             f"Səbəb: {block_reason}\n\n"
                             f"Bloku açmaq üçün {required_payment:.2f} AZN ödəniş etməlisiniz.\n"
                             f"Ödəniş etmək üçün aşağıdakı düyməni istifadə edin:",
                        reply_markup=keyboard,
                        parse_mode="HTML"
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
        
        # Get payment method to check if it's cash payment
        # If cash payment, no need to notify artisan about transfer
        payment_details = debug_order_payment(order_id)
        if payment_details and payment_details.get('payment_method') == 'cash':
            logger.info(f"Skipping payment transfer notification for cash payment. Order ID: {order_id}")
            return True
        
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
        customer = wrap_get_dict_function(get_customer_by_id)(order.get('customer_id'))
        
        # Ustanın bilgilerini alıp şifrelerini manuel olarak çöz ve maskele
        from crypto_service import decrypt_data
        from db_encryption_wrapper import decrypt_dict_data
        artisan = get_artisan_by_id(order.get('artisan_id'))
        
        if not customer or not artisan:
            logger.error(f"Customer or artisan not found for order {order_id}")
            return False
        
        # Get customer telegram ID
        telegram_id = customer.get('telegram_id')
        if not telegram_id:
            logger.error(f"Customer has no telegram ID for review request, order {order_id}")
            return False
        
        # Check if customer has already reviewed this order to prevent duplicate reviews
        from db import has_customer_reviewed_order
        if has_customer_reviewed_order(order_id, customer.get('id')):
            logger.info(f"Customer {customer.get('id')} has already reviewed order {order_id}, skipping review request")
            return True
        
        # Create review keyboard
        keyboard = InlineKeyboardMarkup(row_width=5)
        for i in range(1, 6):
            keyboard.insert(InlineKeyboardButton(f"{i}⭐", callback_data=f"review_{order_id}_{i}"))
        
        artisan_id = order.get('artisan_id')
        # Əvvəlki kod: artisan = get_artisan_by_id(artisan_id)
        from crypto_service import decrypt_data
        
        # db.py-dəki get_artisan_by_id funksiyası artıq deşifrə edilmiş versiya qaytarır,
        # amma bəzən ola bilər ki, deşifrələmə tam işləməsin
        artisan = get_artisan_by_id(artisan_id)
        
        # Əlavə təhlükəsizlik üçün əl ilə də deşifrə edirik
        artisan_decrypted = decrypt_dict_data(artisan, mask=False)
        artisan_name = artisan_decrypted.get('name', 'Usta')
        artisan_phone = artisan_decrypted.get('phone', 'Telefon')


        # Əgər məlumatlar hələ də şifrəlidirsə, əl ilə deşifrə etməyə çalışırıq
        if artisan_name and isinstance(artisan_name, str) and artisan_name.startswith("gAAAAA"):
            try:
                artisan_name = decrypt_data(artisan_name)
            except Exception as e:
                logger.error(f"Error decrypting artisan name: {e}")
                
        if artisan_phone and isinstance(artisan_phone, str) and artisan_phone.startswith("gAAAAA"):
            try:
                artisan_phone = decrypt_data(artisan_phone)
            except Exception as e:
                logger.error(f"Error decrypting artisan phone: {e}")

        # Send review request
        message_text = (
            f"⭐ *Xidməti qiymətləndirin*\n\n"
            f"Sifariş #{order_id} uğurla tamamlandı!\n"
            f"Usta: {artisan_name}\n"
            f"Xidmət: {order.get('service')}\n\n"
            f"Zəhmət olmasa, ustanın xidmətini qiymətləndirərək başqalarına da kömək edin."
        )
        
        await bot.send_message(
            chat_id=telegram_id,
            text=message_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error in send_review_request_to_customer: {str(e)}")
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
        
        # Get payment details from order_payments table
        payment_details = debug_order_payment(order_id)
        admin_fee = 0
        
        if payment_details and payment_details.get('admin_fee') is not None:
            admin_fee = float(payment_details.get('admin_fee'))
        else:
            # Fallback calculation if order_payments doesn't have admin_fee
            price = float(order.get('price', 0))
            commission_rate = 0
            for tier, info in COMMISSION_RATES.items():
                threshold = info.get("threshold")
                if threshold is not None and price <= threshold:
                    commission_rate = info["rate"] / 100
                    break
            admin_fee = round(price * commission_rate, 2)
        
        # Ensure admin_fee is not zero
        if admin_fee <= 0:
            logger.warning(f"Admin fee calculation for order {order_id} resulted in {admin_fee}. Using default calculation.")
            price = float(order.get('price', 0))
            admin_fee = round(price * 0, 2)  
        
        # Calculate total amount with penalty
        penalty_percentage = 0.15  # 15% penalty
        total_amount = admin_fee * (1 + penalty_percentage)
        
        # Create payment keyboard
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton(
            "📸 Ödəniş qəbzini göndər", 
            callback_data=f"resend_commission_{order_id}"
        ))
        
        # Send warning message with 18 hour deadline
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

async def cancel_order_notifications_for_other_artisans(order_id, accepted_artisan_id):
    """
    Cancels order notifications for all artisans except the one who accepted the order
    
    Args:
        order_id (int): ID of the order
        accepted_artisan_id (int): ID of the artisan who accepted the order
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get all artisans who might have received the notification
        from db import get_connection, execute_query
        from geo_helpers import calculate_distance
        
        # Get order details
        order = get_order_details(order_id)
        if not order:
            logger.error(f"Order {order_id} not found for notification cancellation")
            return False
        
        # Get artisans who may have received the notification
        query = """
            SELECT id, telegram_id 
            FROM artisans 
            WHERE active = TRUE 
            AND service = %s 
            AND id != %s
        """
        
        artisans = execute_query(query, (order['service'], accepted_artisan_id), fetchall=True)
        
        if not artisans:
            logger.info(f"No other artisans to cancel notifications for order {order_id}")
            return True
            
        cancellation_count = 0
        
        # Send cancellation message to all other artisans
        for artisan in artisans:
            artisan_id = artisan[0]
            artisan_telegram_id = artisan[1]
            
            if artisan_telegram_id:
                try:
                    # Try to edit any existing messages for this order
                    await bot.send_message(
                        chat_id=artisan_telegram_id,
                        text=f"ℹ️ *Sifariş artıq mövcud deyil*\n\n"
                             f"Sifariş #{order_id} başqa bir usta tərəfindən götürülüb.",
                        parse_mode="Markdown"
                    )
                    cancellation_count += 1
                except Exception as e:
                    logger.error(f"Error cancelling notification for artisan {artisan_id}: {e}")
        
        logger.info(f"Cancelled order notifications for {cancellation_count} artisans for order {order_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error in cancel_order_notifications_for_other_artisans: {e}", exc_info=True)
        return False