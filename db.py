# db.py

import psycopg2
from psycopg2.extras import RealDictCursor
import math
from datetime import datetime
from config import DB_CONFIG, COMMISSION_RATES
from psycopg2.pool import SimpleConnectionPool
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_connection():
    """Establish and return a connection to the database"""
    return psycopg2.connect(**DB_CONFIG)

def execute_query(query, params=None, fetchone=False, fetchall=False, commit=False, dict_cursor=False):
    """Execute a database query with error handling and connection management"""
    conn = None
    cursor = None
    result = None
    
    try:
        conn = get_connection()
        if dict_cursor:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
        else:
            cursor = conn.cursor()
            
        cursor.execute(query, params)
        
        if fetchone:
            result = cursor.fetchone()
        elif fetchall:
            result = cursor.fetchall()
            
        if commit:
            conn.commit()
            
        return result
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        print(f"Database error: {e}")
        raise e
    finally:
        if cursor:
            cursor.close()
        if conn:
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
    query = """
        SELECT * FROM customers 
        WHERE telegram_id = %s
    """
    
    result = execute_query(query, (telegram_id,), fetchone=True, dict_cursor=True)
    
    return dict(result) if result else None


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
    
    return dict(result) if result else None

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
    query = """
        INSERT INTO customers (telegram_id, name, phone, city, created_at)
        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
        RETURNING id
    """
    
    result = execute_query(query, (telegram_id, name, phone, city), fetchone=True, commit=True)
    
    return result[0] if result else None

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
        print(f"Error updating customer profile: {e}")
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
               o.status, o.subservice  -- Bunları ekleyelim
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
    """Get artisan ID by Telegram ID
    
    Args:
        telegram_id (int): Telegram user ID
        
    Returns:
        int: Artisan ID or None if not found
    """
    query = """
        SELECT id FROM artisans 
        WHERE telegram_id = %s
    """
    result = execute_query(query, (telegram_id,), fetchone=True)
    
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
    
    return dict(result) if result else None

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
    query = """
        INSERT INTO artisans (telegram_id, name, phone, service, location, city, 
                              latitude, longitude, active, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP)
        RETURNING id
    """
    
    result = execute_query(
        query, 
        (telegram_id, name, phone, service, location, city, latitude, longitude),
        fetchone=True,
        commit=True
    )
    
    return result[0] if result else None

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
        print(f"Error updating artisan profile: {e}")
        return False

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
        print(f"Error updating artisan location: {e}")
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
        
    current_status = result[0]
    new_status = not current_status
    
    # Update status
    update_query = "UPDATE artisans SET active = %s WHERE id = %s"
    
    try:
        execute_query(update_query, (new_status, artisan_id), commit=True)
        return True, new_status
    except Exception as e:
        print(f"Error toggling artisan status: {e}")
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
        print(f"Error updating artisan service: {e}")
        return False
    finally:
        if conn:
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
        VALUES (%s, TRUE, %s, %s, CURRENT_TIMESTAMP)
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
        print(f"Error blocking artisan: {e}")
        return False
    finally:
        if conn:
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
        SET is_blocked = FALSE, unblocked_at = CURRENT_TIMESTAMP
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
        print(f"Error unblocking artisan: {e}")
        return False
    finally:
        if conn:
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
        VALUES (%s, %s, 'pending', CURRENT_TIMESTAMP)
        RETURNING id
    """
    
    try:
        result = execute_query(query, (artisan_id, file_id), fetchone=True, commit=True)
        return bool(result)
    except Exception as e:
        print(f"Error saving fine receipt: {e}")
        return False

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
        return dict(result) if result else None
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
                VALUES (%s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP)
            """
            execute_query(insert_query, (artisan_id, subservice_id, min_price, max_price), commit=True)
            
        return True
    except Exception as e:
        print(f"Error updating price range: {e}")
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

