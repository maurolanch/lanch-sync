from flask import Flask
import requests

app = Flask(__name__)

@app.route('/')
def index():
    return "¡Hola desde GCP!"

@app.route('/get_token')
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
        token = data['data']['app_secret_key'][0]['suc_data'][0]['token']
        return f"Token recibido: {token}"
    else:
        return f"Error {response.status_code}: {response.text}"

if __name__ == '__main__':
    app.run()
