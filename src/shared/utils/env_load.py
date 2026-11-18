from dotenv import load_dotenv
import os

load_dotenv()



def get_env_required(name: str) -> str:
    value = os.getenv(name)

    if value is None or value.strip() == "":
        raise RuntimeError(f"Variável de ambiente obrigatória não encontrada: {name}")

    return value


# Banco
DB_USER   = os.getenv("DB_USER")
DB_PASS   = os.getenv("DB_PASSWORD")
TOKEN_DB_API = os.getenv("TOKEN_DB_API")
TOKEN_KEY = os.getenv("TOKEN_KEY")

# Servidores
DB_71  = os.getenv("DB_71")
DB_72  = os.getenv("DB_72")
DB_66  = os.getenv("DB_66")
DB_65  = os.getenv("DB_65")
DB_248 = os.getenv("DB_248")
DB_170 = os.getenv("DB_170")

# SendGrid
SENDGRID_API_KEY  = os.getenv("SENDGRID_API_KEY")
SENDGRID_BASE_URL = os.getenv("SENDGRID_BASE_URL", "https://api.sendgrid.com/v3")

#ActiveDirectory
AD_USER   = os.getenv("AD_USER")
AD_PASS   = os.getenv("AD_PASS")
AD_SERVER = os.getenv("AD_SERVER")

#Chave de Token
JWT_SECRET = os.getenv("JWT_SECRET")

#Twilio
ACCOUNT_SID = os.getenv("ACCOUNT_SID")
AUTH_TOKEN = os.getenv("AUTH_TOKEN")


SMB_USER = os.getenv("SMB_USER")
SMB_PASS = os.getenv("SMB_PASS")
SMB_DOMINIO = os.getenv("SMB_DOMINIO")

# Meta / WhatsApp templates
WHATSAPP_META_WABA_ID = os.getenv("WHATSAPP_META_WABA_ID")
WHATSAPP_META_ACCESS_TOKEN = os.getenv("WHATSAPP_META_ACCESS_TOKEN")
WHATSAPP_META_API_VERSION = os.getenv("WHATSAPP_META_API_VERSION", "v20.0")

# Infobip
INFOBIP_BASE_URL = os.getenv("INFOBIP_BASE_URL")
INFOBIP_API_KEY = os.getenv("INFOBIP_API_KEY")
INFOBIP_AUTH_TYPE = os.getenv("INFOBIP_AUTH_TYPE")
INFOBIP_WHATSAPP_ENDPOINT = os.getenv("INFOBIP_WHATSAPP_ENDPOINT")

# VCOM
VCOM_BASE_URL = os.getenv("VCOM_BASE_URL")
VCOM_USUARIO = os.getenv("VCOM_USUARIO")
VCOM_SENHA = os.getenv("VCOM_SENHA")
VCOM_TENANT = os.getenv("VCOM_TENANT")

# Meta / Copilot webhook proxy
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN")
META_APP_SECRET = os.getenv("META_APP_SECRET")
COPILOT_META_WEBHOOK_URL = os.getenv("COPILOT_META_WEBHOOK_URL")
COPILOT_META_WEBHOOK_TOKEN = os.getenv("COPILOT_META_WEBHOOK_TOKEN")
API_SISTEMA_ACME_INTERNAL_TOKEN = os.getenv("API_SISTEMA_ACME_INTERNAL_TOKEN")

class Settings:
    PLAYWRIGHT_TIMEOUT = 40_000
    PLAYWRIGHT_HEADLESS = True

    EASYCOLLECTOR_LOGIN_URL = "http://10.0.0.64/easycollector/login.aspx"
    EASYCOLLECTOR_BASE_URL = "http://10.0.0.64/easycollector"


    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    SCREENSHOT_DIR = os.path.join(BASE_DIR, "data", "prints")



TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
EASYCOLLECTOR_USER = os.getenv("EASYCOLLECTOR_USER")
EASYCOLLECTOR_PASSWORD = os.getenv("EASYCOLLECTOR_PASSWORD")
TELEGRAM_ALLOWED_CHAT_ID = os.getenv("TELEGRAM_ALLOWED_CHAT_ID")
