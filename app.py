from flask import Flask
import requests
import threading
import time

app = Flask(__name__)

# Variable global para almacenar el token
current_token = None

# Función para obtener el token
def get_token():
    secret_key = "$2y$10$2cwvoVf4kMCYzakUC9Yfg.LkiKtK77y9szWW7CLBAYcEAQO1xQ/tK"
    url = "https://grupologi.com.co/ApiLogi/principal_graph.php"
    body = {
        "query": f"query {{ app_secret_key(secret_client: \"{secret_key}\") {{ suc_data {{ token }} }} }}"
    }
    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=body, headers=headers)

    if response.status_code == 200:
        data = response.json()
        # Accede correctamente a la estructura de los datos
        global current_token
        current_token = data['data']['app_secret_key'][0]['suc_data'][0]['token']
        print(f"Token renovado: {current_token}")
    else:
        print(f"Error {response.status_code}: {response.text}")

# Función para renovar el token cada 12 horas
def renew_token_periodically():
    while True:
        get_token()  # Llama a la función para renovar el token
        time.sleep(43200)  # Espera 12 horas (43200 segundos)

# Inicia el hilo para renovar el token
@app.before_first_request
def start_token_renewal_thread():
    threading.Thread(target=renew_token_periodically, daemon=True).start()

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
    app.run()
