import datetime
from typing import List, Dict, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Month names in Azerbaijani
AZ_MONTH_NAMES = {
    1: "Yanvar",
    2: "Fevral",
    3: "Mart",
    4: "Aprel",
    5: "May",
    6: "İyun",
    7: "İyul",
    8: "Avqust",
    9: "Sentyabr",
    10: "Oktyabr",
    11: "Noyabr",
    12: "Dekabr"
}

# Day names in Azerbaijani
AZ_DAY_NAMES = {
    0: "Bazar ertəsi",
    1: "Çərşənbə axşamı",
    2: "Çərşənbə",
    3: "Cümə axşamı",
    4: "Cümə",
    5: "Şənbə",
    6: "Bazar"
}

def get_date_keyboard(days_ahead: int = 3) -> InlineKeyboardMarkup:
    """
    Create a keyboard with date options for the next N days.
    
    Args:
        days_ahead (int): Number of days to include in the options
        
    Returns:
        InlineKeyboardMarkup: Keyboard with date buttons
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    for i in range(days_ahead):
        date = today + datetime.timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        
        # Format the display text
        if i == 0:
            display_text = "Bu gün"
        elif i == 1:
            display_text = "Sabah"
        else:
            weekday = AZ_DAY_NAMES[date.weekday()]
            day = date.day
            month = AZ_MONTH_NAMES[date.month]
            display_text = f"{day} {month}, {weekday}"
        
        keyboard.add(InlineKeyboardButton(display_text, callback_data=f"date_{date_str}"))
    
    return keyboard

def get_time_keyboard(
    start_hour: int = 8, 
    end_hour: int = 23,
    interval_mins: int = 10  
) -> InlineKeyboardMarkup:
    """
    Create a keyboard with time slot options.
    
    Args:
        start_hour (int): Starting hour (24-hour format)
        end_hour (int): Ending hour (24-hour format)
        interval_mins (int): Interval between time slots in minutes
        
    Returns:
        InlineKeyboardMarkup: Keyboard with time slot buttons
    """
    # config'den değerleri al
    from config import TIME_SLOTS_START_HOUR, TIME_SLOTS_END_HOUR, TIME_SLOT_INTERVAL
    
    # Default değerleri config değerleriyle değiştir
    start_hour = TIME_SLOTS_START_HOUR if start_hour == 8 else start_hour
    end_hour = TIME_SLOTS_END_HOUR if end_hour == 23 else end_hour
    
    # 24 saati işlemək üçün düzəltmə
    if end_hour == 23:
        end_hour = 23
        include_midnight = True
    else:
        include_midnight = False
        
    interval_mins = TIME_SLOT_INTERVAL if interval_mins == 10 else interval_mins
    
    keyboard = InlineKeyboardMarkup(row_width=3)
    buttons = []
    
    current_time = datetime.datetime.now().replace(
        hour=start_hour, minute=0, second=0, microsecond=0
    )
    end_time = datetime.datetime.now().replace(
        hour=end_hour, minute=59, second=59, microsecond=999999
    )
    
    while current_time <= end_time:
        time_str = current_time.strftime("%H:%M")
        buttons.append(InlineKeyboardButton(time_str, callback_data=f"time_{time_str}"))
        current_time += datetime.timedelta(minutes=interval_mins)
    
    # Gecəyarısını əlavə et (əgər lazımdırsa)
    if include_midnight:
        buttons.append(InlineKeyboardButton("00:00", callback_data="time_00:00"))
    
    # Add buttons to keyboard in rows
    keyboard.add(*buttons)
    
    return keyboard

def format_datetime(date_str: str, time_str: str) -> str:
    """
    Format date and time strings into a human-readable format in Azerbaijani.
    
    Args:
        date_str (str): Date in format "YYYY-MM-DD"
        time_str (str): Time in format "HH:MM"
        
    Returns:
        str: Formatted date and time string
    """
    try:
        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        
        day = date_obj.day
        month = AZ_MONTH_NAMES[date_obj.month]
        weekday = AZ_DAY_NAMES[date_obj.weekday()]
        
        return f"{day} {month}, {weekday}, saat {time_str}"
    except ValueError:
        # Return the original strings if parsing fails
        return f"{date_str}, {time_str}"

def get_available_time_slots(
    date_str: str, 
    booked_slots: List[str],
    start_hour: int = 8,
    end_hour: int = 23, 
    interval_mins: int = 10  
) -> List[str]:
    """
    Get available time slots for a specific date, excluding already booked slots.
    
    Args:
        date_str (str): Date in format "YYYY-MM-DD"
        booked_slots (List[str]): List of already booked time slots in format "HH:MM"
        start_hour (int): Starting hour (24-hour format)
        end_hour (int): Ending hour (24-hour format)
        interval_mins (int): Interval between time slots in minutes
        
    Returns:
        List[str]: List of available time slots
    """
    # config'den değerleri al
    from config import TIME_SLOTS_START_HOUR, TIME_SLOTS_END_HOUR, TIME_SLOT_INTERVAL
    
    # Default değerleri config değerleriyle değiştir
    start_hour = TIME_SLOTS_START_HOUR if start_hour == 8 else start_hour
    end_hour = TIME_SLOTS_END_HOUR if end_hour == 23 else end_hour
    
    # 24 saati işlemək üçün düzəltmə
    if end_hour == 23:
        end_hour = 23
        include_midnight = True
    else:
        include_midnight = False
        
    interval_mins = TIME_SLOT_INTERVAL if interval_mins ==10 else interval_mins
    
    # Generate all possible time slots
    all_slots = []
    
    current_time = datetime.datetime.strptime(f"{date_str} {start_hour}:00", "%Y-%m-%d %H:%M")
    end_time = datetime.datetime.strptime(f"{date_str} {end_hour}:59", "%Y-%m-%d %H:%M")
    
    while current_time <= end_time:
        all_slots.append(current_time.strftime("%H:%M"))
        current_time += datetime.timedelta(minutes=interval_mins)
        
    # Gecəyarısını əlavə et (əgər lazımdırsa)
    if include_midnight:
        all_slots.append("00:00")
    
    # Remove booked slots
    available_slots = [slot for slot in all_slots if slot not in booked_slots]
    
    return available_slots

def get_time_slots_keyboard(
    date_str: str, 
    booked_slots: List[str] = None,
    start_hour: int = 8,
    end_hour: int = 23, 
    interval_mins: int = 10
) -> InlineKeyboardMarkup:
    """Create a keyboard with available time slots for a specific date."""
    keyboard = InlineKeyboardMarkup(row_width=3)
    
    if booked_slots is None:
        booked_slots = []
    
    # Get values from config
    from config import TIME_SLOTS_START_HOUR, TIME_SLOTS_END_HOUR, TIME_SLOT_INTERVAL
    
    # Set default values with config values
    start_hour = TIME_SLOTS_START_HOUR if start_hour == 8 else start_hour
    end_hour = TIME_SLOTS_END_HOUR if end_hour == 23 else end_hour
    
    # 24 saati işlemək üçün düzəltmə
    if end_hour == 23:
        end_hour = 23
        include_midnight = True
    else:
        include_midnight = False
        
    interval_mins = TIME_SLOT_INTERVAL if interval_mins == 10 else interval_mins
    
    # Check if selected date is today
    import datetime  # Önce modülü import et
    today = datetime.datetime.now().strftime("%Y-%m-%d")  # datetime.datetime.now() kullan
    is_today = (date_str == today)
    
    # For today, we need to adjust start time to ensure it's in the future
    if is_today:
        current_time = datetime.datetime.now()  # datetime.datetime.now() kullan
        current_hour = current_time.hour
        current_minute = current_time.minute
        
        # Add buffer (e.g., 30 minutes)
        buffer_minutes = 30
        
        # Calculate start time with buffer
        buffer_time = current_time + datetime.timedelta(minutes=buffer_minutes)
        buffer_hour = buffer_time.hour
        buffer_minute = buffer_time.minute
        
        # Adjust start hour if needed
        if buffer_hour > start_hour or (buffer_hour == start_hour and buffer_minute > 0):
            start_hour = buffer_hour
            
            # Round to next interval
            if buffer_minute > 0:
                rounded_minute = ((buffer_minute // interval_mins) + 1) * interval_mins
                if rounded_minute >= 60:
                    start_hour += 1
                    rounded_minute = 0
            else:
                rounded_minute = 0
                
            # Update start minutes for first slot
            start_minute = rounded_minute
        else:
            start_minute = 0
    else:
        start_minute = 0
    
    available_slots = get_available_time_slots(
        date_str, booked_slots, start_hour, end_hour, interval_mins
    )
    
    # Gecəyarısını əlavə etmək (əgər lazımdırsa)
    if include_midnight and not is_today:
        if "00:00" not in available_slots and "00:00" not in booked_slots:
            available_slots.append("00:00")
    
    # Filter out past times for today
    if is_today:
        current_time = datetime.datetime.now()  # datetime.datetime.now() kullan
        available_slots = [
            slot for slot in available_slots 
            if datetime.datetime.strptime(f"{date_str} {slot}", "%Y-%m-%d %H:%M") > current_time + datetime.timedelta(minutes=buffer_minutes)
        ]
    
    # If no available slots for today, provide user feedback
    if is_today and not available_slots:
        # No slots available - we'll handle this message in the calling function
        pass
    
    # Sort slots chronologically
    available_slots.sort(key=lambda x: (int(x.split(':')[0]), int(x.split(':')[1])))
    
    buttons = [
        InlineKeyboardButton(slot, callback_data=f"time_{slot}")
        for slot in available_slots
    ]
    
    # Add buttons to keyboard in rows
    keyboard.add(*buttons)
    
    # Add back button
    keyboard.add(InlineKeyboardButton("🔙 Geri", callback_data="back_to_date"))
    
    return keyboard, bool(available_slots)  # Return keyboard and availability flag

def is_time_available(date_str: str, time_str: str, booked_datetime_list: List[str]) -> bool:
    """
    Check if a specific date and time is available.
    
    Args:
        date_str (str): Date in format "YYYY-MM-DD"
        time_str (str): Time in format "HH:MM"
        booked_datetime_list (List[str]): List of booked datetimes in format "YYYY-MM-DD HH:MM"
        
    Returns:
        bool: True if the time slot is available, False otherwise
    """
    datetime_str = f"{date_str} {time_str}"
    return datetime_str not in booked_datetime_list