def insert_order(customer_id, artisan_id, service, date_time, note, latitude=None, longitude=None, location_name=None, status='pending', subservice=None):
    """Insert a new order into the database
    
    Args:
        customer_id (int): ID of the customer
        artisan_id (int): ID of the artisan
        service (str): Type of service requested
        date_time (str): Date and time for the service
        note (str): Additional information about the order
        latitude (float, optional): Customer's latitude
        longitude (float, optional): Customer's longitude
        location_name (str, optional): Name of the location
        status (str, optional): Order status (default: 'pending')
        subservice (str, optional): Specific subservice requested
        
    Returns:
        int: ID of the inserted order
    """
    
    query = """
    INSERT INTO orders (customer_id, artisan_id, service, date_time, note,
                   latitude, longitude, location_name, status, subservice, created_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
    RETURNING id
    """
    
    # Default status değeri fonksiyon imzasında tanımlanmıştır
    # Bu satırı kaldırabilirsiniz çünkü artık gereksiz
    # status = 'pending' 
    
    # Parse date_time string to datetime object if needed
    if isinstance(date_time, str):
        try:
            # Try to parse the date_time string
            date_time = datetime.strptime(date_time, "%Y-%m-%d %H:%M")
        except ValueError:
            # If it's not in the expected format, keep it as is
            pass
    
    result = execute_query(
        query, 
        (customer_id, artisan_id, service, date_time, note, latitude, longitude, location_name, status, subservice),
        fetchone=True,
        commit=True
    )
    
    return result[0] if result else None

