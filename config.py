#!/usr/bin/env python
"""
Configuration settings for the Artisan Booking Bot.
"""

import os
from dotenv import load_dotenv

# .env faylını yüklə
load_dotenv()

# Telegram Bot Token (Get from BotFather)
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Database Connection Parameters
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "port": int(os.getenv("DB_PORT"))
}

# Google Maps API for Reverse Geocoding (Optional)
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# Commission Rates (in percentage)
# Used for calculating admin fee on orders
COMMISSION_RATES = {
    "low": {  # 0-50 AZN
        "threshold": 50,
        "rate": 12
    },
    "medium": {  # 50-200 AZN
        "threshold": 200,
        "rate": 16  # Updated from 15% to 16% as requested
    },
    "high": {  # 200+ AZN
        "threshold": float('inf'),
        "rate": 20
    }
}

# Payment Settings
ADMIN_CARD_NUMBER = "4098 5844 9700 2863"  # Card number for cash payment commission transfer
ADMIN_CARD_HOLDER = "Nihad Aslanzade"  # Card holder name
PAYMENT_WAIT_TIME_HOURS = 24  # Hours to wait for commission payment
BLOCK_AFTER_HOURS = 30  # Hours after which to block artisan for non-payment
FINE_PERCENTAGE = 15  # Additional fine percentage for late payments
UNBLOCK_PAYMENT_PERCENTAGE = 50  # Percentage of total amount needed to unblock account

# Bot Settings
DEFAULT_LANGUAGE = "az"  # Azerbaijani
BOT_ADMINS = [1246396928]  # Telegram User IDs of admins

# Support Contact Information
SUPPORT_EMAIL = "techrep.support@gmail.com"
SUPPORT_PHONE = "+994506606351"  # Support contact phone

# Location Settings
DEFAULT_SEARCH_RADIUS = 10  # km - Default radius for searching nearby artisans
MAX_SEARCH_RADIUS = 50  # km - Maximum allowed search radius

# Time Settings
TIME_SLOTS_START_HOUR = 1  
TIME_SLOTS_END_HOUR = 24
TIME_SLOT_INTERVAL = 10  # minutes - Interval between time slots

# User Experience Settings
MAX_NEARBY_ARTISANS = 10  # Maximum number of nearby artisans to display
ARTISAN_MIN_RATING = 0  # Minimum rating for artisans to be shown in search
DAYS_AHEAD_BOOKING = 3  # How many days ahead users can book services

# Registration Settings
PHONE_VALIDATION_REGEX = r'^\+?994\d{9}$|^0\d{9}$'  # Regex pattern for valid Azerbaijani phone numbers
MIN_NAME_LENGTH = 2  # Minimum length for user names
MAX_NAME_LENGTH = 50  # Maximum length for user names

# Debug Settings
DEBUG_MODE = True  # Enable/disable debug mode
LOG_LEVEL = "INFO"  # Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL