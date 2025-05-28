# admin_service.py

import logging
from dispatcher import *
from db import *
from notification_service import *
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from db_encryption_wrapper import wrap_get_dict_function, wrap_get_list_function
from crypto_service import mask_card_number, mask_phone, mask_name

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)



async def process_receipt_verification_update(order_id, is_verified):
    """Process receipt verification status update from admin
    
    Args:
        order_id (int): ID of the order
        is_verified (bool or None): Verification status
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Log the action for debugging
        logger.info(f"Processing receipt verification update for order {order_id}. Verified: {is_verified}")
        
        # Update status in database
        status_updated = update_receipt_verification_status(order_id, is_verified)
        
        if not status_updated:
            logger.error(f"Failed to update verification status for order {order_id}")
            return False
        
        # If verification is False (invalid), notify appropriate user
        if is_verified is False:
            # Get payment method to determine which type of receipt was rejected
            payment_details = debug_order_payment(order_id)
            
            if payment_details:
                payment_method = payment_details.get('payment_method')
                
                if payment_method == 'cash':
                    # This is an artisan commission receipt, notify artisan
                    logger.info(f"Commission receipt for order {order_id} marked as invalid, notifying artisan")
                    await notify_artisan_about_invalid_commission(order_id)
                else:
                    # This is a customer payment receipt, notify customer
                    logger.info(f"Payment receipt for order {order_id} marked as invalid, notifying customer")
                    await notify_customer_about_invalid_receipt(order_id)
            else:
                logger.error(f"Could not determine payment method for order {order_id}")
                return False
        
        return True
    except Exception as e:
        logger.error(f"Error in process_receipt_verification_update: {e}", exc_info=True)
        return False

async def process_admin_payment_completed_update(order_id, is_completed):
    """Process admin payment completed status update from admin
    
    Args:
        order_id (int): ID of the order
        is_completed (bool): Whether payment is completed
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Update status in database
        status_updated = set_admin_payment_completed(order_id, is_completed)
        
        if not status_updated:
            logger.error(f"Failed to update admin payment status for order {order_id}")
            return False
        
        # If payment is completed, notify artisan
        if is_completed:
            logger.info(f"Admin payment for order {order_id} marked as completed, notifying artisan")
            await notify_artisan_about_payment_transfer(order_id)
        
        return True
    except Exception as e:
        logger.error(f"Error in process_admin_payment_completed_update: {e}")
        return False

# Function to periodically check for status changes
async def check_payment_status_changes():
    """Periodically check for payment status changes in the database
    
    This function can be called in a loop at regular intervals
    """
    try:
        from db import execute_query
        
        # Get orders with receipt_verified = 0 (meaning invalid)
        # Only for card payments
        invalid_receipts_query = """
            SELECT order_id
            FROM order_payments
            WHERE receipt_verified = 0
            AND payment_method != 'cash'
            AND receipt_file_id IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM notification_log 
                WHERE notification_type = 'invalid_receipt' 
                AND target_id = order_id
            )
        """
        
        # Get orders with admin_payment_completed = true that haven't been notified
        completed_payments_query = """
            SELECT order_id
            FROM order_payments
            WHERE admin_payment_completed = TRUE
            AND NOT EXISTS (
                SELECT 1 FROM notification_log 
                WHERE notification_type = 'payment_transfer' 
                AND target_id = order_id
            )
        """
        
        # Check pending receipts
        invalid_receipts = execute_query(invalid_receipts_query, fetchall=True)
        for receipt in invalid_receipts:
            order_id = receipt[0]
            logger.info(f"Found pending receipt for order {order_id}")
            await notify_customer_about_invalid_receipt(order_id)
            
            # Log notification
            log_query = """
                INSERT INTO notification_log (notification_type, target_id, created_at)
                VALUES ('invalid_receipt', %s, CURRENT_TIMESTAMP)
            """
            execute_query(log_query, (order_id,), commit=True)
        
        # Check completed payments
        completed_payments = execute_query(completed_payments_query, fetchall=True)
        for payment in completed_payments:
            order_id = payment[0]
            logger.info(f"Found completed payment for order {order_id}")
            await notify_artisan_about_payment_transfer(order_id)
            
            # Log notification
            log_query = """
                INSERT INTO notification_log (notification_type, target_id, created_at)
                VALUES ('payment_transfer', %s, CURRENT_TIMESTAMP)
            """
            execute_query(log_query, (order_id,), commit=True)
            
    except Exception as e:
        logger.error(f"Error in check_payment_status_changes: {e}")

