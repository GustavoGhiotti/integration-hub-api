from twilio.rest import Client
from src.shared.utils.env_load import ACCOUNT_SID, AUTH_TOKEN

def get_twilio_client():
    return Client(ACCOUNT_SID, AUTH_TOKEN)
