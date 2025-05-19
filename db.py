# db.py

import mysql.connector
from mysql.connector import Error
from mysql.connector.cursor import MySQLCursorDict
import math
from datetime import datetime, timedelta
import json
import logging
from config import DB_CONFIG, COMMISSION_RATES
from crypto_service import encrypt_data
import hashlib

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_connection():
    """Establish and return a connection to the MySQL database"""
    try:
        conn = mysql.connector.connect(
            host=DB_CONFIG["host"],
            database=DB_CONFIG["database"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            port=DB_CONFIG.get("port", 3306),
            auth_plugin='mysql_native_password',  # Bu satırı ekleyin
            use_pure=True  # Bu satırı ekleyin
        )
        return conn
    except Error as e:
        logger.error(f"Error connecting to MySQL database: {e}")
        raise e


def execute_query(query, params=None, fetchone=False, fetchall=False, commit=False, dict_cursor=False):
    """Execute a database query with error handling and connection management
    
    Args:
        query (str): SQL query to execute
        params (tuple or list): Parameters for the query
        fetchone (bool): Whether to fetch one result
        fetchall (bool): Whether to fetch all results
        commit (bool): Whether to commit the transaction
        dict_cursor (bool): Whether to use a dictionary cursor
        
    Returns:
        Mixed: Query results or None
    """
    conn = None
    cursor = None
    result = None
    
    try:
        conn = get_connection()
        if dict_cursor:
            cursor = conn.cursor(dictionary=True)
        else:
            cursor = conn.cursor()
            
        cursor.execute(query, params or ())
        
        if fetchone:
            result = cursor.fetchone()
        elif fetchall:
            result = cursor.fetchall()
            
        if commit:
            conn.commit()
            
        return result
    except Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise e
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


# -------------------------
# CUSTOMER RELATED FUNCTIONS
# -------------------------

def get_customer_by_telegram_id(telegram_id):
    """Get customer information by Telegram ID
    
    Args:
        telegram_id (int): Telegram user ID
        
    Returns:
        dict: Customer information or None if not found
    """
    telegram_id_hash = hash_telegram_id(telegram_id)
    query = """
        SELECT * FROM customers 
        WHERE telegram_id_hash = %s
    """
    result = execute_query(query, (telegram_id_hash,), fetchone=True, dict_cursor=True)
    return result


def get_customer_by_id(customer_id):
    """Get customer information by ID
    
    Args:
        customer_id (int): Customer ID
        
    Returns:
        dict: Customer information or None if not found
    """
    query = """
        SELECT * FROM customers 
        WHERE id = %s
    """
    
    result = execute_query(query, (customer_id,), fetchone=True, dict_cursor=True)
    
    return result


def create_customer(telegram_id, name, phone=None, city=None):
    """Create a new customer and return their ID
    
    Args:
        telegram_id (int): Telegram user ID
        name (str): Customer name
        phone (str, optional): Customer phone number
        city (str, optional): Customer city
        
    Returns:
        int: ID of the created customer
    """
    telegram_id_hash = hash_telegram_id(telegram_id)
    encrypted_telegram_id = encrypt_data(telegram_id)
    
    # Limit name length to 45 characters before encryption to prevent database errors
    if name and len(name) > 45:
        name = name[:45]
    
    name = encrypt_data(name)
    
    # Limit phone length if provided
    if phone and len(phone) > 20:
        phone = phone[:20]
        
    phone = encrypt_data(phone) if phone else None
    query = """
        INSERT INTO customers (telegram_id, telegram_id_hash, name, phone, city, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
    """
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (encrypted_telegram_id, telegram_id_hash, name, phone, city))
        conn.commit()
        return cursor.lastrowid
    except Error as e:
        logger.error(f"Error creating customer: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def get_or_create_customer(telegram_id, name, phone=None, city=None):
    """Get customer ID by Telegram ID or create if not exists
    
    Args:
        telegram_id (int): Telegram user ID
        name (str): Customer name
        phone (str, optional): Customer phone number
        city (str, optional): Customer city
        
    Returns:
        int: Customer ID
    """
    customer = get_customer_by_telegram_id(telegram_id)
    
    if not customer:
        customer_id = create_customer(telegram_id, name, phone, city)
        return customer_id
    
    return customer['id']


def update_customer_profile(telegram_id, data):
    """Update customer profile information
    
    Args:
        telegram_id (int): Telegram user ID
        data (dict): Data to update (keys: name, phone, city)
        
    Returns:
        bool: True if successful, False otherwise
    """
    valid_fields = ['name', 'phone', 'city']
    update_parts = []
    params = []
    
    for field in valid_fields:
        if field in data and data[field] is not None:
            update_parts.append(f"{field} = %s")
            params.append(data[field])
    
    if not update_parts:
        return False  # Nothing to update
        
    params.append(telegram_id)  # For the WHERE clause
    
    query = f"""
        UPDATE customers
        SET {', '.join(update_parts)}
        WHERE telegram_id = %s
    """
    
    try:
        execute_query(query, params, commit=True)
        return True
    except Exception as e:
        logger.error(f"Error updating customer profile: {e}")
        return False


def get_customer_orders(customer_id):
    """Get orders for a specific customer
    
    Args:
        customer_id (int): ID of the customer
        
    Returns:
        list: List of customer orders
    """
    query = """
        SELECT o.*, a.name as artisan_name, a.phone as artisan_phone,
               op.amount, op.payment_status, op.payment_method,
               o.status, o.subservice
        FROM orders o
        JOIN artisans a ON o.artisan_id = a.id
        LEFT JOIN order_payments op ON o.id = op.order_id
        WHERE o.customer_id = %s
        ORDER BY o.date_time DESC
    """
    
    return execute_query(query, (customer_id,), fetchall=True, dict_cursor=True)


# -------------------------
# ARTISAN RELATED FUNCTIONS
# -------------------------

def get_artisan_by_telegram_id(telegram_id):
    telegram_id_hash = hash_telegram_id(telegram_id)
    query = "SELECT id FROM artisans WHERE telegram_id_hash = %s"
    result = execute_query(query, (telegram_id_hash,), fetchone=True)
    return result[0] if result else None


def get_artisan_by_id(artisan_id):
    """Get artisan information by ID
    
    Args:
        artisan_id (int): ID of the artisan
        
    Returns:
        dict: Artisan information or None if not found
    """
    query = """
        SELECT id, name, phone, service, location, city, 
               latitude, longitude, rating, active, created_at, telegram_id 
        FROM artisans 
        WHERE id = %s
    """
    
    result = execute_query(query, (artisan_id,), fetchone=True, dict_cursor=True)
    
    return result


def check_artisan_exists(telegram_id=None, phone=None, exclude_id=None):
    """Check if an artisan with the given parameters exists
    
    Args:
        telegram_id (int, optional): Telegram user ID
        phone (str, optional): Phone number
        exclude_id (int, optional): ID to exclude from the check
        
    Returns:
        bool: True if exists, False otherwise
    """
    if telegram_id is None and phone is None:
        return False
        
    query_parts = []
    params = []
    
    if telegram_id is not None:
        query_parts.append("telegram_id = %s")
        params.append(telegram_id)
        
    if phone is not None:
        query_parts.append("phone = %s")
        params.append(phone)
        
    query = f"""
        SELECT id FROM artisans 
        WHERE ({' OR '.join(query_parts)})
    """
    
    if exclude_id is not None:
        query += " AND id != %s"
        params.append(exclude_id)
        
    result = execute_query(query, params, fetchone=True)
    return result is not None

def hash_telegram_id(telegram_id):
    return hashlib.sha256(str(telegram_id).encode()).hexdigest()

def create_artisan(telegram_id, name, phone, service, location=None, city=None, latitude=None, longitude=None):
    """Create a new artisan and return their ID
    
    Args:
        telegram_id (int): Telegram user ID
        name (str): Artisan name
        phone (str): Artisan phone number
        service (str): Type of service provided
        location (str, optional): Artisan location description
        city (str, optional): Artisan city
        latitude (float, optional): Artisan latitude
        longitude (float, optional): Artisan longitude
        
    Returns:
        int: ID of the created artisan
    """
    telegram_id_hash = hash_telegram_id(telegram_id)
    encrypted_telegram_id = encrypt_data(telegram_id)
    
    # Limit name length to 45 characters before encryption to prevent database errors
    if name and len(name) > 200:
        name = name[:200]
        
    name = encrypt_data(name)
    
    # Limit phone length if needed
    if phone and len(phone) > 200:
        phone = phone[:200]
        
    phone = encrypt_data(phone)

    query = """
        INSERT INTO artisans (telegram_id, telegram_id_hash, name, phone, service, location, city, 
                              latitude, longitude, active, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW())
    """
    
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (encrypted_telegram_id, telegram_id_hash, name, phone, service, location, city, latitude, longitude))
        conn.commit()
        return cursor.lastrowid
    except Error as e:
        logger.error(f"Error creating artisan: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def get_or_create_artisan(telegram_id, name, phone, service, location=None, city=None, latitude=None, longitude=None):
    """Get artisan ID by Telegram ID or create if not exists
    
    Args:
        telegram_id (int): Telegram user ID
        name (str): Artisan name
        phone (str): Artisan phone number
        service (str): Type of service provided
        location (str, optional): Artisan location description
        city (str, optional): Artisan city
        latitude (float, optional): Artisan latitude
        longitude (float, optional): Artisan longitude
        
    Returns:
        int: Artisan ID
    """
    artisan_id = get_artisan_by_telegram_id(telegram_id)
    
    if artisan_id is None:
        artisan_id = create_artisan(telegram_id, name, phone, service, location, city, latitude, longitude)
    else:
        # Update artisan information
        update_query = """
            UPDATE artisans 
            SET name = %s, phone = %s, service = %s, 
                location = COALESCE(%s, location),
                city = COALESCE(%s, city),
                latitude = COALESCE(%s, latitude),
                longitude = COALESCE(%s, longitude)
            WHERE id = %s
        """
        execute_query(
            update_query, 
            (name, phone, service, location, city, latitude, longitude, artisan_id),
            commit=True
        )
        
    return artisan_id

def update_artisan_for_order(order_id, artisan_id):
    """Siparişe usta ata"""
    try:
        if not order_id:
            logger.error("Cannot update artisan: order_id is None")
            return False
        
        logger.info(f"Updating order {order_id} with artisan ID {artisan_id}")

        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE orders
            SET artisan_id = %s
            WHERE id = %s
        """, (artisan_id, order_id))
        
        affected_rows = cursor.rowcount
        conn.commit()
        
        if affected_rows == 0:
            logger.warning(f"No order updated with ID {order_id}")
            return False
        
        logger.info(f"Successfully updated order {order_id} with artisan {artisan_id}")

        return True
    except Exception as e:
        logger.error(f"Error in update_artisan_for_order: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def update_artisan_profile(artisan_id, data):
    """Update artisan profile information
    
    Args:
        artisan_id (int): ID of the artisan
        data (dict): Data to update (keys: name, phone, city, etc.)
        
    Returns:
        bool: True if successful, False otherwise
    """
    valid_fields = ['name', 'phone', 'city', 'service', 'location', 'active']
    update_parts = []
    params = []
    
    for field in valid_fields:
        if field in data and data[field] is not None:
            update_parts.append(f"{field} = %s")
            params.append(data[field])
    
    if not update_parts:
        return False  # Nothing to update
        
    params.append(artisan_id)  # For the WHERE clause
    
    query = f"""
        UPDATE artisans
        SET {', '.join(update_parts)}
        WHERE id = %s
    """
    
    try:
        execute_query(query, params, commit=True)
        return True
    except Exception as e:
        logger.error(f"Error updating artisan profile: {e}")
        return False

def skip_artisan_for_next_order(artisan_id):
    """Ustanın növbəti bir sifarişdən kənarlaşdırılması üçün işarələyir
    
    Args:
        artisan_id (int): Ustanın ID-si
        
    Returns:
        bool: True əgər əməliyyat uğurludursa, əks halda False
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Cədvəlin mövcud olub-olmadığını yoxla
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = %s AND table_name = 'artisan_skip_next_order'
        """, (DB_CONFIG['database'],))
        
        table_exists = cursor.fetchone()[0] > 0
        
        # Cədvəl yoxdursa yarat
        if not table_exists:
            cursor.execute("""
                CREATE TABLE artisan_skip_next_order (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    artisan_id INT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    skipped BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (artisan_id) REFERENCES artisans(id) ON DELETE CASCADE
                )
            """)
        
        # Mövcud qeydləri yoxla
        cursor.execute(
            "SELECT id FROM artisan_skip_next_order WHERE artisan_id = %s AND skipped = FALSE",
            (artisan_id,)
        )
        existing = cursor.fetchone()
        
        if existing:
            # Artıq bir qeyd varsa, güncəllənmə etmə
            logger.info(f"Artisan {artisan_id} already marked to skip next order")
        else:
            # Yeni qeyd yarat
            cursor.execute(
                """
                INSERT INTO artisan_skip_next_order (artisan_id, skipped)
                VALUES (%s, FALSE)
                """,
                (artisan_id,)
            )
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error in skip_artisan_for_next_order: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()

def should_skip_artisan_for_order(artisan_id):
    """Ustanın cari sifariş üçün kənarlaşdırılması lazım olub-olmadığını yoxlayır
    
    Args:
        artisan_id (int): Ustanın ID-si
        
    Returns:
        bool: True əgər kənarlaşdırılmalıdırsa, əks halda False
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Əvvəlcə cədvəli yoxla
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = %s AND table_name = 'artisan_skip_next_order'
        """, (DB_CONFIG['database'],))
        
        table_exists = cursor.fetchone()[0] > 0
        
        if not table_exists:
            return False
        
        # Kənarlaşdırılmalı olan bir sifariş varmı?
        cursor.execute(
            "SELECT id FROM artisan_skip_next_order WHERE artisan_id = %s AND skipped = FALSE",
            (artisan_id,)
        )
        record = cursor.fetchone()
        
        if record:
            # Qeydi yenilə - artıq kənarlaşdırılmış kimi işarələ
            cursor.execute(
                "UPDATE artisan_skip_next_order SET skipped = TRUE WHERE id = %s",
                (record[0],)
            )
            conn.commit()
            return True
        
        return False
    except Exception as e:
        logger.error(f"Error in should_skip_artisan_for_order: {e}")
        return False  # Xəta halında təhlükəsiz tərəf - kənarlaşdırma
    finally:
        if conn and conn.is_connected():
            conn.close()

def update_artisan_location(artisan_id, latitude, longitude, location_name=None, city=None):
    """Update an artisan's location
    
    Args:
        artisan_id (int): ID of the artisan
        latitude (float): Latitude
        longitude (float): Longitude
        location_name (str, optional): Location description
        city (str, optional): City name
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Build query based on provided parameters
    update_fields = ["latitude = %s", "longitude = %s"]
    params = [latitude, longitude]
    
    if location_name:
        update_fields.append("location = %s")
        params.append(location_name)
    
    if city:
        update_fields.append("city = %s")
        params.append(city)
    
    params.append(artisan_id)  # For WHERE clause
    
    query = f"""
        UPDATE artisans 
        SET {', '.join(update_fields)}
        WHERE id = %s
    """
    
    try:
        execute_query(query, params, commit=True)
        return True
    except Exception as e:
        logger.error(f"Error updating artisan location: {e}")
        return False


def toggle_artisan_active_status(artisan_id):
    """Toggle an artisan's active status
    
    Args:
        artisan_id (int): ID of the artisan
        
    Returns:
        tuple: (bool success, bool new_status)
    """
    # First get current status
    query = "SELECT active FROM artisans WHERE id = %s"
    result = execute_query(query, (artisan_id,), fetchone=True)
    
    if not result:
        return False, False
        
    current_status = bool(result[0])
    new_status = not current_status
    
    # Update status
    update_query = "UPDATE artisans SET active = %s WHERE id = %s"
    
    try:
        execute_query(update_query, (new_status, artisan_id), commit=True)
        return True, new_status
    except Exception as e:
        logger.error(f"Error toggling artisan status: {e}")
        return False, current_status


def update_artisan_service_and_reset_prices(artisan_id, service):
    """Update artisan's service and reset all price ranges
    
    Args:
        artisan_id (int): ID of the artisan
        service (str): New service type
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Use a transaction to ensure both operations complete or fail together
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Update service
        cursor.execute(
            "UPDATE artisans SET service = %s WHERE id = %s",
            (service, artisan_id)
        )
        
        # Delete existing price ranges
        cursor.execute(
            "DELETE FROM artisan_price_ranges WHERE artisan_id = %s",
            (artisan_id,)
        )
        
        conn.commit()
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error updating artisan service: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()


def get_artisan_blocked_status(artisan_id):
    """Check if an artisan is blocked and get the reason
    
    Args:
        artisan_id (int): ID of the artisan
        
    Returns:
        tuple: (bool is_blocked, str reason, float required_payment)
    """
    query = """
        SELECT is_blocked, block_reason, required_payment
        FROM artisan_blocks
        WHERE artisan_id = %s AND is_blocked = TRUE
        ORDER BY created_at DESC
        LIMIT 1
    """
    
    result = execute_query(query, (artisan_id,), fetchone=True)
    
    if result:
        return True, result[1], result[2]
    else:
        return False, None, 0


def block_artisan(artisan_id, reason, required_payment):
    """Block an artisan
    
    Args:
        artisan_id (int): ID of the artisan
        reason (str): Reason for blocking
        required_payment (float): Amount needed to unblock
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Set artisan as inactive
    update_query = "UPDATE artisans SET active = FALSE WHERE id = %s"
    
    # Insert block record
    block_query = """
        INSERT INTO artisan_blocks 
        (artisan_id, is_blocked, block_reason, required_payment, created_at)
        VALUES (%s, TRUE, %s, %s, NOW())
    """
    
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(update_query, (artisan_id,))
        cursor.execute(block_query, (artisan_id, reason, required_payment))
        
        conn.commit()
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error blocking artisan: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()


def unblock_artisan(artisan_id):
    """Unblock an artisan
    
    Args:
        artisan_id (int): ID of the artisan
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Set artisan as active
    update_query = "UPDATE artisans SET active = TRUE WHERE id = %s"
    
    # Update block record
    block_query = """
        UPDATE artisan_blocks
        SET is_blocked = FALSE, unblocked_at = NOW()
        WHERE artisan_id = %s AND is_blocked = TRUE
    """
    
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(update_query, (artisan_id,))
        cursor.execute(block_query, (artisan_id,))
        
        conn.commit()
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error unblocking artisan: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()


def save_fine_receipt(artisan_id, file_id):
    """Save fine payment receipt
    
    Args:
        artisan_id (int): ID of the artisan
        file_id (str): Telegram file ID of the receipt
        
    Returns:
        bool: True if successful, False otherwise
    """
    query = """
        INSERT INTO fine_receipts 
        (artisan_id, file_id, status, created_at)
        VALUES (%s, %s, 'pending', NOW())
    """
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (artisan_id, file_id))
        conn.commit()
        return cursor.lastrowid is not None
    except Exception as e:
        logger.error(f"Error saving fine receipt: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()


# -------------------------
# SERVICES AND SUBSERVICES
# -------------------------

def get_services():
    """Get all available service types
    
    Returns:
        list: List of service types
    """
    query = "SELECT name FROM services WHERE active = TRUE ORDER BY name"
    result = execute_query(query, fetchall=True)
    
    # Extract service names from result tuples
    return [row[0] for row in result] if result else []


def get_subservices(service_name):
    """Get subservices for a specific service
    
    Args:
        service_name (str): Service name
        
    Returns:
        list: List of subservice names
    """
    query = """
        SELECT s.name 
        FROM subservices s
        JOIN services srv ON s.service_id = srv.id
        WHERE srv.name = %s AND s.active = TRUE
        ORDER BY s.name
    """
    
    result = execute_query(query, (service_name,), fetchall=True)
    
    # Extract subservice names from result tuples
    return [row[0] for row in result] if result else []


def get_artisan_price_ranges(artisan_id, subservice=None):
    """Get price ranges for an artisan's services
    
    Args:
        artisan_id (int): ID of the artisan
        subservice (str, optional): Filter by specific subservice
        
    Returns:
        list or dict: List of price ranges or specific subservice's price range
    """
    if subservice:
        # Get specific subservice price range
        query = """
            SELECT apr.min_price, apr.max_price, s.name as subservice
            FROM artisan_price_ranges apr
            JOIN subservices s ON apr.subservice_id = s.id
            WHERE apr.artisan_id = %s AND s.name = %s
            AND apr.is_active = TRUE
        """
        
        result = execute_query(query, (artisan_id, subservice), fetchone=True, dict_cursor=True)
        return result
    else:
        # Get all price ranges
        query = """
            SELECT apr.min_price, apr.max_price, s.name as subservice
            FROM artisan_price_ranges apr
            JOIN subservices s ON apr.subservice_id = s.id
            WHERE apr.artisan_id = %s AND apr.is_active = TRUE
            ORDER BY s.name
        """
        
        result = execute_query(query, (artisan_id,), fetchall=True, dict_cursor=True)
        return result if result else []


def update_artisan_price_range(artisan_id, subservice, min_price, max_price):
    """Update or create price range for a specific subservice
    
    Args:
        artisan_id (int): ID of the artisan
        subservice (str): Subservice name
        min_price (float): Minimum price
        max_price (float): Maximum price
        
    Returns:
        bool: True if successful, False otherwise
    """
    # First, get subservice_id
    subservice_query = "SELECT id FROM subservices WHERE name = %s"
    subservice_result = execute_query(subservice_query, (subservice,), fetchone=True)
    
    if not subservice_result:
        return False
        
    subservice_id = subservice_result[0]
    
    # Check if price range already exists
    check_query = """
        SELECT id FROM artisan_price_ranges 
        WHERE artisan_id = %s AND subservice_id = %s
    """
    
    existing = execute_query(check_query, (artisan_id, subservice_id), fetchone=True)
    
    try:
        if existing:
            # Update existing price range
            update_query = """
                UPDATE artisan_price_ranges 
                SET min_price = %s, max_price = %s, is_active = TRUE
                WHERE artisan_id = %s AND subservice_id = %s
            """
            execute_query(update_query, (min_price, max_price, artisan_id, subservice_id), commit=True)
        else:
            # Create new price range
            insert_query = """
                INSERT INTO artisan_price_ranges 
                (artisan_id, subservice_id, min_price, max_price, is_active, created_at)
                VALUES (%s, %s, %s, %s, TRUE, NOW())
            """
            execute_query(insert_query, (artisan_id, subservice_id, min_price, max_price), commit=True)
            
        return True
    except Exception as e:
        logger.error(f"Error updating price range: {e}")
        return False


def get_artisan_by_service(service):
    """Get artisans providing a specific service
    
    Args:
        service (str): Type of service
        
    Returns:
        list: List of artisans matching the service
    """
    query = """
        SELECT id, name, phone, service, location, latitude, longitude
        FROM artisans 
        WHERE service = %s AND active = TRUE
    """
    
    return execute_query(query, (service,), fetchall=True)


def get_nearby_artisans(latitude, longitude, radius=10, service=None, subservice=None):
    """Get artisans near the specified location within radius km
    
    Args:
        latitude (float): Customer's latitude
        longitude (float): Customer's longitude
        radius (float, optional): Search radius in kilometers (default: 10)
        service (str, optional): Filter by service type
        subservice (str, optional): Filter by subservice type
        
    Returns:
        list: List of nearby artisans with distance
    """
    # Base query to get active artisans with location info
    query = """
        SELECT a.id, a.name, a.phone, a.service, a.location, 
               a.latitude, a.longitude, a.rating
        FROM artisans a
        WHERE a.active = TRUE AND a.latitude IS NOT NULL AND a.longitude IS NOT NULL
    """
    
    params = []
    
    # Add service filter if provided
    if service:
        query += " AND a.service = %s"
        params.append(service)
    
    # Add subservice filter if provided
    if subservice:
        query += """
            AND EXISTS (
                SELECT 1 FROM artisan_price_ranges apr
                JOIN subservices s ON apr.subservice_id = s.id
                WHERE apr.artisan_id = a.id AND s.name = %s AND apr.is_active = TRUE
            )
        """
        params.append(subservice)
    
    result = execute_query(query, params, fetchall=True)
    
    if not result:
        return []
    
    # Filter artisans by distance and add distance information
    nearby_artisans = []
    for artisan in result:
        artisan_lat = artisan[5]  # latitude index
        artisan_lon = artisan[6]  # longitude index
        
        if artisan_lat and artisan_lon:
            distance = calculate_distance(latitude, longitude, artisan_lat, artisan_lon)
            
            if distance <= radius:
                # Convert to list to add distance field
                artisan_with_distance = list(artisan)
                artisan_with_distance.append(distance)
                nearby_artisans.append(artisan_with_distance)
    
    # Sort by distance (ascending)
    nearby_artisans.sort(key=lambda x: x[-1])
    
    return nearby_artisans


# -------------------------
# ORDER RELATED FUNCTIONS
# -------------------------

def insert_order(customer_id, service, date_time, note, latitude, longitude, location_name, subservice=None, status="pending", artisan_id=None):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Artisan ID NULL olarsa ona görə SQL sorğusunu dəyişdirin
        if artisan_id is None:
            query = """
                INSERT INTO orders (customer_id, service, subservice, date_time, note, 
                              latitude, longitude, location_name, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            cursor.execute(query, (
                customer_id, service, subservice, date_time, note, 
                latitude, longitude, location_name, status
            ))
        else:
            query = """
                INSERT INTO orders (customer_id, artisan_id, service, subservice, date_time, note, 
                              latitude, longitude, location_name, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            cursor.execute(query, (
                customer_id, artisan_id, service, subservice, date_time, note, 
                latitude, longitude, location_name, status
            ))
        
        order_id = cursor.lastrowid
        conn.commit()
        return order_id
        
    except Exception as e:
        logger.error(f"Error inserting order: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            conn.close()


def get_order_details(order_id):
    """Get detailed information about an order"""
    try:
        if not order_id:
            logger.warning("get_order_details called with None order_id")
            return None
            
        # Log the request for troubleshooting
        logger.info(f"Getting details for order ID: {order_id}")
        
        query = """
            SELECT o.*, c.name as customer_name, c.phone as customer_phone, 
                   a.name as artisan_name, a.phone as artisan_phone
            FROM orders o
            LEFT JOIN customers c ON o.customer_id = c.id
            LEFT JOIN artisans a ON o.artisan_id = a.id
            WHERE o.id = %s
        """
        
        result = execute_query(query, (order_id,), fetchone=True, dict_cursor=True)
        
        if not result:
            logger.warning(f"No order found with ID {order_id}")
            return None
            
        logger.info(f"Found order: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in get_order_details: {e}")
        return None


def update_order_status(order_id, status):
    """Update the status of an order
    
    Args:
        order_id (int): ID of the order
        status (str): New status ('pending', 'accepted', 'completed', 'cancelled')
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Log the status change for debugging
    logger.info(f"Updating order {order_id} status to: {status}")
    
    query = "UPDATE orders SET status = %s WHERE id = %s"
    
    try:
        execute_query(query, (status, order_id), commit=True)
        
        # If status is 'completed', also update the completed_at timestamp
        if status == 'completed':
            timestamp_query = "UPDATE orders SET completed_at = NOW() WHERE id = %s"
            execute_query(timestamp_query, (order_id,), commit=True)
        
        # Double check that the status was updated
        check_query = "SELECT status FROM orders WHERE id = %s"
        result = execute_query(check_query, (order_id,), fetchone=True)
        if result and result[0] != status:
            logger.warning(f"Status update failed - DB returned {result[0]} instead of {status}")
            return False
            
        return True
    except Exception as e:
        logger.error(f"Error updating order status: {e}")
        return False


def get_artisan_active_orders(artisan_id):
    """Get active orders for a specific artisan
    
    Args:
        artisan_id (int): ID of the artisan
        
    Returns:
        list: List of active orders
    """
    query = """
        SELECT o.*, c.name as customer_name, c.phone as customer_phone
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        WHERE o.artisan_id = %s AND o.status = 'pending'
        ORDER BY o.date_time ASC
    """
    
    return execute_query(query, (artisan_id,), fetchall=True, dict_cursor=True)


def set_order_price(order_id, price, admin_fee=None, artisan_amount=None):
    """Set the price for an order
    
    Args:
        order_id (int): ID of the order
        price (float): Total price
        admin_fee (float, optional): Admin fee portion
        artisan_amount (float, optional): Artisan portion
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Log price setting attempt for debugging
    logger.info(f"Setting price for order {order_id}: {price} AZN")
    
    # If admin_fee and artisan_amount are not provided, calculate them
    if admin_fee is None or artisan_amount is None:
        # Get commission rate based on price
        commission_rate = 0.12  # Default rate (12%)
        
        for tier, info in COMMISSION_RATES.items():
            if price <= info["threshold"]:
                commission_rate = info["rate"] / 100  # Convert percentage to decimal
                break
        
        admin_fee = round(price * commission_rate, 2)
        artisan_amount = price - admin_fee
    
    # Update the price in the orders table directly as well
    update_order_query = """
        UPDATE orders 
        SET price = %s, 
            updated_at = NOW()
        WHERE id = %s
    """
    
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Start with updating the orders table
        cursor.execute(update_order_query, (price, order_id))
        
        # Check if payment record exists
        cursor.execute("SELECT id FROM order_payments WHERE order_id = %s", (order_id,))
        payment_exists = cursor.fetchone()
        
        if payment_exists:
            # Update existing payment record
            cursor.execute(
                """
                UPDATE order_payments 
                SET amount = %s, admin_fee = %s, artisan_amount = %s
                WHERE order_id = %s
                """,
                (price, admin_fee, artisan_amount, order_id)
            )
        else:
            # Create new payment record
            cursor.execute(
                """
                INSERT INTO order_payments 
                (order_id, amount, admin_fee, artisan_amount, payment_status, created_at)
                VALUES (%s, %s, %s, %s, 'pending', NOW())
                """,
                (order_id, price, admin_fee, artisan_amount)
            )
        
        # Verify price was set
        cursor.execute("SELECT price FROM orders WHERE id = %s", (order_id,))
        verify_result = cursor.fetchone()
        
        conn.commit()
        
        if verify_result and verify_result[0] is not None:
            logger.info(f"Price for order {order_id} set successfully to {price} AZN")
            return True
        else:
            logger.error(f"Failed to verify price for order {order_id}")
            return False
            
    except Exception as e:
        logger.error(f"Error setting order price: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def update_payment_method(order_id, payment_method):
    """Update payment method for an order
    
    Args:
        order_id (int): ID of the order
        payment_method (str): Payment method (card, cash, etc.)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if payment record exists
        cursor.execute("SELECT id FROM order_payments WHERE order_id = %s", (order_id,))
        payment_record = cursor.fetchone()
        
        if payment_record:
            # Update existing record with payment method and set receipt_verified to NULL for all payment methods
            cursor.execute(
                """
                UPDATE order_payments 
                SET payment_method = %s,
                    payment_status = 'pending',
                    receipt_verified = NULL,
                    updated_at = NOW()
                WHERE order_id = %s
                """,
                (payment_method, order_id)
            )
        else:
            # Get order price
            cursor.execute("SELECT price FROM orders WHERE id = %s", (order_id,))
            price_result = cursor.fetchone()
            
            if not price_result or price_result[0] is None:
                logger.error(f"Order {order_id} has no price set when updating payment method")
                conn.rollback()
                return False
            
            price = float(price_result[0])
            
            # Calculate commission
            commission_rate = 0.16  # Default
            for tier, info in COMMISSION_RATES.items():
                threshold = info.get("threshold")
                if threshold is not None and price <= threshold:
                    commission_rate = info["rate"] / 100
                    break
            
            admin_fee = round(price * commission_rate, 2)
            artisan_amount = round(price - admin_fee, 2)
            
            # Create new payment record
            cursor.execute(
                """
                INSERT INTO order_payments 
                (order_id, amount, admin_fee, artisan_amount, payment_method, 
                 payment_status, receipt_verified, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, 'pending', NULL, NOW(), NOW())
                """,
                (order_id, price, admin_fee, artisan_amount, payment_method)
            )
        
        # Update order payment method field as well
        cursor.execute(
            "UPDATE orders SET payment_method = %s WHERE id = %s",
            (payment_method, order_id)
        )
        
        conn.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error updating payment method: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()


def save_payment_receipt(order_id, file_id):
    """Save payment receipt for an order"""
    try:
        logger.info(f"Attempting to save payment receipt for order {order_id} with file_id: {file_id}")

        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # First check if the order exists
            cursor.execute("SELECT id FROM orders WHERE id = %s", (order_id,))
            order_exists = cursor.fetchone()
            
            if not order_exists:
                logger.error(f"Order {order_id} not found when saving receipt")
                return False
            
            # Check if payment record exists
            cursor.execute("SELECT id, payment_method FROM order_payments WHERE order_id = %s", (order_id,))
            payment_record = cursor.fetchone()
            
            if payment_record:
                logger.info(f"Found payment record: ID={payment_record[0]}, Method={payment_record[1]}")
                # Update existing payment record
                cursor.execute(
                    """
                    UPDATE order_payments 
                    SET receipt_file_id = %s,
                        receipt_uploaded_at = NOW(),
                        payment_status = 'pending',
                        payment_date = NOW(),
                        receipt_verified = NULL,
                        admin_payment_completed = FALSE
                    WHERE order_id = %s
                    """,
                    (file_id, order_id)
                )
                
                # Also update the order payment status
                cursor.execute(
                    "UPDATE orders SET payment_status = 'paid' WHERE id = %s",
                    (order_id,)
                )
            else:
                # Create new payment record based on order price
                logger.info(f"No payment record found, creating new one for order {order_id}")
                
                # Get the order price first
                cursor.execute("SELECT price FROM orders WHERE id = %s", (order_id,))
                price_result = cursor.fetchone()
                
                if not price_result or price_result[0] is None:
                    logger.error(f"Order {order_id} has no price set")
                    conn.rollback()
                    return False
                
                price = float(price_result[0])
                
                # Calculate commission
                commission_rate = 0.16  # Default at 16%
                for tier, info in COMMISSION_RATES.items():
                    threshold = info.get("threshold")
                    if threshold is not None and price <= threshold:
                        commission_rate = info["rate"] / 100
                        break
                
                admin_fee = round(price * commission_rate, 2)
                artisan_amount = round(price - admin_fee, 2)
                
                # Insert the new payment record
                cursor.execute(
                    """
                    INSERT INTO order_payments 
                    (order_id, amount, admin_fee, artisan_amount, receipt_file_id, receipt_uploaded_at, 
                     payment_status, payment_method, payment_date, created_at, updated_at, receipt_verified)
                    VALUES (%s, %s, %s, %s, %s, NOW(), 'pending', 'cash', NOW(), 
                            NOW(), NOW(), NULL)
                    """,
                    (order_id, price, admin_fee, artisan_amount, file_id)
                )
            
            # Verify the receipt was actually saved
            cursor.execute("SELECT receipt_file_id FROM order_payments WHERE order_id = %s", (order_id,))
            verify_result = cursor.fetchone()
            if not verify_result or not verify_result[0]:
                logger.error(f"Failed to verify receipt was saved for order {order_id}")
                # Force direct update
                cursor.execute(
                    "UPDATE order_payments SET receipt_file_id = %s WHERE order_id = %s",
                    (file_id, order_id)
                )
            
            conn.commit()
            logger.info(f"Successfully saved receipt for order {order_id}")
            return True
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error in save_payment_receipt: {e}", exc_info=True)
            return False
        finally:
            if conn and conn.is_connected():
                conn.close()
            
    except Exception as e:
        logger.error(f"Error saving payment receipt: {e}", exc_info=True)
        return False


def confirm_payment(order_id, is_verified=True):
    """Confirm payment for an order
    
    Args:
        order_id (int): ID of the order
        is_verified (bool): Whether payment was verified
        
    Returns:
        bool: True if successful, False otherwise
    """
    status = "completed" if is_verified else "failed"
    
    query = """
        UPDATE order_payments 
        SET payment_status = %s,
            payment_date = NOW()
        WHERE order_id = %s
    """
    
    try:
        execute_query(query, (status, order_id), commit=True)
        return True
    except Exception as e:
        logger.error(f"Error confirming payment: {e}")
        return False


# -------------------------
# USER CONTEXT FUNCTIONS
# -------------------------
from crypto_service import encrypt_data, decrypt_data

def set_user_context(telegram_id, context_data):
    """Set context data for a user
    
    Args:
        telegram_id (int or str): Telegram user ID (can be encrypted)
        context_data (dict or str): Context data to store
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Always convert telegram_id to string to avoid database type issues
        telegram_id_str = str(telegram_id)
        
        # Ensure we're storing JSON in the database
        context_json = None
        
        if isinstance(context_data, dict):
            # Convert datetime objects to strings
            cleaned_data = {}
            for key, value in context_data.items():
                if isinstance(value, datetime):
                    cleaned_data[key] = value.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    cleaned_data[key] = value
            
            context_json = json.dumps(cleaned_data)
            
        elif isinstance(context_data, str):
            # If it's already a string, ensure it's valid JSON or wrap it
            try:
                json.loads(context_data)  # Test if it's valid JSON
                context_json = context_data
            except json.JSONDecodeError:
                context_json = json.dumps({"value": context_data})
                
        else:
            # For any other type, convert to string then wrap in JSON
            context_json = json.dumps({"value": str(context_data)})
        
        # Verify we have a valid JSON string before proceeding
        if not context_json:
            raise ValueError("Failed to convert context data to JSON")
        
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Delete any existing records for this telegram_id - always use string
            cursor.execute("DELETE FROM user_context WHERE telegram_id = %s", (telegram_id_str,))
            
            # Insert new context - always as string
            cursor.execute(
                """
                INSERT INTO user_context (telegram_id, context_data, created_at, updated_at)
                VALUES (%s, %s, NOW(), NOW())
                """,
                (telegram_id_str, context_json)
            )
            
            conn.commit()
            return True
        except Exception as db_error:
            if conn:
                conn.rollback()
            logger.error(f"Database error in set_user_context: {db_error}", exc_info=True)
            return False
        finally:
            if conn and conn.is_connected():
                conn.close()
                
    except Exception as e:
        logger.error(f"Error setting user context: {e}", exc_info=True)
        return False


def get_user_context(telegram_id):
    """Get context data for a user
    
    Args:
        telegram_id (int or str): Telegram user ID (can be encrypted)
        
    Returns:
        dict: Context data or empty dict if not found
    """
    conn = None
    try:
        # Always convert telegram_id to string
        telegram_id_str = str(telegram_id)
        
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Check if table exists
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM information_schema.tables 
            WHERE table_schema = %s 
            AND table_name = 'user_context'
        """, (DB_CONFIG['database'],))
        
        table_exists = cursor.fetchone()['count'] > 0
        
        if not table_exists:
            return {}
        
        # Always query with the string version
        cursor.execute(
            "SELECT context_data FROM user_context WHERE telegram_id = %s",
            (telegram_id_str,)
        )
        result = cursor.fetchone()
        
        if result and result['context_data']:
            # MySQL returns JSON data already parsed
            context_data = result['context_data']
            
            if isinstance(context_data, dict):
                return context_data
            elif isinstance(context_data, str):
                try:
                    return json.loads(context_data)
                except json.JSONDecodeError:
                    return {"value": context_data}
            else:
                return {"value": str(context_data)}
        else:
            return {}
            
    except Exception as e:
        logger.error(f"Error getting user context: {e}", exc_info=True)
        return {}
    finally:
        if conn and conn.is_connected():
            conn.close()


def clear_user_context(telegram_id):
    """Clear context data for a user
    
    Args:
        telegram_id (int or str): Telegram user ID (can be encrypted)
        
    Returns:
        bool: True if successful, False otherwise
    """
    conn = None
    try:
        # Always convert telegram_id to string
        telegram_id_str = str(telegram_id)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = %s 
            AND table_name = 'user_context'
        """, (DB_CONFIG['database'],))
        
        table_exists = cursor.fetchone()[0] > 0
        
        if not table_exists:
            return True  # No table means nothing to clear
        
        # Always use string version
        cursor.execute(
            "DELETE FROM user_context WHERE telegram_id = %s",
            (telegram_id_str,)
        )
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error clearing user context: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()


# -------------------------
# REVIEW FUNCTIONS
# -------------------------

def add_review(order_id, customer_id, artisan_id, rating, comment=None):
    """Add a review for an artisan
    
    Args:
        order_id (int): ID of the order
        customer_id (int): ID of the customer
        artisan_id (int): ID of the artisan
        rating (int): Rating (1-5)
        comment (str, optional): Review comment
        
    Returns:
        int: ID of the created review
    """
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Insert review
        cursor.execute(
            """
            INSERT INTO reviews (order_id, customer_id, artisan_id, rating, comment, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            """,
            (order_id, customer_id, artisan_id, rating, comment)
        )
        
        review_id = cursor.lastrowid
        
        # Update artisan's average rating
        cursor.execute(
            """
            UPDATE artisans 
            SET rating = (
                SELECT AVG(rating) 
                FROM reviews 
                WHERE artisan_id = %s
            )
            WHERE id = %s
            """,
            (artisan_id, artisan_id)
        )
        
        conn.commit()
        return review_id
    except Exception as e:
        logger.error(f"Error adding review: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def get_artisan_reviews(artisan_id):
    """Get reviews for a specific artisan
    
    Args:
        artisan_id (int): ID of the artisan
        
    Returns:
        list: List of reviews
    """
    query = """
        SELECT r.*, c.name as customer_name, o.service, o.subservice
        FROM reviews r
        JOIN customers c ON r.customer_id = c.id
        JOIN orders o ON r.order_id = o.id
        WHERE r.artisan_id = %s
        ORDER BY r.created_at DESC
    """
    
    return execute_query(query, (artisan_id,), fetchall=True, dict_cursor=True)


def get_artisan_average_rating(artisan_id):
    """Get average rating for an artisan
    
    Args:
        artisan_id (int): ID of the artisan
        
    Returns:
        float: Average rating or None if no reviews
    """
    query = "SELECT rating FROM artisans WHERE id = %s"
    result = execute_query(query, (artisan_id,), fetchone=True)
    
    return result[0] if result else None


# -------------------------
# STATISTICS FUNCTIONS
# -------------------------

def get_artisan_statistics(artisan_id):
    """Get statistics for a specific artisan
    
    Args:
        artisan_id (int): ID of the artisan
        
    Returns:
        dict: Statistics dict or None if error
    """
    try:
        # Get total customers
        customers_query = """
            SELECT COUNT(DISTINCT customer_id) 
            FROM orders 
            WHERE artisan_id = %s
        """
        total_customers = execute_query(customers_query, (artisan_id,), fetchone=True)[0]
        
        # Get completed orders count
        completed_query = """
            SELECT COUNT(*) 
            FROM orders 
            WHERE artisan_id = %s AND status = 'completed'
        """
        completed_orders = execute_query(completed_query, (artisan_id,), fetchone=True)[0]
        
        # Get cancelled orders count
        cancelled_query = """
            SELECT COUNT(*) 
            FROM orders 
            WHERE artisan_id = %s AND status = 'cancelled'
        """
        cancelled_orders = execute_query(cancelled_query, (artisan_id,), fetchone=True)[0]
        
        # Get average rating
        rating_query = "SELECT rating FROM artisans WHERE id = %s"
        avg_rating_result = execute_query(rating_query, (artisan_id,), fetchone=True)
        avg_rating = avg_rating_result[0] if avg_rating_result and avg_rating_result[0] is not None else 0
        
        # Get total earnings
        earnings_query = """
            SELECT COALESCE(SUM(artisan_amount), 0) 
            FROM order_payments op
            JOIN orders o ON op.order_id = o.id
            WHERE o.artisan_id = %s AND o.status = 'completed'
        """
        total_earnings = execute_query(earnings_query, (artisan_id,), fetchone=True)[0]
        
        # Get monthly earnings (last 30 days)
        monthly_earnings_query = """
            SELECT COALESCE(SUM(artisan_amount), 0) 
            FROM order_payments op
            JOIN orders o ON op.order_id = o.id
            WHERE o.artisan_id = %s 
            AND o.status = 'completed'
            AND o.completed_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """
        monthly_earnings = execute_query(monthly_earnings_query, (artisan_id,), fetchone=True)[0]
        
        # Get orders from last 7 days
        last_week_query = """
            SELECT COUNT(*) 
            FROM orders 
            WHERE artisan_id = %s
            AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        """
        last_week_orders = execute_query(last_week_query, (artisan_id,), fetchone=True)[0]
        
        # Get orders from last 30 days
        last_month_query = """
            SELECT COUNT(*) 
            FROM orders 
            WHERE artisan_id = %s
            AND created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """
        last_month_orders = execute_query(last_month_query, (artisan_id,), fetchone=True)[0]
        
        # Get orders from previous 30 days (for growth calculation)
        prev_month_query = """
            SELECT COUNT(*) 
            FROM orders 
            WHERE artisan_id = %s
            AND created_at >= DATE_SUB(NOW(), INTERVAL 60 DAY)
            AND created_at < DATE_SUB(NOW(), INTERVAL 30 DAY)
        """
        prev_month_orders = execute_query(prev_month_query, (artisan_id,), fetchone=True)[0]
        
        # Calculate order growth rate
        order_growth = 0
        if prev_month_orders > 0:
            order_growth = round(((last_month_orders - prev_month_orders) / prev_month_orders) * 100)
        
        # Get most requested subservice
        top_service_query = """
            SELECT subservice, COUNT(*) as count
            FROM orders
            WHERE artisan_id = %s AND subservice IS NOT NULL
            GROUP BY subservice
            ORDER BY count DESC
            LIMIT 1
        """
        top_service_result = execute_query(top_service_query, (artisan_id,), fetchone=True)
        top_service = top_service_result[0] if top_service_result else "N/A"
        
        # Get most profitable subservice
        profitable_service_query = """
            SELECT o.subservice, SUM(op.artisan_amount) as amount
            FROM orders o
            JOIN order_payments op ON o.id = op.order_id
            WHERE o.artisan_id = %s AND o.subservice IS NOT NULL
            GROUP BY o.subservice
            ORDER BY amount DESC
            LIMIT 1
        """
        profitable_result = execute_query(profitable_service_query, (artisan_id,), fetchone=True)
        most_profitable_service = profitable_result[0] if profitable_result else "N/A"
        
        # Determine activity status based on orders in last 30 days
        activity_status = "Qeyri-aktiv"
        if last_month_orders >= 10:
            activity_status = "Yüksək aktivlik"
        elif last_month_orders >= 5:
            activity_status = "Orta aktivlik"
        elif last_month_orders >= 1:
            activity_status = "Aşağı aktivlik"
        
        # Compile all statistics
        stats = {
            "total_customers": total_customers,
            "completed_orders": completed_orders,
            "cancelled_orders": cancelled_orders,
            "avg_rating": avg_rating,
            "total_earnings": total_earnings,
            "monthly_earnings": monthly_earnings,
            "last_week_orders": last_week_orders,
            "last_month_orders": last_month_orders,
            "order_growth": order_growth,
            "top_service": top_service,
            "most_profitable_service": most_profitable_service,
            "activity_status": activity_status
        }
        
        return stats
    except Exception as e:
        logger.error(f"Error getting artisan statistics: {e}")
        return None


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in kilometers using the haversine formula
    
    Args:
        lat1 (float): Latitude of point 1
        lon1 (float): Longitude of point 1
        lat2 (float): Latitude of point 2
        lon2 (float): Longitude of point 2
        
    Returns:
        float: Distance in kilometers
    """
    # Earth radius in kilometers
    R = 6371
    
    # Convert latitude and longitude from degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Differences
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    
    # Haversine formula
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance = R * c
    
    return distance


# -------------------------
# DEBUGGING FUNCTIONS
# -------------------------

def debug_order_payment(order_id):
    """Debug function to check order payment details"""
    try:
        # Detailed query to get all payment info
        query = """
            SELECT o.id as order_id, o.price, o.status, 
                  op.payment_method, op.payment_status, op.amount, 
                  op.admin_fee, op.artisan_amount, op.receipt_file_id,
                  op.receipt_uploaded_at, op.receipt_verified,
                  op.admin_payment_completed, op.created_at, op.updated_at
            FROM orders o
            LEFT JOIN order_payments op ON o.id = op.order_id
            WHERE o.id = %s
        """
        
        result = execute_query(query, (order_id,), fetchone=True, dict_cursor=True)
        
        return result
    except Exception as e:
        logger.error(f"Error in debug_order_payment: {e}")
        return None


def check_receipt_verification_status(order_id):
    """Check the receipt verification status for an order
    
    Args:
        order_id (int): ID of the order
        
    Returns:
        str or None: Verification status ('verified', 'invalid', 'pending') or None if not found
    """
    try:
        query = """
            SELECT receipt_verified
            FROM order_payments
            WHERE order_id = %s
        """
        
        result = execute_query(query, (order_id,), fetchone=True)
        
        if result is not None:
            if result[0] == 1:  # MySQL stores boolean as 0/1
                return 'verified'
            elif result[0] == 0:
                return 'invalid'
            elif result[0] is None:
                return 'pending'
        return None
    except Exception as e:
        logger.error(f"Error checking receipt verification status: {e}", exc_info=True)
        return None


def block_customer(customer_id, reason, required_payment, block_hours=24):
    """Block a customer
    
    Args:
        customer_id (int): ID of the customer
        reason (str): Reason for blocking
        required_payment (float): Amount needed to unblock
        block_hours (int): Hours for which to block
        
    Returns:
        bool: True if successful, False otherwise
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Update customer to set as inactive
        cursor.execute(
            "UPDATE customers SET active = FALSE WHERE id = %s",
            (customer_id,)
        )
        
        # Calculate block duration
        if block_hours > 0:
            block_timestamp = datetime.datetime.now() + datetime.timedelta(hours=block_hours)
            block_until = block_timestamp.strftime("%Y-%m-%d %H:%M:%S")
        else:
            block_until = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Insert block record
        cursor.execute(
            """
            INSERT INTO customer_blocks 
            (customer_id, is_blocked, block_reason, required_payment, block_until, created_at)
            VALUES (%s, TRUE, %s, %s, DATE_ADD(NOW(), INTERVAL %s HOUR), NOW())
            """,
            (customer_id, reason, required_payment, block_hours)
        )
        
        conn.commit()
        logger.info(f"Successfully blocked customer {customer_id} for reason: {reason}")
        return True
    except Exception as e:
        logger.error(f"Error blocking customer: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()


def get_customer_blocked_status(customer_id):
    """Check if a customer is blocked and get the reason
    
    Args:
        customer_id (int): ID of the customer
        
    Returns:
        tuple: (bool is_blocked, str reason, float required_payment, datetime block_until)
    """
    try:
        # First check if the table exists
        check_table_query = """
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = %s AND table_name = 'customer_blocks'
        """
        
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(check_table_query, (DB_CONFIG['database'],))
        table_exists = cursor.fetchone()[0] > 0
        
        if not table_exists:
            # Table doesn't exist, customer can't be blocked
            return False, None, 0, None
        
        query = """
            SELECT is_blocked, block_reason, required_payment, block_until
            FROM customer_blocks
            WHERE customer_id = %s AND is_blocked = TRUE
            ORDER BY created_at DESC
            LIMIT 1
        """
        
        cursor.execute(query, (customer_id,))
        result = cursor.fetchone()
        
        if result:
            return bool(result[0]), result[1], float(result[2]), result[3]
        else:
            return False, None, 0, None
    except Exception as e:
        logger.error(f"Error checking customer blocked status: {e}")
        return False, None, 0, None
    finally:
        if conn and conn.is_connected():
            conn.close()


def update_receipt_verification_status(order_id, is_verified):
    """Update receipt verification status
    
    Args:
        order_id (int): ID of the order
        is_verified (bool or None): Verification status (True, False, or None)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Different query based on verification status
        if is_verified is True:
            # If verified, also update payment_status to completed and set admin_payment_completed to TRUE
            query = """
                UPDATE order_payments
                SET receipt_verified = %s,
                    payment_status = 'completed',
                    admin_payment_completed = TRUE,
                    updated_at = NOW()
                WHERE order_id = %s
            """
        elif is_verified is False:
            # If rejected, update payment_status to rejected and ensure admin_payment_completed is FALSE
            query = """
                UPDATE order_payments
                SET receipt_verified = %s,
                    payment_status = 'rejected',
                    admin_payment_completed = FALSE,
                    updated_at = NOW()
                WHERE order_id = %s
            """
        else:
            # If status is None (pending), just update receipt_verified
            query = """
                UPDATE order_payments
                SET receipt_verified = %s,
                    updated_at = NOW()
                WHERE order_id = %s
            """
        
        # Convert Python None to MySQL NULL
        params = [is_verified if is_verified is not None else None, order_id]
        
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(query, params)
        
        # If receipt is verified, also update the order table status
        if is_verified is True:
            cursor.execute(
                """
                UPDATE orders
                SET payment_status = 'completed'
                WHERE id = %s
                """,
                (order_id,)
            )
        elif is_verified is False:
            cursor.execute(
                """
                UPDATE orders
                SET payment_status = 'rejected'
                WHERE id = %s
                """,
                (order_id,)
            )
        
        conn.commit()
        
        # Check if any rows were affected
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error updating receipt verification status: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()


def set_admin_payment_completed(order_id, is_completed):
    """Set admin payment completed status
    
    Args:
        order_id (int): ID of the order
        is_completed (bool): Whether payment is completed
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        query = """
            UPDATE order_payments
            SET admin_payment_completed = %s,
                updated_at = NOW()
            WHERE order_id = %s
        """
        
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(query, (is_completed, order_id))
        conn.commit()
        
        # Check if any rows were affected
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error setting admin payment completed: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()


def get_admin_payment_completed(order_id):
    """Check if admin payment is completed
    
    Args:
        order_id (int): ID of the order
        
    Returns:
        bool: True if completed, False otherwise
    """
    try:
        query = """
            SELECT admin_payment_completed
            FROM order_payments
            WHERE order_id = %s
        """
        
        result = execute_query(query, (order_id,), fetchone=True)
        
        return bool(result and result[0])
    except Exception as e:
        logger.error(f"Error checking admin payment completion: {e}")
        return False


def save_customer_fine_receipt(customer_id, file_id):
    """Save customer fine payment receipt
    
    Args:
        customer_id (int): ID of the customer
        file_id (str): Telegram file ID of the receipt
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = %s 
            AND table_name = 'customer_fine_receipts'
        """, (DB_CONFIG['database'],))
        
        table_exists = cursor.fetchone()[0] > 0
        
        # Create table if it doesn't exist
        if not table_exists:
            cursor.execute("""
                CREATE TABLE customer_fine_receipts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    customer_id INT NOT NULL,
                    file_id VARCHAR(255) NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    verified_by INT,
                    verified_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
                )
            """)
        
        # Insert receipt record
        cursor.execute("""
            INSERT INTO customer_fine_receipts 
            (customer_id, file_id, status, created_at)
            VALUES (%s, %s, 'pending', NOW())
        """, (customer_id, file_id))
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving customer fine receipt: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()


def unblock_customer(customer_id):
    """Unblock a customer
    
    Args:
        customer_id (int): ID of the customer
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Set customer as active
    update_query = "UPDATE customers SET active = TRUE WHERE id = %s"
    
    # Update block record
    block_query = """
        UPDATE customer_blocks
        SET is_blocked = FALSE, unblocked_at = NOW()
        WHERE customer_id = %s AND is_blocked = TRUE
    """
    
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(update_query, (customer_id,))
        cursor.execute(block_query, (customer_id,))
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error unblocking customer: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()


def create_refund_request(order_id, amount, reason):
    """Create a refund request
    
    Args:
        order_id (int): ID of the order
        amount (float): Amount to refund
        reason (str): Reason for the refund
        
    Returns:
        int: ID of the created refund request or None if failed
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = %s 
            AND table_name = 'refund_requests'
        """, (DB_CONFIG['database'],))
        
        table_exists = cursor.fetchone()[0] > 0
        
        # Create table if it doesn't exist
        if not table_exists:
            cursor.execute("""
                CREATE TABLE refund_requests (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    order_id INT NOT NULL,
                    amount DECIMAL(10, 2) NOT NULL,
                    reason TEXT NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    card_number VARCHAR(50),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    completed_by INT,
                    completed_at DATETIME,
                    FOREIGN KEY (order_id) REFERENCES orders(id)
                )
            """)
        
        # Insert refund request
        cursor.execute("""
            INSERT INTO refund_requests 
            (order_id, amount, reason, status, created_at)
            VALUES (%s, %s, %s, 'pending', NOW())
        """, (order_id, amount, reason))
        
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        logger.error(f"Error creating refund request: {e}", exc_info=True)
        return None
    finally:
        if conn and conn.is_connected():
            conn.close()


