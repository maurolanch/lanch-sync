from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv

# Cargar variables del archivo .env
load_dotenv(dotenv_path="config/.env")

app = Flask(__name__)

# Variables de configuración
SHOP_NAME = os.getenv("SHOPIFY_STORE")  # Tu dominio de tienda
ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")  # Access Token

BASE_URL = f"https://{SHOP_NAME}/admin/api/2023-01"  # URL base para la API
GRAPHQL_URL = f"https://{SHOP_NAME}/admin/api/2024-01/graphql.json"

API_VERSION = "2024-01"
API_URL = f"https://{SHOP_NAME}/admin/api/{API_VERSION}"

# Encabezados para autenticación
HEADERS = {
    "Content-Type": "application/json",
    "X-Shopify-Access-Token": ACCESS_TOKEN
}

def get_url_pics_sku(sku):
    """Busca un SKU en Shopify usando GraphQL."""
    graphql_url = f"https://{SHOP_NAME}/admin/api/2023-01/graphql.json"
    query = {
        "query": f"""
        {{
          productVariants(first: 10, query: "sku:{sku}") {{
            edges {{
              node {{
                id
                sku
                product {{
                  id
                  title
                  images(first: 10) {{
                    edges {{
                      node {{
                        originalSrc
                      }}
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """
    }

    respuesta = requests.post(graphql_url, json=query, headers=HEADERS)
    if respuesta.status_code != 200:
        return {"error": f"Error en GraphQL: {respuesta.status_code}"}

    datos = respuesta.json()
    variantes = datos.get("data", {}).get("productVariants", {}).get("edges", [])

    if not variantes:
        print("\n❌ SKU no encontrado en GraphQL.")
        return {"error": "SKU no encontrado"}

    # Extraemos la información del producto
    variante = variantes[0]["node"]
    product_title = variante["product"]["title"]
    imagenes = [img["node"]["originalSrc"] for img in variante["product"]["images"]["edges"]]

    print(f"\n✅ SKU encontrado con GraphQL: {sku}")
    print(f"🔹 Producto: {product_title}")
    print(f"🔹 URLs de imágenes: {imagenes}")

    return {"sku": sku, "imagenes": imagenes}

def get_inventory_item_id(sku):
    """Obtiene el inventoryItemId basado en el SKU."""
    query = {
        "query": f"""
        {{
          productVariants(first: 1, query: "sku:{sku}") {{
            edges {{
              node {{
                id
                sku
                inventoryItem {{
                  id
                }}
              }}
            }}
          }}
        }}
        """
    }

    print(f"🔍 Buscando inventoryItemId para SKU: {sku}")
    response = requests.post(GRAPHQL_URL, json=query, headers=HEADERS)
    
    try:
        data = response.json()
    except requests.exceptions.JSONDecodeError:
        print("❌ Error al decodificar JSON de Shopify")
        return None

    print(f"📥 Respuesta de Shopify: {data}")  # Depuración

    variants = data.get("data", {}).get("productVariants", {}).get("edges", [])
    if not variants:
        print("❌ No se encontró el SKU en Shopify")
        return None

    inventory_item_gid = variants[0]["node"]["inventoryItem"].get("id")
    
    if not inventory_item_gid or "gid://shopify/InventoryItem/" not in inventory_item_gid:
        print("❌ Formato de inventoryItemId inesperado")
        return None

    inventory_item_id = inventory_item_gid.split("/")[-1]  # Extrae solo el número

    print(f"✅ inventoryItemId encontrado: {inventory_item_id}")
    return inventory_item_id


def get_location_id():
    url = f"https://{SHOP_NAME}/admin/api/2024-01/graphql.json"
    headers = {
        "X-Shopify-Access-Token": ACCESS_TOKEN,
        "Content-Type": "application/json"
    }
    query = {
        "query": """
        query {
          locations(first: 10) {
            edges {
              node {
                id
                name
              }
            }
          }
        }
        """
    }

    print("🔍 Buscando locationId en Shopify...")

    response = requests.post(url, headers=headers, json=query)
    
    try:
        data = response.json()
    except requests.exceptions.JSONDecodeError:
        print("❌ Error al decodificar JSON de Shopify")
        return None

    print(f"📥 Respuesta de Shopify: {data}")

    locations = data.get("data", {}).get("locations", {}).get("edges", [])

    if not locations:
        print("❌ No se encontraron ubicaciones en Shopify.")
        return None

    location_gid = locations[0]["node"]["id"]  # Extrae el ID en formato GID
    location_id = location_gid.split("/")[-1]  # Extrae solo el número

    print(f"✅ Location encontrada: {locations[0]['node']['name']} -> {location_id}")
    return location_id
    
