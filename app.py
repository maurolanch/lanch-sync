from flask import Flask, jsonify
import json
import requests
import threading
import time
from google.cloud import secretmanager
import os
from datetime import datetime

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

#Descargar el inventario de productos

def obtener_inventario(token):
    # Definir la consulta (query)
    query = {
        "query": '''
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
        '''
    }

    # Definir la URL del endpoint
    url = "https://grupologi.com.co/ApiLogi/principal_graph.php"

    # Configurar los headers con el token de autorización
    headers = {
        'Content-Type': 'application/json',
        'Authorization': token  # El token sin bearer
    }

    # Realizar la solicitud POST
    try:
        # Realizar la solicitud
        response = requests.post(url, data=json.dumps(query), headers=headers)
        response.raise_for_status()  # Verifica si hay algún error HTTP

        # Verificar si la respuesta fue exitosa (código 200)
        if response.status_code == 200:
            # Verificar si el tipo de contenido es JSON
            if 'application/json' in response.headers.get('Content-Type', ''):
                try:
                    # Intentar cargar el JSON
                    data = response.json()

                    # Validar la estructura completa del JSON
                    if not isinstance(data, dict):
                        print("Error: La respuesta no tiene una estructura de objeto JSON válida.")
                        return None
                    
                    # Verificar si existe la clave 'data' y que esta sea un diccionario
                    if 'data' not in data or not isinstance(data['data'], dict):
                        print("Error: La clave 'data' está ausente o tiene un tipo incorrecto.")
                        return None

                    # Verificar si 'stock' está dentro de 'data' y es una lista
                    if 'stock' not in data['data'] or not isinstance(data['data']['stock'], list):
                        print("Error: La clave 'stock' está ausente o tiene un tipo incorrecto.")
                        return None

                    stock_data = data['data']['stock']

                    # Validar que stock no esté vacío
                    if not stock_data:
                        print("Advertencia: La lista de productos está vacía.")
                        return None

                    # Validar cada producto dentro de 'stock'
                    for item in stock_data:
                        if 'producto' not in item or not isinstance(item['producto'], list):
                            print(f"Error: El campo 'producto' está ausente o tiene un tipo incorrecto en el item {item}.")
                            return None

                        if 'total_stock' not in item or not isinstance(item['total_stock'], list):
                            print(f"Error: El campo 'total_stock' está ausente o tiene un tipo incorrecto en el item {item}.")
                            return None

                        # Validar campos dentro de 'producto'
                        producto = item['producto'][0] if item['producto'] else None
                        if producto:
                            required_fields = ['pro_cod', 'pro_sku', 'pro_desc', 'pro_ubicacion', 'pro_fech_registro']
                            for field in required_fields:
                                if field not in producto:
                                    print(f"Error: El campo '{field}' está ausente en un producto.")
                                    return None
                                    
                            # Validar formato de la fecha
                            try:
                                datetime.strptime(producto['pro_fech_registro'], '%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                print(f"Error: El campo 'pro_fech_registro' tiene un formato inválido en el producto {producto['pro_cod']}.")
                                return None
                        else:
                            print(f"Error: Producto malformado en el item {item}.")
                            return None

                        # Validar que 'total_stock' tenga un valor válido
                        total_stock = item['total_stock'][0]['total_stock'] if item['total_stock'] else None
                        if total_stock is None or not isinstance(total_stock, int) or total_stock < 0:
                            print(f"Error: El campo 'total_stock' tiene un valor inválido o negativo para el producto {producto['pro_cod']}.")
                            return None

                    # Si todo es correcto, retornar los datos
                    return data

                except json.JSONDecodeError as e:
                    print(f"Error al procesar el JSON: {e}")
                    return None
            else:
                print(f"Error: El tipo de contenido de la respuesta no es JSON. {response.headers.get('Content-Type')}")
                return None
        else:
            print(f"Error {response.status_code}: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        # Manejo de errores en caso de problemas con la conexión
        print(f"Error al realizar la solicitud: {e}")
        return None



#Decodificar, formatear e imprimir los datos del inventario


def decode_and_format(data):
    try:
        # Acceder a la información del inventario
        stock_data = data.get("data", {}).get("stock", [])

        # Lista para almacenar los productos formateados
        productos_formateados = []

        # Procesar cada item de stock
        for stock_item in stock_data:
            productos = stock_item.get("producto", [])
            total_stock = stock_item.get("total_stock", [])

            for producto in productos:
                # Extraer los valores del producto
                pro_cod = producto.get("pro_cod", "").strip()
                pro_sku = producto.get("pro_sku", "").strip()
                pro_desc = producto.get("pro_desc", "").strip()
                pro_ubicacion = producto.get("pro_ubicacion", "").strip()
                pro_fech_registro = producto.get("pro_fech_registro", "").strip()

                # Decodificar pro_desc si tiene caracteres especiales (unicode)
                try:
                    pro_desc = json.loads(f'"{pro_desc}"')  # Decodificar Unicode
                except json.JSONDecodeError:
                    print(f"Error al decodificar 'pro_desc': {pro_desc}")
                    pro_desc = pro_desc  # Mantener el valor original si no se puede decodificar

                # Convertir fecha a timestamp
                try:
                    pro_fech_registro_timestamp = datetime.strptime(pro_fech_registro, "%Y-%m-%d %H:%M:%S").timestamp()
                except ValueError:
                    print(f"Error al convertir 'pro_fech_registro' a timestamp: {pro_fech_registro}")
                    pro_fech_registro_timestamp = None  # Si no puede convertir la fecha, asignar None

                # Obtener total_stock de manera segura
                total_stock_value = total_stock[0].get("total_stock", 0) if total_stock else 0

                # Crear un diccionario con los datos procesados
                producto_formateado = {
                    "pro_cod": pro_cod,
                    "pro_sku": pro_sku,
                    "pro_desc": pro_desc,
                    "pro_ubicacion": pro_ubicacion,
                    "pro_fech_registro": pro_fech_registro_timestamp,
                    "total_stock": total_stock_value
                }
                productos_formateados.append(producto_formateado)

        # Devolver los productos formateados
        print("Productos formateados correctamente:")
        print(productos_formateados)
        return productos_formateados

    except Exception as e:
        print(f"Error al procesar el inventario: {e}")
        return None


# Función para renovar el token cada 12 horas
def renew_token_periodically():
    while True:
        get_token(project_id, secret_id)  # Llama a la función para renovar el token
        time.sleep(43200)  # Espera 12 horas (43200 segundos)

@app.route('/')
def index():
    return "¡Hola desde GCP!"

app = Flask(__name__)

# Aquí va tu función decode_and_format que ya definimos

@app.route("/decode_inventario", methods=["GET"])
def decode_inventario():
    # Obtén el token usando la función obtener_token()
    token = get_token(project_id, secret_id)

    if not token:
        return jsonify({"error": "Token no proporcionado"}), 400
    
    # Supongamos que 'data' es lo que obtienes al hacer la consulta a la API
    # Aquí deberías obtener los datos del inventario con el token
    data = obtener_inventario(token)  # Aquí llamas a obtener_inventario con el token

    if data:
        # Llamamos a la función decode_and_format con los datos recibidos
        productos_formateados = decode_and_format(data)

        # Construir la respuesta como texto con los productos formateados
        productos_texto = ""
        for producto in productos_formateados:
            productos_texto += f"Código: {producto['pro_cod']}\n"
            productos_texto += f"SKU: {producto['pro_sku']}\n"
            productos_texto += f"Descripción: {producto['pro_desc']}\n"
            productos_texto += f"Ubicación: {producto['pro_ubicacion']}\n"
            productos_texto += f"Fecha de Registro: {datetime.fromtimestamp(producto['pro_fech_registro']) if producto['pro_fech_registro'] else 'N/A'}\n"
            productos_texto += f"Total Stock: {producto['total_stock']}\n"
            productos_texto += "-" * 30 + "\n"

        # Devolvemos los productos formateados en el cuerpo de la respuesta
        return productos_texto, 200
    else:
        return jsonify({"error": "No se pudo obtener el inventario"}), 500


# Iniciar el servidor Flask
if __name__ == '__main__':
    # Inicia el hilo para renovar el token
    threading.Thread(target=renew_token_periodically, daemon=True).start()
    app.run()

