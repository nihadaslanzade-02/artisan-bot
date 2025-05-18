# crypto_service.py

import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get encryption key from environment variable or generate one
def get_encryption_key():
    """Get or generate an encryption key"""
    key = os.getenv("ENCRYPTION_KEY")
    
    if not key:
        # Generate a new key directly using Fernet.generate_key()
        key = Fernet.generate_key()
        logger.warning(f"ENCRYPTION_KEY not found in environment, generated a new one")
        logger.warning(f"Generated key: {key.decode()}. Add this to your .env file as ENCRYPTION_KEY")
        return key
    
    try:
        # If the key is a string, encode it
        if isinstance(key, str):
            key = key.encode()
        
        # Test if the key is valid
        Fernet(key)
        return key
    except Exception as e:
        logger.error(f"Invalid encryption key: {e}")
        # Generate a new key if the provided one is invalid
        new_key = Fernet.generate_key()
        logger.warning(f"Generated new key: {new_key.decode()}. Add this to your .env file as ENCRYPTION_KEY")
        return new_key

# Initialize Fernet cipher with our key
_key = get_encryption_key()
try:
    cipher = Fernet(_key)
except Exception as e:
    logger.error(f"Error initializing Fernet cipher: {e}")
    # Generate a new key if there was an error
    _key = Fernet.generate_key()
    cipher = Fernet(_key)

# Encryption functions
def encrypt_data(data):
    """Encrypt sensitive data
    
    Args:
        data (str): Data to encrypt
        
    Returns:
        str: Encrypted data in base64 format
    """
    
    if data is None:
        return None
        
    try:
        # Always cast to string before encoding
        data_str = str(data).encode('utf-8')
        encrypted_data = cipher.encrypt(data_str)
        # Use standard base64 encoding without padding to avoid issues
        encoded = base64.urlsafe_b64encode(encrypted_data).decode('utf-8')
        # Remove any padding at the end (= characters) for consistency
        return encoded.rstrip("=")
    except Exception as e:
        logger.error(f"Error encrypting data: {e}")
        # If encryption fails, return a special marker followed by original data
        return f"FAILED_ENC:{data}"

def decrypt_data(encrypted_data):
    if encrypted_data is None:
        return None
        
    # Check if encryption previously failed
    if isinstance(encrypted_data, str) and encrypted_data.startswith("FAILED_ENC:"):
        return encrypted_data[11:]  # Return original data after the marker
        
    # If data is not a string, return as is
    if not isinstance(encrypted_data, str):
        return encrypted_data
        
    try:
        # First, clean the string from any unsafe characters
        # Sometimes strings can have line breaks or whitespaces
        clean_data = encrypted_data.strip()
        
        # Handle Base64 padding more robustly
        # First try direct decode, then try with padding correction
        try:
            # Try direct decode first
            encrypted_bytes = base64.urlsafe_b64decode(clean_data.encode('utf-8'))
        except Exception as direct_error:
            logger.info(f"Direct base64 decode failed, trying with padding: {str(direct_error)}")
            
            # Calculate required padding
            padding_needed = 4 - (len(clean_data) % 4) if len(clean_data) % 4 else 0
            if padding_needed:
                clean_data += '=' * padding_needed
                
            try:
                encrypted_bytes = base64.urlsafe_b64decode(clean_data.encode('utf-8'))
            except Exception as padding_error:
                logger.error(f"Base64 decoding error even with padding: {str(padding_error)}")
                return encrypted_data
        
        # Decrypt data
        try:
            decrypted_data = cipher.decrypt(encrypted_bytes)
            return decrypted_data.decode('utf-8')
        except Exception as decrypt_error:
            logger.error(f"Cipher decryption error: {str(decrypt_error)}")
            return encrypted_data
    except Exception as e:
        logger.error(f"General decryption error: {str(e)}")
        return encrypted_data