def get_inventory_level_id(shopify_store, access_token, inventory_item_id, location_id):
    url = f"https://{shopify_store}/admin/api/2024-01/inventory_levels.json"
    
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }
    
    params = {
        "inventory_item_ids": inventory_item_id,
        "location_ids": location_id
    }
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        
        if data.get("inventory_levels"):
            inventory_level = data["inventory_levels"][0]  # Tomamos el primer resultado
            return inventory_level["admin_graphql_api_id"]  # Este es el inventoryLevelId
        
        return None  # No se encontró el inventory level
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")
        return None

import requests

def set_stock(inventory_item_id, location_id, stock):
    """Actualiza el stock de un producto en Shopify usando REST API."""
    url = f"https://{SHOP_NAME}/admin/api/2023-10/inventory_levels/set.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": ACCESS_TOKEN,
    }
    payload = {
        "location_id": location_id,
        "inventory_item_id": inventory_item_id,
        "available": stock,
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response_data = response.json() if response.content else {}

        success = response.status_code in [200, 201]
        return {
            "success": success,
            "status_code": response.status_code,
            "response": response_data
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "status_code": 500,
            "response": {"error": f"Request error: {str(e)}"}
        }
    except Exception as e:
        return {
            "success": False,
            "status_code": 500,
            "response": {"error": f"Unexpected error: {str(e)}"}
        }

@app.route("/update_stock", methods=["POST"])
def update_stock():
    """Ruta para actualizar stock en Shopify usando SKU"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No se recibió JSON"}), 400
        
        sku = data.get("sku")
        new_stock = data.get("stock")

        if not sku or new_stock is None:
            return jsonify({"success": False, "error": "Faltan parámetros (sku y stock)"}), 400

        # Obtener inventory_item_id
        inventory_item_id = get_inventory_item_id(sku)
        if not inventory_item_id:
            return jsonify({"success": False, "error": f"SKU '{sku}' no encontrado"}), 404

        # Obtener location_id
        location_id = get_location_id()
        if not location_id:
            return jsonify({"success": False, "error": "No se encontró location_id"}), 500

        # Actualizar stock en Shopify
        result = set_stock(inventory_item_id, location_id, new_stock)

        # 🛠️ Log para depuración
        print(f"🔍 Respuesta de set_stock(): {result}")

        # Asegurar que result tiene la estructura esperada
        if not isinstance(result, dict) or "success" not in result or "status_code" not in result:
            return jsonify({"success": False, "error": "Respuesta inválida de set_stock"}), 500

        if result["success"]:
            return jsonify({"success": True, "message": "Stock actualizado correctamente"}), 200
        else:
            return jsonify({
                "success": False,
                "error": "Error al actualizar el stock",
                "status_code": result.get("status_code", 500),
                "response": result.get("response", {})
            }), 500  # Evitamos devolver el mismo código de error si es inválido

    except Exception as e:
        return jsonify({"success": False, "error": f"Exception: {str(e)}"}), 500




@app.route("/inventory-level", methods=["GET"])
def inventory_level():
    """Endpoint para obtener el inventoryLevelId de un SKU."""
    sku = request.args.get("sku")
    if not sku:
        return jsonify({"error": "Se requiere un SKU"}), 400

    inventory_item_id = get_inventory_item_id(sku)
    if not inventory_item_id:
        return jsonify({"error": "No se encontró inventoryItemId para el SKU"}), 404

    location_id = get_location_id()
    if not location_id:
        return jsonify({"error": "No se encontró locationId"}), 404

    inventory_level_id = get_inventory_level_id(SHOP_NAME, ACCESS_TOKEN, inventory_item_id, location_id)
    if not inventory_level_id:
        return jsonify({"error": "No se encontró inventoryLevelId"}), 404

    return jsonify({
        "sku": sku,
        "inventory_item_id": inventory_item_id,
        "location_id": location_id,
        "inventory_level_id": inventory_level_id
    })



@app.route('/get_inventory_item_id', methods=['GET'])
def api_get_inventory_item_id():
    sku = request.args.get('sku')
    if not sku:
        return jsonify({"error": "Se requiere el parámetro SKU"}), 400
    
    inventory_item_id = get_inventory_item_id(sku)
    if inventory_item_id:
        return jsonify({"inventory_item_id": inventory_item_id})
    else:
        return jsonify({"error": "No se encontró inventoryItemId"}), 404

# Endpoint de prueba para get_location_id
@app.route('/get_location_id', methods=['GET'])
def api_get_location_id():
    locations = get_location_id()
    if locations:
        return jsonify({"locations": locations})
    else:
        return jsonify({"error": "No se encontraron ubicaciones"}), 404


if __name__ == '__main__':
    app.run(debug=True, port=5000)