def get_order_details(order_id):
    """Get detailed information about an order
    
    Args:
        order_id (int): ID of the order
        
    Returns:
        dict: Order details or None if not found
    """
    query = """
        SELECT o.*, 
               c.name as customer_name, c.phone as customer_phone,
               a.name as artisan_name, a.phone as artisan_phone, 
               o.latitude, o.longitude, o.location_name,
               COALESCE(op.amount, o.price) as price,
               op.admin_fee, op.artisan_amount, 
               op.payment_status, op.payment_method
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        JOIN artisans a ON o.artisan_id = a.id
        LEFT JOIN order_payments op ON o.id = op.order_id
        WHERE o.id = %s
    """
    
    result = execute_query(query, (order_id,), fetchone=True, dict_cursor=True)
    
    # Extra logging for debugging
    if result:
        logger.info(f"Retrieved order details for order {order_id}. Price: {result.get('price')}")
    else:
        logger.warning(f"No order found with ID {order_id}")
    
    return dict(result) if result else None 

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
            timestamp_query = "UPDATE orders SET completed_at = CURRENT_TIMESTAMP WHERE id = %s"
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
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
    """
    
    try:
        # Start with updating the orders table
        execute_query(update_order_query, (price, order_id), commit=True)
        
        # Check if payment record exists
        check_query = "SELECT id FROM order_payments WHERE order_id = %s"
        payment_exists = execute_query(check_query, (order_id,), fetchone=True)
        
        if payment_exists:
            # Update existing payment record
            update_query = """
                UPDATE order_payments 
                SET amount = %s, admin_fee = %s, artisan_amount = %s
                WHERE order_id = %s
            """
            execute_query(update_query, (price, admin_fee, artisan_amount, order_id), commit=True)
        else:
            # Create new payment record
            insert_query = """
                INSERT INTO order_payments 
                (order_id, amount, admin_fee, artisan_amount, payment_status, created_at)
                VALUES (%s, %s, %s, %s, 'pending', CURRENT_TIMESTAMP)
            """
            execute_query(insert_query, (order_id, price, admin_fee, artisan_amount), commit=True)
        
        # Verify price was set
        verify_query = "SELECT price FROM orders WHERE id = %s"
        verify_result = execute_query(verify_query, (order_id,), fetchone=True)
        if verify_result and verify_result[0] is not None:
            logger.info(f"Price for order {order_id} set successfully to {price} AZN")
            return True
        else:
            logger.error(f"Failed to verify price for order {order_id}")
            return False
            
    except Exception as e:
        logger.error(f"Error setting order price: {e}", exc_info=True)
        return False

def update_payment_method(order_id, payment_method):
    """Update the payment method for an order
    
    Args:
        order_id (int): ID of the order
        payment_method (str): Payment method ('card' or 'cash')
        
    Returns:
        bool: True if successful, False otherwise
    """
    query = """
        UPDATE order_payments 
        SET payment_method = %s
        WHERE order_id = %s
    """
    
    try:
        execute_query(query, (payment_method, order_id), commit=True)
        return True
    except Exception as e:
        print(f"Error updating payment method: {e}")
        return False

# save_payment_receipt fonksiyonunda şu değişiklikleri yapalım
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
                        receipt_uploaded_at = CURRENT_TIMESTAMP,
                        payment_status = 'pending',
                        payment_date = CURRENT_TIMESTAMP,
                        receipt_verified = FALSE,
                        admin_payment_completed = FALSE
                    WHERE order_id = %s
                    RETURNING id
                    """,
                    (file_id, order_id)
                )
                update_result = cursor.fetchone()
                
                if not update_result:
                    logger.error(f"Failed to update payment record for order {order_id}")
                    # Try direct update without returning
                    cursor.execute(
                        """
                        UPDATE order_payments 
                        SET receipt_file_id = %s,
                            receipt_uploaded_at = CURRENT_TIMESTAMP,
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
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, 'pending', 'cash', CURRENT_TIMESTAMP, 
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, FALSE)
                    RETURNING id
                    """,
                    (order_id, price, admin_fee, artisan_amount, file_id)
                )
                insert_result = cursor.fetchone()
                
                if not insert_result:
                    logger.error(f"Failed to insert payment record for order {order_id}")
                    conn.rollback()
                    return False
            
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
            if conn:
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
            payment_date = CURRENT_TIMESTAMP
        WHERE order_id = %s
    """
    
    try:
        execute_query(query, (status, order_id), commit=True)
        return True
    except Exception as e:
        print(f"Error confirming payment: {e}")
        return False

# -------------------------
# USER CONTEXT FUNCTIONS
# -------------------------

def set_user_context(telegram_id, context_data):
    """Set context data for a user
    
    Args:
        telegram_id (int): Telegram user ID
        context_data (dict or str): Context data to store
        
    Returns:
        bool: True if successful, False otherwise
    """
    import json
    
    try:
        # Ensure we're storing a string in the database
        context_json = None
        
        if isinstance(context_data, dict):
            # Convert datetime objects to strings
            cleaned_data = {}
            for key, value in context_data.items():
                if isinstance(value, datetime):
                    cleaned_data[key] = value.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    cleaned_data[key] = value
            
            # Ensure we're serializing a valid dictionary
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
        
        # Log the actual JSON being stored for debugging
        logger.debug(f"Storing context as JSON: {context_json}")
        
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Check if context exists
            cursor.execute(
                "SELECT id FROM user_context WHERE telegram_id = %s",
                (telegram_id,)
            )
            context_exists = cursor.fetchone()
            
            if context_exists:
                cursor.execute(
                    """
                    UPDATE user_context 
                    SET context_data = %s::jsonb, updated_at = CURRENT_TIMESTAMP
                    WHERE telegram_id = %s
                    """,
                    (context_json, telegram_id)
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO user_context (telegram_id, context_data, created_at, updated_at)
                    VALUES (%s, %s::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (telegram_id, context_json)
                )
            
            conn.commit()
            return True
        except Exception as db_error:
            if conn:
                conn.rollback()
            logger.error(f"Database error in set_user_context: {db_error}", exc_info=True)
            return False
        finally:
            if conn:
                conn.close()
                
    except Exception as e:
        logger.error(f"Error setting user context: {e}", exc_info=True)
        return False

def get_user_context(telegram_id):
    """Get context data for a user
    
    Args:
        telegram_id (int): Telegram user ID
        
    Returns:
        dict: Context data or empty dict if not found
    """
    import json
    
    conn = None
    try:
        # Direct database connection for better error handling
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT context_data FROM user_context WHERE telegram_id = %s",
            (telegram_id,)
        )
        result = cursor.fetchone()
        
        if result and result[0]:
            # Parse JSON data based on its type
            context_data = result[0]
            
            # For string type (most likely scenario)
            if isinstance(context_data, str):
                try:
                    return json.loads(context_data)
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON string from database: {e}")
                    return {}
            
            # For dict type (if PostgreSQL returns it as a dict already)
            elif isinstance(context_data, dict):
                return context_data
                
            # For binary data
            elif isinstance(context_data, (bytes, bytearray)):
                try:
                    context_str = context_data.decode('utf-8')
                    return json.loads(context_str)
                except Exception as e:
                    logger.error(f"Error decoding bytes to string: {e}")
                    return {}
            
            else:
                # For any other type, log a warning
                logger.warning(f"Unexpected type in context_data: {type(result[0])}")
                return {"value": str(context_data)}
        else:
            return {}
            
    except Exception as e:
        logger.error(f"Error getting user context: {e}", exc_info=True)
        return {}
    finally:
        if conn:
            conn.close()

def clear_user_context(telegram_id):
    """Clear context data for a user
    
    Args:
        telegram_id (int): Telegram user ID
        
    Returns:
        bool: True if successful, False otherwise
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "DELETE FROM user_context WHERE telegram_id = %s",
            (telegram_id,)
        )
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error clearing user context: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


