from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path="config/.env")

app = Flask(__name__)

# Variables de configuración (centralizadas)
SHOP_NAME = os.getenv("SHOPIFY_STORE")
ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
API_VERSION = "2024-01"  # Define la versión aquí
BASE_URL = f"https://{SHOP_NAME}/admin/api/{API_VERSION}"
GRAPHQL_URL = f"https://{SHOP_NAME}/admin/api/{API_VERSION}/graphql.json"  # Usa la versión consistente

HEADERS = {
    "Content-Type": "application/json",
    "X-Shopify-Access-Token": ACCESS_TOKEN
}

# --- Funciones principales ---

def get_url_pics_sku(sku):
    """Busca un SKU en Shopify usando GraphQL."""
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

    response = requests.post(GRAPHQL_URL, json=query, headers=HEADERS)
    response.raise_for_status()  # Lanza una excepción si el status code no es 200

    data = response.json()
    variants = data.get("data", {}).get("productVariants", {}).get("edges", [])

    if not variants:
        return {"error": "SKU no encontrado"}

    variant = variants[0]["node"]
    product_title = variant["product"]["title"]
    images = [img["node"]["originalSrc"] for img in variant["product"]["images"]["edges"]]

    return images

def get_inventory_item_id(sku):
    """Obtiene el inventoryItemId basado en el SKU."""

    query = {
        "query": f"""
        {{
          productVariants(first: 1, query: "sku:{sku}") {{
            edges {{
              node {{
                inventoryItem {{
                  id
                }}
              }}
            }}
          }}
        }}
        """
    }

    try:
        response = requests.post(GRAPHQL_URL, json=query, headers=HEADERS)
        response.raise_for_status()  # Lanza una excepción para manejar errores HTTP

        data = response.json()
        variants = data.get("data", {}).get("productVariants", {}).get("edges", [])

        if not variants:
            return None  # SKU no encontrado

        inventory_item_gid = variants[0]["node"]["inventoryItem"].get("id")

        if not inventory_item_gid or "gid://shopify/InventoryItem/" not in inventory_item_gid:
            return None  # Formato de ID inesperado

        return inventory_item_gid.split("/")[-1]  # Extrae el ID numérico

    except requests.exceptions.RequestException as e:
        print(f"❌ Error al obtener inventoryItemId para SKU {sku}: {e}") # Mensaje de error más descriptivo
        return None  # O podrías relanzar la excepción si quieres que el error se propague
    except (KeyError, TypeError) as e:  # Maneja posibles errores en la estructura del JSON
        print(f"❌ Error al procesar la respuesta de Shopify para SKU {sku}: {e}")
        return None
    except Exception as e: #Cualquier otro error
        print(f"❌ Error inesperado al obtener inventoryItemId para SKU {sku}: {e}")
        return None


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

    response = requests.post(GRAPHQL_URL, json=query, headers=HEADERS)
    response.raise_for_status()  # Lanza excepción para manejar errores

    data = response.json()
    variants = data.get("data", {}).get("productVariants", {}).get("edges", [])

    if not variants:
        return None

    inventory_item_gid = variants[0]["node"]["inventoryItem"].get("id")
    if not inventory_item_gid or "gid://shopify/InventoryItem/" not in inventory_item_gid:
        return None

    return inventory_item_gid.split("/")[-1]


def get_location_id():
    """Obtiene el ID de la ubicación."""
    query = {
        "query": """
        query {
          locations(first: 1) {  # Obtén solo la primera ubicación
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

    response = requests.post(GRAPHQL_URL, json=query, headers=HEADERS)
    response.raise_for_status()

    data = response.json()
    locations = data.get("data", {}).get("locations", {}).get("edges", [])

    if not locations:
        return None

    return locations[0]["node"]["id"].split("/")[-1]  # Devuelve solo el ID numérico


def set_stock(inventory_item_id, location_id, stock):
    """Actualiza el stock en Shopify."""
    url = f"{BASE_URL}/inventory_levels/set.json"  # Usa BASE_URL
    payload = {
        "location_id": location_id,
        "inventory_item_id": inventory_item_id,
        "available": stock,
    }

    response = requests.post(url, json=payload, headers=HEADERS)
    response.raise_for_status()  # Lanza excepción para manejar errores

    return response.json()  # Devuelve el JSON de la respuesta


# --- Rutas de Flask ---

@app.route("/update_stock", methods=["POST"])
def update_stock():
    try:
        data = request.get_json()
        sku = data.get("sku")
        new_stock = data.get("stock")

        if not sku or new_stock is None:
            return jsonify({"error": "Faltan parámetros (sku y stock)"}), 400

        inventory_item_id = get_inventory_item_id(sku)
        if not inventory_item_id:
            return jsonify({"error": f"SKU '{sku}' no encontrado"}), 404

        location_id = get_location_id()
        if not location_id:
            return jsonify({"error": "No se encontró location_id"}), 500

        set_stock(inventory_item_id, location_id, new_stock)  # No necesitas guardar el resultado si no lo usas

        return jsonify({"success": True, "message": "Stock actualizado correctamente"}), 200

    except requests.exceptions.HTTPError as e:  # Captura errores HTTP específicos
        return jsonify({"success": False, "error": f"Error en Shopify: {e}"}), e.response.status_code
    except Exception as e:
        return jsonify({"success": False, "error": f"Error: {str(e)}"}), 500


# ... (resto de rutas)

if __name__ == '__main__':
    app.run(debug=True, port=5000)