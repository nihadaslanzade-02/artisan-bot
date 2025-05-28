# db_encryption_wrapper.py

from crypto_service import (
    encrypt_data, decrypt_data, mask_name, mask_phone,
    mask_card_number, mask_telegram_id, should_encrypt_field
)
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Wrap database operations with encryption/decryption functionality

def encrypt_dict_data(data_dict):
    """Encrypt sensitive fields in a dictionary
    
    Args:
        data_dict (dict): Dictionary with data to encrypt
        
    Returns:
        dict: Dictionary with encrypted sensitive data
    """
    if not isinstance(data_dict, dict):
        return data_dict
        
    encrypted_dict = {}
    
    for key, value in data_dict.items():
        if should_encrypt_field(key) and value is not None:
            encrypted_dict[key] = encrypt_data(value)
        else:
            encrypted_dict[key] = value
            
    return encrypted_dict

def decrypt_dict_data(data_dict, mask=False):
    """Decrypt sensitive fields in a dictionary
    
    Args:
        data_dict (dict): Dictionary with encrypted data
        mask (bool): Whether to mask sensitive data after decryption
        
    Returns:
        dict: Dictionary with decrypted data
    """
    if not isinstance(data_dict, dict):
        return data_dict
        
    decrypted_dict = {}
    
    for key, value in data_dict.items():
        if should_encrypt_field(key) and value is not None:
            try:
                # Try to decrypt the value
                decrypted_value = decrypt_data(value)
                
                # Apply masking if requested
                if mask:
                    try:
                        if key == 'name' or key.endswith('_name'):
                            decrypted_dict[key] = mask_name(decrypted_value)
                        elif key == 'phone' or key.endswith('_phone'):
                            decrypted_dict[key] = mask_phone(decrypted_value)
                        elif key == 'card_number':
                            decrypted_dict[key] = mask_card_number(decrypted_value)
                        elif key == 'telegram_id':
                            decrypted_dict[key] = mask_telegram_id(decrypted_value)
                        else:
                            decrypted_dict[key] = decrypted_value
                    except Exception as mask_error:
                        # If masking fails, just use the decrypted value
                        logger.error(f"Error masking field {key}: {mask_error}")
                        decrypted_dict[key] = decrypted_value
                else:
                    decrypted_dict[key] = decrypted_value
            except Exception as e:
                logger.error(f"Error decrypting field {key}: {e}")
                # Handle different error cases
                if isinstance(value, str):
                    if len(value) % 4 == 1:
                        logger.warning(f"Likely Base64 padding issue with field {key}. Length: {len(value)}")
                    elif "=" in value:
                        logger.warning(f"Field {key} has padding characters which should be stripped")
                
                # If decryption fails, keep the original value
                decrypted_dict[key] = value
        else:
            decrypted_dict[key] = value
            
    return decrypted_dict

def decrypt_list_data(data_list, mask=False):
    """Decrypt sensitive data in a list of dictionaries
    
    Args:
        data_list (list): List of dictionaries with encrypted data
        mask (bool): Whether to mask sensitive data after decryption
        
    Returns:
        list: List of dictionaries with decrypted data
    """
    if not isinstance(data_list, list):
        return data_list
        
    return [decrypt_dict_data(item, mask) for item in data_list]

# Wrapper functions for database operations

def wrap_create_customer(original_func):
    """Wrap create_customer function to encrypt sensitive data"""
    def wrapper(telegram_id, name, phone=None):
        # Artıq db.py-də encrypt olunur, burada birbaşa orijinal funksiyanı çağır
        return original_func(telegram_id, name, phone)
    return wrapper

def wrap_create_artisan(original_func):
    """Wrap create_artisan function to encrypt sensitive data"""
    def wrapper(telegram_id, name, phone, service, location=None, city=None, latitude=None, longitude=None):
        # Encrypt sensitive data
        encrypted_name = encrypt_data(name)
        encrypted_phone = encrypt_data(phone)
        
        # Call original function with encrypted data
        return original_func(telegram_id, encrypted_name, encrypted_phone, service, location, city, latitude, longitude)
    return wrapper

def wrap_get_dict_function(original_func, decrypt=True, mask=False):
    """Wrap functions that return a dictionary to decrypt sensitive data
    
    Args:
        original_func: Original function
        decrypt (bool): Whether to decrypt data
        mask (bool): Whether to mask sensitive data after decryption
    """
    def wrapper(*args, **kwargs):
        result = original_func(*args, **kwargs)
        
        if not result or not decrypt:
            return result
            
        return decrypt_dict_data(result, mask)
    return wrapper

def wrap_get_list_function(original_func, decrypt=True, mask=False):
    """Wrap functions that return a list of dictionaries to decrypt sensitive data
    
    Args:
        original_func: Original function
        decrypt (bool): Whether to decrypt data
        mask (bool): Whether to mask sensitive data after decryption
    """
    def wrapper(*args, **kwargs):
        result = original_func(*args, **kwargs)
        
        if not result or not decrypt:
            return result
            
        return decrypt_list_data(result, mask)
    return wrapper

def wrap_update_customer_profile(original_func):
    """Wrap update_customer_profile function to encrypt sensitive data"""
    def wrapper(telegram_id, data):
        # Encrypt sensitive data in the update data
        encrypted_data = encrypt_dict_data(data)
        
        # Call original function with encrypted data
        return original_func(telegram_id, encrypted_data)
    return wrapper

def wrap_update_artisan_profile(original_func):
    """Wrap update_artisan_profile function to encrypt sensitive data"""
    def wrapper(artisan_id, data):
        # Encrypt sensitive data in the update data
        encrypted_data = encrypt_dict_data(data)
        
        # Call original function with encrypted data
        return original_func(artisan_id, encrypted_data)
    return wrapper

def wrap_save_payment_receipt(original_func):
    """Wrap save_payment_receipt function for card data"""
    def wrapper(order_id, file_id):
        # The original function doesn't store sensitive payment data directly
        # but may be used in relation to payment processing
        return original_func(order_id, file_id)
    return wrapper