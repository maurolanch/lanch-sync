from flask import Flask
import json
import requests
import threading
import time
from google.cloud import secretmanager
import os
# Instancia de Flask
app = Flask(__name__)

# Variable global para el token
current_token = None

# Establecer la ruta a tus credenciales de Google Cloud
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "config/lanch-sync-e5d12969c196.json"

# Configuración del proyecto y secreto
project_id = "lanch-sync"
secret_id = "API_SECRET_KEY"



# Función para obtener el secreto desde Google Secret Manager
def get_secret(project_id, secret_id, version_id="latest"):
    try:
        # Crear cliente de Secret Manager
        client = secretmanager.SecretManagerServiceClient()

        # Construir la ruta del recurso del secreto
        secret_path = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"

        # Acceder al secreto
        response = client.access_secret_version(name=secret_path)
        secret_value = response.payload.data.decode("UTF-8")
        return secret_value
    except Exception as e:
        print(f"Error al obtener el secreto: {e}")
        return None


# Función para obtener el token usando el secreto
def get_token(project_id, secret_id):
    global current_token  # Declarar que estamos utilizando la variable global
    # Obtener el secreto desde Google Secret Manager
    secret_key = get_secret(project_id, secret_id)

    secret_key = secret_key.strip()

    if not secret_key:
        print("Error: No se pudo obtener el secreto. No se puede continuar.")
        return

    # Construir el query para obtener el token

    query = {"query": '{app_secret_key(secret_client:"' + secret_key + '"){suc_data{token}}}'}
   
    url = "https://grupologi.com.co/ApiLogi/principal_graph.php"
    body = json.dumps(query)
    #body = query
    headers = {
    'Content-Type': 'application/json'
    }

    # Realizar la solicitud HTTP
    try:
        response = requests.post(url, data=body, headers=headers)
        response.raise_for_status()
        if response.status_code == 200:
            data = response.json()

            # Extraer token si está presente
            if "data" in data and "app_secret_key" in data["data"]:
                current_token = data["data"]["app_secret_key"][0]["suc_data"][0]["token"]
                print(f"Token renovado: {current_token}")
                return current_token
            else:
                print("Error: La respuesta no contiene datos esperados.")
        else:
            print(f"Error {response.status_code}: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Error al realizar la solicitud: {e}")

# Llamar a la función para obtener el token
get_token(project_id, secret_id)



# Función para renovar el token cada 12 horas
def renew_token_periodically():
    while True:
        get_token(project_id, secret_id)  # Llama a la función para renovar el token
        time.sleep(43200)  # Espera 12 horas (43200 segundos)

@app.route('/')
def index():
    return "¡Hola desde GCP!"

@app.route('/get_token')
def get_token_route():
    if current_token:
        return f"Token actual: {current_token}"
    else:
        return "Token aún no disponible"

if __name__ == '__main__':
    # Inicia el hilo para renovar el token
    threading.Thread(target=renew_token_periodically, daemon=True).start()
    app.run()