# Masking functions
def mask_name(name):
    """Mask a name, showing only first letters
    
    Args:
        name (str): Full name
        
    Returns:
        str: Masked name (e.g. "John Doe" -> "J*** D**")
    """
    if not name:
        return ""
        
    # Split name into parts
    parts = name.split()
    masked_parts = []
    
    for part in parts:
        if len(part) > 0:
            masked_part = part[0] + "*" * (len(part) - 1)
            masked_parts.append(masked_part)
        else:
            masked_parts.append("")
    
    return " ".join(masked_parts)

def mask_phone(phone):
    """Mask a phone number, showing only the last 4 digits
    
    Args:
        phone (str): Phone number
        
    Returns:
        str: Masked phone number (e.g. "+994501234567" -> "+994xx xxxx 4567")
    """
    if not phone:
        return ""
        
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)
    
    if len(digits) < 4:
        return "*" * len(digits)
        
    # Keep last 4 digits, mask the rest
    masked = "*" * (len(digits) - 4) + digits[-4:]
    
    # Format according to standard phone format
    if len(digits) == 10:  # Standard 10-digit number
        return f"****-***-{masked[-4:]}"
    elif len(digits) == 12 and digits.startswith('994'):  # Azerbaijan format
        return f"+994-**-***-{masked[-4:]}"
    else:
        # Apply a simple formatting if no standard format fits
        return "*" * (len(digits) - 4) + "-" + digits[-4:]

def mask_card_number(card_number):
    """Mask a card number, showing only the last 4 digits
    
    Args:
        card_number (str): Card number
        
    Returns:
        str: Masked card number (e.g. "4169123456781234" -> "4169 **** **** 1234")
    """
    if not card_number:
        return ""
        
    # Remove spaces or other separators
    card = re.sub(r'\D', '', card_number)
    
    if len(card) < 4:
        return "*" * len(card)
        
    # Format with standard credit card spacing and masking
    if len(card) == 16:  # Standard credit card
        return f"{card[:4]} **** **** {card[-4:]}"
    else:
        # Simple masking for non-standard length
        return "*" * (len(card) - 4) + card[-4:]

def mask_telegram_id(telegram_id):
    """Mask a Telegram ID, showing only the last 3 digits
    
    Args:
        telegram_id (int or str): Telegram ID
        
    Returns:
        str: Masked Telegram ID (e.g. "123456789" -> "******789")
    """
    if telegram_id is None:
        return ""
        
    # Convert to string
    tid = str(telegram_id)
    
    if len(tid) < 3:
        return "*" * len(tid)
        
    # Mask all except the last 3 digits
    return "*" * (len(tid) - 3) + tid[-3:]

# Function to determine if a field should be encrypted
def should_encrypt_field(field_name):
    """Determine if a field should be encrypted
    
    Args:
        field_name (str): Name of the field
        
    Returns:
        bool: True if the field should be encrypted
    """
    # List of field names that should be encrypted
    sensitive_fields = [
        'name', 'phone', 'card_number', 'card_holder', 'telegram_id',
        'customer_name', 'artisan_name', 'customer_phone', 'artisan_phone'
    ]
    
    return field_name in sensitive_fields

def normalize_encrypted_data(encrypted_data):
    """Normalize encrypted data by decrypting and re-encrypting it
    
    Args:
        encrypted_data (str): Encrypted data to normalize
        
    Returns:
        str: Re-encrypted data with consistent formatting
    """
    if encrypted_data is None:
        return None
        
    # Skip already failed data
    if isinstance(encrypted_data, str) and encrypted_data.startswith("FAILED_ENC:"):
        return encrypted_data
    
    try:
        # Try to decrypt the data
        decrypted = decrypt_data(encrypted_data)
        
        # Re-encrypt the data for consistency
        if decrypted == encrypted_data:
            # If decryption didn't actually work, return original
            return encrypted_data
        else:
            # Otherwise, re-encrypt with consistent format
            return encrypt_data(decrypted)
    except Exception as e:
        logger.error(f"Error normalizing encrypted data: {e}")
        return encrypted_data