def clear_user_context(telegram_id):
    """Clear context data for a user
    
    Args:
        telegram_id (int): Telegram user ID
        
    Returns:
        bool: True if successful, False otherwise
    """
    query = "DELETE FROM user_context WHERE telegram_id = %s"
    
    try:
        execute_query(query, (telegram_id,), commit=True)
        return True
    except Exception as e:
        print(f"Error clearing user context: {e}")
        return False

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
    query = """
        INSERT INTO reviews (order_id, customer_id, artisan_id, rating, comment, created_at)
        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        RETURNING id
    """
    
    result = execute_query(
        query, 
        (order_id, customer_id, artisan_id, rating, comment),
        fetchone=True,
        commit=True
    )
    
    # Update artisan's average rating
    update_rating_query = """
        UPDATE artisans 
        SET rating = (
            SELECT AVG(rating) 
            FROM reviews 
            WHERE artisan_id = %s
        )
        WHERE id = %s
    """
    execute_query(update_rating_query, (artisan_id, artisan_id), commit=True)
    
    return result[0] if result else None

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
        avg_rating = avg_rating_result[0] if avg_rating_result[0] is not None else 0
        
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
            AND o.completed_at >= NOW() - INTERVAL '30 days'
        """
        monthly_earnings = execute_query(monthly_earnings_query, (artisan_id,), fetchone=True)[0]
        
        # Get orders from last 7 days
        last_week_query = """
            SELECT COUNT(*) 
            FROM orders 
            WHERE artisan_id = %s
            AND created_at >= NOW() - INTERVAL '7 days'
        """
        last_week_orders = execute_query(last_week_query, (artisan_id,), fetchone=True)[0]
        
        # Get orders from last 30 days
        last_month_query = """
            SELECT COUNT(*) 
            FROM orders 
            WHERE artisan_id = %s
            AND created_at >= NOW() - INTERVAL '30 days'
        """
        last_month_orders = execute_query(last_month_query, (artisan_id,), fetchone=True)[0]
        
        # Get orders from previous 30 days (for growth calculation)
        prev_month_query = """
            SELECT COUNT(*) 
            FROM orders 
            WHERE artisan_id = %s
            AND created_at >= NOW() - INTERVAL '60 days'
            AND created_at < NOW() - INTERVAL '30 days'
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
        print(f"Error getting artisan statistics: {e}")
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



# db.py içerisine debug fonksiyonlarını ekleyelim
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
        
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(query, (order_id,))
        result = cursor.fetchone()
        conn.close()
        
        return dict(result) if result else None
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
        
        if result:
            if result[0] is True:
                return 'verified'
            elif result[0] is False:
                return 'invalid'
            else:
                return 'pending'
        return None
    except Exception as e:
        logger.error(f"Error checking receipt verification status: {e}", exc_info=True)
        return None