async def verify_customer_fine_receipt(receipt_id, is_verified, admin_id):
    """Verify a customer fine payment receipt
    
    Args:
        receipt_id (int): ID of the receipt
        is_verified (bool): Whether the receipt is verified
        admin_id (int): ID of the admin who verified
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get receipt details
        cursor.execute(
            """
            SELECT customer_id, file_id
            FROM customer_fine_receipts
            WHERE id = %s
            """,
            (receipt_id,)
        )
        
        receipt = cursor.fetchone()
        
        if not receipt:
            logger.error(f"Receipt {receipt_id} not found")
            return False
        
        customer_id = receipt[0]
        
        # Update receipt status
        cursor.execute(
            """
            UPDATE customer_fine_receipts
            SET status = %s, verified_by = %s, verified_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            ('verified' if is_verified else 'rejected', admin_id, receipt_id)
        )
        
        # If verified, unblock customer
        if is_verified:
            # Unblock customer
            unblock_customer(customer_id)
            
            # Get customer telegram_id
            cursor.execute(
                "SELECT telegram_id FROM customers WHERE id = %s",
                (customer_id,)
            )
            
            customer_result = cursor.fetchone()
            
            if customer_result and customer_result[0]:
                # Notify customer
                keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
                keyboard.add(KeyboardButton("✅ Yeni sifariş ver"))
                keyboard.add(KeyboardButton("📜 Əvvəlki sifarişlərə bax"))
                keyboard.add(KeyboardButton("🌍 Yaxınlıqdakı ustaları göstər"))
                keyboard.add(KeyboardButton("👤 Profilim"), KeyboardButton("🔍 Xidmətlər"))
                keyboard.add(KeyboardButton("🏠 Əsas menyuya qayıt"))
                
                await bot.send_message(
                    chat_id=customer_result[0],
                    text=f"✅ *Blok götürüldü*\n\n"
                         f"Cərimə ödənişiniz təsdiqləndi və hesabınız blokdan çıxarıldı.\n"
                         f"İndi yenidən xidmətlərimizdən istifadə edə bilərsiniz.",
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
        else:
            # Get customer telegram_id
            cursor.execute(
                "SELECT telegram_id FROM customers WHERE id = %s",
                (customer_id,)
            )
            
            customer_result = cursor.fetchone()
            
            if customer_result and customer_result[0]:
                # Create retry button
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton(
                    "📸 Yeni qəbz göndər", 
                    callback_data="send_customer_fine_receipt"
                ))
                
                # Notify customer
                await bot.send_message(
                    chat_id=customer_result[0],
                    text=f"❌ *Qəbz təsdiqlənmədi*\n\n"
                         f"Təəssüf ki, göndərdiyiniz cərimə ödənişi qəbzi təsdiqlənmədi.\n"
                         f"Zəhmət olmasa, düzgün ödəniş edib yeni qəbz göndərin.",
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error verifying customer fine receipt: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()



async def request_customer_card_details(order_id, amount, reason):
    """Request card details from customer for refund
    
    Args:
        order_id (int): ID of the order
        amount (float): Amount to refund
        reason (str): Reason for refund
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get order details
        order = get_order_details(order_id)
        if not order:
            logger.error(f"Order {order_id} not found for refund request")
            return False
        
        # Get customer details - normal version for direct contact
        customer_id = order.get('customer_id')
        customer = get_customer_by_id(customer_id)
        if not customer:
            logger.error(f"Customer not found for order {order_id}")
            return False
        
        customer_telegram_id = customer.get('telegram_id')
        if not customer_telegram_id:
            logger.error(f"Customer telegram ID not found for order {order_id}")
            return False
        
        # Store refund info in database
        from db import create_refund_request
        refund_id = create_refund_request(order_id, amount, reason)
        
        if not refund_id:
            logger.error(f"Failed to create refund request for order {order_id}")
            return False
        
        # Set context for the customer
        from db import set_user_context
        set_user_context(customer_telegram_id, {
            "action": "provide_card_details",
            "refund_id": refund_id,
            "order_id": order_id,
            "amount": amount
        })
        
        # Create keyboard
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("❌ İmtina et", callback_data=f"decline_refund_{refund_id}"))
        
        # Send request to customer - using normal (unmasked) data for direct communication
        await bot.send_message(
            chat_id=customer_telegram_id,
            text=f"💰 *Ödəniş qaytarılması*\n\n"
                 f"Sifariş #{order_id} üçün {amount} AZN məbləğində ödəniş qaytarılması təsdiq edildi.\n"
                 f"Səbəb: {reason}\n\n"
                 f"Ödənişi almaq üçün zəhmət olmasa, kart nömrənizi daxil edin (məs: 4169 7425 0000 1234):",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        # For admin notifications - get masked customer details
        from db_encryption_wrapper import wrap_get_dict_function
        masked_customer = wrap_get_dict_function(get_customer_by_id, mask=True)(customer_id)
        masked_customer_name = masked_customer.get('name', 'Müştəri')
        
        # Notify admins about the refund request creation with masked data
        for admin_id in BOT_ADMINS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=f"💰 *Yeni ödəniş qaytarma tələbi*\n\n"
                         f"Sifariş: #{order_id}\n"
                         f"Müştəri: {masked_customer_name} (ID: {customer_id})\n"
                         f"Məbləğ: {amount} AZN\n"
                         f"Səbəb: {reason}\n\n"
                         f"Müştəridən kart məlumatları gözlənilir.",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id} about refund request creation: {e}")
        
        logger.info(f"Refund request sent to customer for order {order_id}, amount: {amount} AZN")
        return True
        
    except Exception as e:
        logger.error(f"Error in request_customer_card_details: {e}", exc_info=True)
        return False

async def process_customer_card_details(customer_id, card_number, refund_id):
    """Process customer card details for refund
    
    Args:
        customer_id (int): ID of the customer
        card_number (str): Card number provided by customer
        refund_id (int): ID of the refund request
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # 1. İlk olaraq kart məlumatlarını təhlükəsiz şəkildə saxla
        from payment_service import secure_store_card_details
        
        # Get refund details and order_id
        from db import get_refund_request
        refund = get_refund_request(refund_id)
        if not refund:
            logger.error(f"Refund request {refund_id} not found")
            return False
            
        order_id = refund.get('order_id')
        
        # Kart məlumatlarını şifrələnmiş şəkildə saxla
        # İstifadəçinin kart nömrəsini şifrələyərək saxlayır və yalnız əlaqəli açarla deşifrə edilə bilər
        success = secure_store_card_details(order_id, card_number)
        
        if not success:
            logger.error(f"Failed to securely store card details for order {order_id}")
        
        # 2. Refund request-i yenilə, lakin kart nömrəsini birbaşa saxlama
        from db import update_refund_request
        success = update_refund_request(refund_id, {
            'status': 'pending_admin'
            # Kart nömrəsini refund cədvəlində saxlamırıq. Əvəzinə, payment_card_details cədvəlində şifrələnmiş formada saxlayırıq.
        })
        
        if not success:
            logger.error(f"Failed to update refund request {refund_id}")
            return False
        
        # Get order details
        from db import get_order_details
        order = get_order_details(order_id)
        
        if not order:
            logger.error(f"Order {order_id} not found for refund notification")
            return False
        
        # 3. Maskalanmış məlumatları almaq üçün xüsusi wrapper funksiya istifadə et
        from db_encryption_wrapper import wrap_get_dict_function
        from db import get_customer_by_id
        from crypto_service import mask_card_number
        
        # Müştəri məlumatlarını maskalanmış şəkildə al
        masked_customer = wrap_get_dict_function(get_customer_by_id, mask=False)(customer_id)
        
        # Ad, telefon məlumatları maskalanmış olacaq, məs: "J*** D***"
        customer_name = masked_customer.get('name', 'Unknown')
        
        # Kart numarasını maskele
        from crypto_service import mask_card_number
        card_number_display = mask_card_number(card_number)
        
        # 4. Adminlərə həssas məlumatları maskalanmış şəkildə göndər
        for admin_id in BOT_ADMINS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=f"💳 *Yeni kart məlumatları*\n\n"
                         f"Sifariş: #{order_id}\n"
                         f"Müştəri: {customer_name} (ID: {customer_id})\n"
                         f"Məbləğ: {refund.get('amount')} AZN\n"
                         f"Səbəb: {refund.get('reason')}\n"
                         f"Kart nömrəsi: `{card_number_display}`\n\n"
                         f"Ödənişi tamamladıqdan sonra aşağıdakı düyməni istifadə edin:",
                    reply_markup=InlineKeyboardMarkup().add(
                        InlineKeyboardButton("✅ Ödəniş edildi", callback_data=f"refund_completed_{refund_id}")
                    ),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id} about refund request: {e}")
        
        # 5. Müştəriyə məlumat göndər - normal, maskalanmamış şəkildə
        # Bu, müştərinin öz məlumatları olduğu üçün maskalanmağa ehtiyac yoxdur
        # Get normal customer data (not masked)
        customer = get_customer_by_id(customer_id)
        customer_telegram_id = customer.get('telegram_id')
        
        if customer_telegram_id:
            await bot.send_message(
                chat_id=customer_telegram_id,
                text=f"✅ *Kart məlumatlarınız qeydə alındı*\n\n"
                     f"Ödəniş {refund.get('amount')} AZN məbləğində kartınıza köçürüləcək.\n"
                     f"Ödəniş tamamlandıqdan sonra sizə bildiriş ediləcək.",
                parse_mode="Markdown"
            )
        
        return True
        
    except Exception as e:
        logger.error(f"Error in process_customer_card_details: {e}", exc_info=True)
        return False

