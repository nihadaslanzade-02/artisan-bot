# states/artisan_registration.py

from aiogram.dispatcher.filters.state import State, StatesGroup

class ArtisanRegistration(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_service = State()
    waiting_for_location = State()