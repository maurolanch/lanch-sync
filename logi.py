import json
import os
import threading
import time
import logging
from datetime import datetime

from flask import Flask, jsonify, make_response
import requests
from google.cloud import secretmanager
from barcode import EAN13
from barcode.errors import IllegalCharacterError

# Configuración de logging (más concisa)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# Variables globales (simplificadas)
current_token = None
token_thread = None  # Para controlar el hilo del token

# Configuración de Secret Manager
PROJECT_ID = "lanch-sync"  # Constante para el ID del proyecto
SECRET_ID = "API_SECRET_KEY"  # Constante para el ID del secreto
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "config/lanch-sync-e5d12969c196.json"

API_URL = "https://grupologi.com.co/ApiLogi/principal_graph.php"  # URL de la API (constante)

# --- Funciones ---

def get_secret(project_id, secret_id):
    """Obtiene el secreto desde Google Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    secret_path = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    try:
        response = client.access_secret_version(name=secret_path)
        return response.payload.data.decode("UTF-8").strip()  # Decodifica y elimina espacios en blanco
    except Exception as e:
        logging.error(f"Error al obtener el secreto: {e}")
        return None

def get_token():
    """Obtiene y actualiza el token."""
    global current_token
    secret_key = get_secret(PROJECT_ID, SECRET_ID)
    if not secret_key:
        logging.error("No se pudo obtener el secreto.")
        return None

    query = {"query": f'{{app_secret_key(secret_client:"{secret_key}"){{suc_data{{token}}}}}}'}
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(API_URL, json=query, headers=headers)
        response.raise_for_status()  # Lanza excepción para errores HTTP
        data = response.json()

        token_data = data.get("data", {}).get("app_secret_key", [])
        if token_data:
            current_token = token_data[0].get("suc_data", [])[0].get("token")
            logging.info("Token renovado.")
            return current_token
        else:
            logging.error("Respuesta de token inesperada.")
            return None

    except requests.exceptions.RequestException as e:
        logging.error(f"Error al obtener el token: {e}")
        return None

def obtener_inventario():
    """Obtiene el inventario desde la API."""
    query = {
        "query": """
        {
          stock {
            producto {
              pro_cod
              pro_sku
              pro_desc
              pro_ubicacion
              pro_fech_registro
            }
            total_stock {
              total_stock
            }
          }
        }
        """
    }
    headers = {'Content-Type': 'application/json', 'Authorization': current_token}

    try:
        response = requests.post(API_URL, data=json.dumps(query), headers=headers)
        response.raise_for_status()
        data = response.json()

        # Validación simplificada (se asume estructura consistente)
        stock_data = data.get("data", {}).get("stock", [])
        if not stock_data:
            logging.warning("No se encontraron datos de inventario.")
            return None

        return data  # Devuelve los datos sin procesar, el procesamiento se hace en otro lugar

    except requests.exceptions.RequestException as e:
        logging.error(f"Error al obtener el inventario: {e}")
        return None

def validar_codigo_barras(codigo):
    """Valida si un código de barras es EAN-13 o UPC."""
    try:
        if len(codigo) == 13:
            EAN13(codigo)
            return True
        elif len(codigo) == 12:
            EAN13("0" + codigo)  # Intenta extender UPC a EAN-13
            return True
        return False
    except IllegalCharacterError:
        return False
    except ValueError:
        return False

def decode_and_format(data):
    """Decodifica y formatea los datos del inventario."""

    if not data or not isinstance(data, dict) or not data.get("data") or not data["data"].get("stock"):
        logging.error("Datos de inventario inválidos.")
        return None

    productos_formateados = []
    for stock_item in data["data"]["stock"]:
        for producto in stock_item.get("producto", []):
            try:  # Bloque try para cada producto
                pro_cod = producto.get("pro_cod", "").strip()
                pro_sku = producto.get("pro_sku", "").strip()
                pro_desc = producto.get("pro_desc", "").strip()
                pro_ubicacion = producto.get("pro_ubicacion", "").strip()
                pro_fech_registro = producto.get("pro_fech_registro", "").strip()

                pro_cod_int = int(pro_cod) if pro_cod.isdigit() else None  # Intenta convertir a int
                codigo_valido = validar_codigo_barras(pro_cod) if pro_cod_int is not None else False

                try:
                    pro_fech_registro_timestamp = datetime.strptime(pro_fech_registro, "%Y-%m-%d %H:%M:%S").timestamp()
                except ValueError:
                    logging.warning(f"Fecha inválida: {pro_fech_registro}")
                    pro_fech_registro_timestamp = None

                total_stock_value = 0
                total_stock_list = stock_item.get("total_stock", [])

                if total_stock_list and isinstance(total_stock_list[0], dict):
                    total_stock_value = int(total_stock_list[0].get("total_stock", 0))

                productos_formateados.append({
                    "pro_cod": pro_cod,
                    "pro_cod_int": pro_cod_int,
                    "pro_cod_valido": codigo_valido,
                    "pro_sku": pro_sku,
                    "pro_desc": pro_desc,
                    "pro_ubicacion": pro_ubicacion,
                    "pro_fech_registro": pro_fech_registro_timestamp,
                    "total_stock": total_stock_value
                })

            except (ValueError, TypeError) as e:  # Captura errores de conversión o tipo de dato
                logging.error(f"Error al procesar producto: {producto}. Error: {e}")

    return productos_formateados

def renew_token_periodically():
    """Renueva el token periódicamente."""
    while True:
        get_token()
        time.sleep(43200)  # 12 horas

# --- Rutas de Flask ---
@app.route('/stock')
def mostrar_stock():
    """Muestra el stock en formato JSON."""
    try:
        data = obtener_inventario()
        if not data:
            return "Error al obtener el inventario."

        productos_formateados = decode_and_format(data)
        if not productos_formateados:
            return "Error al procesar los datos del inventario."

        # Convertir a JSON y devolver la respuesta
        response = make_response(json.dumps(productos_formateados, indent=4, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json; charset=utf-8' # Encabezado para JSON
        return response

    except Exception as e:
        logging.error(f"Error en la ruta /stock: {e}")
        return f"Error: {e}"

if __name__ == '__main__':
    # Inicia el hilo del token (una sola vez)
    if not token_thread:
        token_thread = threading.Thread(target=renew_token_periodically, daemon=True)
        token_thread.start()

    app.run(debug=False) # debug=False en producción