async def complete_refund_process(refund_id, admin_id):
    """Mark refund as completed by admin
    
    Args:
        refund_id (int): ID of the refund request
        admin_id (int): ID of the admin who completed the refund
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Update refund status
        from db import update_refund_request
        success = update_refund_request(refund_id, {
            'status': 'completed',
            'completed_by': admin_id,
            'completed_at': 'CURRENT_TIMESTAMP'
        })
        
        if not success:
            logger.error(f"Failed to mark refund {refund_id} as completed")
            return False
        
        # Get refund details
        from db import get_refund_request
        refund = get_refund_request(refund_id)
        
        if not refund:
            logger.error(f"Refund request {refund_id} not found after update")
            return False
        
        # Get order details
        order_id = refund.get('order_id')
        order = get_order_details(order_id)
        
        if not order:
            logger.error(f"Order {order_id} not found for refund completion")
            return False
        
        # Get customer details - normal version for notification to customer
        customer_id = order.get('customer_id')
        customer = get_customer_by_id(customer_id)
        
        if not customer:
            logger.error(f"Customer {customer_id} not found for refund completion")
            return False
        
        # For admin notifications - get masked customer data
        from db_encryption_wrapper import wrap_get_dict_function
        masked_customer = wrap_get_dict_function(get_customer_by_id, mask=False)(customer_id)
        masked_customer_name = masked_customer.get('name', 'Müştəri')
        
        # Get card details in masked form for admin confirmation
        from payment_service import get_card_details
        masked_card = get_card_details(order_id, mask=False)
        card_display = "Kart məlumatı yoxdur"
        if masked_card:
            card_display = masked_card.get('card_number', 'Kart məlumatı yoxdur')
        
        # Notify the admin who completed the refund
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=f"✅ *Ödəniş qaytarma tamamlandı*\n\n"
                     f"Sifariş: #{order_id}\n"
                     f"Müştəri: {masked_customer_name} (ID: {customer_id})\n"
                     f"Məbləğ: {refund.get('amount')} AZN\n"
                     f"Kart: {card_display}\n\n"
                     f"Müştəriyə bildiriş göndərildi.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id} about completed refund: {e}")
        
        # Notify other admins about the completed refund with masked data
        for other_admin in BOT_ADMINS:
            if other_admin != admin_id:  # Skip the admin who completed the refund
                try:
                    await bot.send_message(
                        chat_id=other_admin,
                        text=f"✅ *Ödəniş qaytarma tamamlandı*\n\n"
                             f"Sifariş: #{order_id}\n"
                             f"Müştəri: {masked_customer_name} (ID: {customer_id})\n"
                             f"Məbləğ: {refund.get('amount')} AZN\n"
                             f"Admin: {admin_id} tərəfindən icra edildi",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify admin {other_admin} about completed refund: {e}")
        
        # Notify customer about the completed refund - using normal (unmasked) data
        customer_telegram_id = customer.get('telegram_id')
        if customer_telegram_id:
            await bot.send_message(
                chat_id=customer_telegram_id,
                text=f"💰 *Ödəniş qaytarıldı*\n\n"
                     f"Sifariş #{order_id} üçün {refund.get('amount')} AZN məbləğində ödəniş kartınıza köçürüldü.\n"
                     f"Bizim xidmətlərimizdən istifadə etdiyiniz üçün təşəkkür edirik!",
                parse_mode="Markdown"
            )
        
        return True
        
    except Exception as e:
        logger.error(f"Error in complete_refund_process: {e}", exc_info=True)
        return False