# Make sure this function is correctly implemented in db.py

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
    # Create a new table for customer blocks if it doesn't exist
    create_table_query = """
        CREATE TABLE IF NOT EXISTS customer_blocks (
            id SERIAL PRIMARY KEY,
            customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            is_blocked BOOLEAN DEFAULT TRUE,
            block_reason TEXT,
            required_payment NUMERIC(10,2) DEFAULT 0,
            block_until TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            unblocked_at TIMESTAMP
        )
    """
    
    try:
        # Create the table first (if it doesn't exist)
        execute_query(create_table_query, commit=True)
        
        # Update customer to set as blocked
        update_query = """
            UPDATE customers
            SET active = FALSE
            WHERE id = %s
        """
        
        # Calculate block until time
        import datetime
        block_until = datetime.datetime.now() + datetime.timedelta(hours=block_hours)
        
        # Insert block record
        block_query = """
            INSERT INTO customer_blocks 
            (customer_id, is_blocked, block_reason, required_payment, block_until, created_at)
            VALUES (%s, TRUE, %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id
        """
        
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(update_query, (customer_id,))
        cursor.execute(block_query, (customer_id, reason, required_payment, block_until))
        
        result = cursor.fetchone()
        conn.commit()
        conn.close()
        
        logger.info(f"Successfully blocked customer {customer_id} for reason: {reason}")
        return bool(result)
    except Exception as e:
        logger.error(f"Error blocking customer: {e}", exc_info=True)
        return False
    

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
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'customer_blocks'
            )
        """
        table_exists = execute_query(check_table_query, fetchone=True)[0]
        
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
        
        result = execute_query(query, (customer_id,), fetchone=True)
        
        if result:
            return True, result[1], result[2], result[3]
        else:
            return False, None, 0, None
    except Exception as e:
        logger.error(f"Error checking customer blocked status: {e}")
        return False, None, 0, None

def update_receipt_verification_status(order_id, is_verified):
    """Update receipt verification status
    
    Args:
        order_id (int): ID of the order
        is_verified (bool or None): Verification status (True, False, or None)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        query = """
            UPDATE order_payments
            SET receipt_verified = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE order_id = %s
            RETURNING id
        """
        
        result = execute_query(query, (is_verified, order_id), fetchone=True, commit=True)
        
        return bool(result)
    except Exception as e:
        logger.error(f"Error updating receipt verification status: {e}")
        return False

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
                updated_at = CURRENT_TIMESTAMP
            WHERE order_id = %s
            RETURNING id
        """
        
        result = execute_query(query, (is_completed, order_id), fetchone=True, commit=True)
        
        return bool(result)
    except Exception as e:
        logger.error(f"Error setting admin payment completed: {e}")
        return False

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
        # Create customer_fine_receipts table if it doesn't exist
        create_table_query = """
            CREATE TABLE IF NOT EXISTS customer_fine_receipts (
                id SERIAL PRIMARY KEY,
                customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
                file_id VARCHAR(255) NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                verified_by INTEGER,
                verified_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        
        execute_query(create_table_query, commit=True)
        
        # Insert receipt record
        query = """
            INSERT INTO customer_fine_receipts 
            (customer_id, file_id, status, created_at)
            VALUES (%s, %s, 'pending', CURRENT_TIMESTAMP)
            RETURNING id
        """
        
        result = execute_query(query, (customer_id, file_id), fetchone=True, commit=True)
        return bool(result)
    except Exception as e:
        logger.error(f"Error saving customer fine receipt: {e}")
        return False
    

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
        SET is_blocked = FALSE, unblocked_at = CURRENT_TIMESTAMP
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
        if conn:
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
        # First check if refunds table exists
        check_table_query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'refund_requests'
            )
        """
        table_exists = execute_query(check_table_query, fetchone=True)[0]
        
        # Create table if it doesn't exist
        if not table_exists:
            create_table_query = """
                CREATE TABLE refund_requests (
                    id SERIAL PRIMARY KEY,
                    order_id INTEGER NOT NULL REFERENCES orders(id),
                    amount NUMERIC(10, 2) NOT NULL,
                    reason TEXT NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    card_number VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_by INTEGER,
                    completed_at TIMESTAMP
                )
            """
            execute_query(create_table_query, commit=True)
        
        # Insert refund request
        query = """
            INSERT INTO refund_requests 
            (order_id, amount, reason, status, created_at)
            VALUES (%s, %s, %s, 'pending', CURRENT_TIMESTAMP)
            RETURNING id
        """
        
        result = execute_query(query, (order_id, amount, reason), fetchone=True, commit=True)
        return result[0] if result else None
    
    except Exception as e:
        logger.error(f"Error creating refund request: {e}", exc_info=True)
        return None

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
        return dict(result) if result else None
    
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
                    update_parts.append(f"{field} = CURRENT_TIMESTAMP")
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
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE order_payments 
            SET admin_payment_completed = TRUE
            WHERE order_id = %s
        """, (order_id,))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"DB error in mark_admin_payment_completed: {e}")
        return False