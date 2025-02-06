import os
import requests
from dotenv import load_dotenv
import re  # Necesario para el manejo de la paginación

# Cargar variables del archivo .env
load_dotenv(dotenv_path="config/.env")

# Variables de configuración
SHOP_NAME = os.getenv("SHOPIFY_STORE")  # Tu dominio de tienda
API_KEY = os.getenv("SHOPIFY_API_KEY")  # API Key
ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")  # Access Token

BASE_URL = f"https://{SHOP_NAME}/admin/api/2023-01"  # URL base para la API
# Encabezados para autenticación
HEADERS = {
    "Content-Type": "application/json",
    "X-Shopify-Access-Token": ACCESS_TOKEN
}

# Obtener productos
def get_all_products(api_url, headers):
    all_products = []
    while api_url:
        response = requests.get(api_url, headers=headers)  # Usamos api_url para la solicitud
        if response.status_code == 200:
            data = response.json()
            #print("Esta es la respuesta de data: ", data)
            products = data.get('products', [])
            all_products.extend(products)
            
            # Obtener la URL de la siguiente página si existe
            next_page_url = None
            if 'link' in response.headers:
                links = response.headers['link']
                next_page_match = re.search(r'<(https://[^>]+)>; rel="next"', links)
                if next_page_match:
                    next_page_url = next_page_match.group(1)
            
            # Actualizar la URL para la siguiente iteración o salir si no hay más páginas
            api_url = next_page_url
        else:
            print(f"Error al obtener datos: {response.status_code}")
            break

    return all_products

if __name__ == "__main__":
    print("Conectando a la API de Shopify...")
    # Pasamos BASE_URL y HEADERS
    products = get_all_products(BASE_URL + "/products.json", HEADERS) 
    if products:
        print(f"Se encontraron {len(products)} productos:")
        for product in products:
            print(f"- {product['title']}")
            for variant in product['variants']:
                sku = variant.get('sku', 'No SKU disponible')  # Obtenemos el SKU de la variante
                print(f"SKU: {sku}")
    else:
        print("No se encontraron productos o hubo un error.")
