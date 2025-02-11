import os
from dotenv import load_dotenv

# Cargar variables de entorno desde config/.env
dotenv_path = os.path.join(os.path.dirname(__file__), "config/.env")
load_dotenv(dotenv_path)

# Credenciales de MercadoLibre
CREDENTIALS = {
    "cuenta1": {
        "client_id": os.getenv("ML_CLIENT_ID_CUENTA1"),
        "client_secret": os.getenv("ML_CLIENT_SECRET_CUENTA1"),
        "redirect_uri": os.getenv("ML_REDIRECT_URI_CUENTA1"),
    },
    "cuenta2": {
        "client_id": os.getenv("ML_CLIENT_ID_CUENTA2"),
        "client_secret": os.getenv("ML_CLIENT_SECRET_CUENTA2"),
        "redirect_uri": os.getenv("ML_REDIRECT_URI_CUENTA2"),
    }
}