def get_refund_request(refund_id):
    """Get refund request by ID
    
    Args:
        refund_id (int): ID of the refund request
        
    Returns:
        dict: Refund request details or None if not found
    """
    try:
        query = """
            SELECT * 
            FROM refund_requests
            WHERE id = %s
        """
        
        result = execute_query(query, (refund_id,), fetchone=True, dict_cursor=True)
        return result
    except Exception as e:
        logger.error(f"Error getting refund request: {e}")
        return None


def update_refund_request(refund_id, data):
    """Update refund request
    
    Args:
        refund_id (int): ID of the refund request
        data (dict): Data to update
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        valid_fields = ['status', 'card_number', 'completed_by', 'completed_at']
        update_parts = []
        params = []
        
        for field in valid_fields:
            if field in data and data[field] is not None:
                if field == 'completed_at' and data[field] == 'CURRENT_TIMESTAMP':
                    update_parts.append(f"{field} = NOW()")
                else:
                    update_parts.append(f"{field} = %s")
                    params.append(data[field])
        
        if not update_parts:
            return False  # Nothing to update
            
        params.append(refund_id)  # For the WHERE clause
        
        query = f"""
            UPDATE refund_requests
            SET {', '.join(update_parts)}
            WHERE id = %s
        """
        
        execute_query(query, params, commit=True)
        return True
    except Exception as e:
        logger.error(f"Error updating refund request: {e}")
        return False


def mark_admin_payment_completed(order_id):
    """Mark admin payment as completed
    
    Args:
        order_id (int): ID of the order
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE order_payments 
            SET admin_payment_completed = TRUE
            WHERE order_id = %s
        """, (order_id,))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"DB error in mark_admin_payment_completed: {e}")
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()

# Encryption wrappers
from db_encryption_wrapper import (
    wrap_create_customer, wrap_create_artisan, wrap_get_dict_function,
    wrap_get_list_function, wrap_update_customer_profile, wrap_update_artisan_profile
)

# Normal (şifresi çözülmüş ama maskelenmemiş) versiyonlar - kendi verilerini görüntülemek için
get_customer_by_telegram_id = wrap_get_dict_function(get_customer_by_telegram_id, decrypt=True, mask=False)
get_customer_by_id = wrap_get_dict_function(get_customer_by_id, decrypt=True, mask=False)
create_customer = wrap_create_customer(create_customer)
update_customer_profile = wrap_update_customer_profile(update_customer_profile)
get_customer_orders = wrap_get_list_function(get_customer_orders, decrypt=True, mask=False)
get_artisan_by_id = wrap_get_dict_function(get_artisan_by_id, decrypt=True, mask=False)
create_artisan = wrap_create_artisan(create_artisan)
update_artisan_profile = wrap_update_artisan_profile(update_artisan_profile)
get_artisan_active_orders = wrap_get_list_function(get_artisan_active_orders, decrypt=True, mask=False)
get_order_details = wrap_get_dict_function(get_order_details, decrypt=True, mask=False)
debug_order_payment = wrap_get_dict_function(debug_order_payment, decrypt=True, mask=False)

# Ekstra: Hassas veri döndüren diğer fonksiyonlar için de wrapper ekle
get_artisan_by_service = wrap_get_list_function(get_artisan_by_service)
get_nearby_artisans = wrap_get_list_function(get_nearby_artisans)
get_artisan_reviews = wrap_get_list_function(get_artisan_reviews)

def save_payment_card_info(artisan_id, card_number, card_holder):
    card_number = encrypt_data(card_number)
    card_holder = encrypt_data(card_holder)
    # ... insert into DB

# Maskelenmiş fonksiyonlar - diğer kullanıcılara görüntülenecek veriler için
def get_masked_customer_by_id(customer_id):
    """Müşteri bilgilerini maskelenmiş olarak al"""
    return wrap_get_dict_function(get_customer_by_id, decrypt=True, mask=True)(customer_id)

def get_masked_artisan_by_id(artisan_id):
    """Usta bilgilerini maskelenmiş olarak al"""
    return wrap_get_dict_function(get_artisan_by_id, decrypt=True, mask=True)(artisan_id)

def get_masked_order_details(order_id):
    """Sipariş detaylarını maskelenmiş olarak al"""
    return wrap_get_dict_function(get_order_details, decrypt=True, mask=True)(order_id)

get_artisan_by_service = wrap_get_list_function(get_artisan_by_service, decrypt=True, mask=False)
get_nearby_artisans = wrap_get_list_function(get_nearby_artisans, decrypt=True, mask=False)
get_artisan_reviews = wrap_get_list_function(get_artisan_reviews, decrypt=True, mask=False)

# Maskelenmiş listeler için fonksiyon
def get_masked_customer_orders(customer_id):
    """Müşteri siparişlerini maskelenmiş olarak al"""
    return wrap_get_list_function(get_customer_orders, decrypt=True, mask=True)(customer_id)

def get_masked_artisan_active_orders(artisan_id):
    """Usta aktif siparişlerini maskelenmiş olarak al"""
    return wrap_get_list_function(get_artisan_active_orders, decrypt=True, mask=True)(artisan_id)