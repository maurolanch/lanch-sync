import webbrowser
import subprocess
import requests
import json
import os
from flask import Flask, request, jsonify
from settings import CREDENTIALS  # Aseg


app = Flask(__name__)

TOKEN_FILE = "config/tokens.json"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"

def load_tokens():
    """Carga los tokens desde el archivo JSON"""
    if not os.path.exists(TOKEN_FILE):
        raise FileNotFoundError(f"El archivo {TOKEN_FILE} no existe. Debes autenticar primero.")

    with open(TOKEN_FILE, "r") as file:
        try:
            tokens = json.load(file)
            if not tokens:
                raise ValueError("El archivo de tokens está vacío.")
            return tokens
        except json.JSONDecodeError:
            raise ValueError(f"El archivo {TOKEN_FILE} no tiene un formato JSON válido.")

def save_tokens(cuenta, tokens):
    """Guarda los tokens en un archivo JSON."""
    try:
        with open(TOKEN_FILE, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    data[cuenta] = tokens

    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f, indent=4)

def refresh_token(cuenta):
    """Renueva el access_token usando el refresh_token guardado."""
    try:
        with open(TOKEN_FILE, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

    if cuenta not in data:
        return None

    refresh_token = data[cuenta].get("refresh_token")
    if not refresh_token:
        return None

    creds = CREDENTIALS[cuenta]

    payload = {
        "grant_type": "refresh_token",
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": refresh_token,
    }

    response = requests.post(TOKEN_URL, data=payload)
    if response.status_code == 200:
        new_tokens = response.json()
        save_tokens(cuenta, new_tokens)
        return new_tokens
    else:
        return None
    
def get_user_info(cuenta):
    """Obtiene información del usuario autenticado en MercadoLibre."""
    try:
        with open(TOKEN_FILE, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

    if cuenta not in data:
        return None

    access_token = data[cuenta].get("access_token")
    if not access_token:
        return None

    url = "https://api.mercadolibre.com/users/me"
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.get(url, headers=headers)
    return response.json()

@app.route("/auth", methods=["GET"])
def auth():
    cuenta = request.args.get("cuenta")
    
    if cuenta not in CREDENTIALS:
        return jsonify({"error": "Cuenta no encontrada"}), 404

    client_id = CREDENTIALS[cuenta]["client_id"]
    redirect_uri = CREDENTIALS[cuenta]["redirect_uri"]
    
    auth_url = f"https://auth.mercadolibre.com/authorization?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}"
    
    # Abre la URL en modo incógnito (Chrome como ejemplo)
    try:
        subprocess.run(["open", "-na", "Google Chrome", "--args", "--incognito", auth_url])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"message": f"Abriendo {auth_url} en modo incógnito"})



@app.route("/callback/<cuenta>")
def callback(cuenta):
    """Recibe el código de autorización y solicita tokens."""
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Código de autorización no recibido"}), 400

    if cuenta not in CREDENTIALS:
        return jsonify({"error": "Cuenta no configurada"}), 400

    creds = CREDENTIALS[cuenta]
    
    payload = {
        "grant_type": "authorization_code",
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "code": code,
        "redirect_uri": creds["redirect_uri"],
    }

    response = requests.post(TOKEN_URL, data=payload)
    if response.status_code == 200:
        tokens = response.json()
        save_tokens(cuenta, tokens)
        return jsonify({"message": "Tokens guardados correctamente", "tokens": tokens})
    else:
        return jsonify({"error": "Error al obtener tokens", "details": response.json()}), response.status_code



if __name__ == "__main__":
    app.run(debug=True)
