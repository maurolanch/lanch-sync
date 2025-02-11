from flask import Flask, request, redirect, jsonify
import requests

app = Flask(__name__)

# Configuración de MercadoLibre
CLIENT_ID = '8885330221347884'
CLIENT_SECRET = 'CN04G3UTi1s6y3RErVCkTbFRA3dLmVzs'
REDIRECT_URI = 'https://ec2d-2800-484-515b-b000-e96a-dabe-2f13-cb12.ngrok-free.app/callback'


CLIENT_ID2 = '8538706117577276' 
CLIENT_SECRET2= 'S8c4YAmn2cq8gKykQZ6N41c6aastRFXw'
REDIRECT_URI2= 'https://ec2d-2800-484-515b-b000-e96a-dabe-2f13-cb12.ngrok-free.app/callback2'


AUTHORIZATION_URL = 'https://auth.mercadolibre.com.co/authorization'
TOKEN_URL = 'https://api.mercadolibre.com/oauth/token'

ACCESS_TOKEN = None  # Variable para almacenar el token
USER_ID = None  # Variable para almacenar el user_id
SITE_ID = None  # Variable para almacenar el site_id

@app.route('/')
def home():
    """Redirige al usuario a la URL de autorización de MercadoLibre."""
    auth_url = f'{AUTHORIZATION_URL}?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}'
    return redirect(auth_url)

@app.route('/callback', methods=['GET'])
def callback():
    """Recibe el código de autorización y obtiene el token de acceso."""
    global ACCESS_TOKEN, USER_ID, SITE_ID
    code = request.args.get('code')  # Código de autorización enviado en la URL
    
    # Depuración: Imprimir el valor de 'code'
    print(f"Received code: {code}")
    
    if not code:
        return 'No code received, something went wrong.', 400

    token_response = get_access_token(code)
    if token_response:
        ACCESS_TOKEN = token_response.get('access_token')
        USER_ID, SITE_ID = get_user_data(ACCESS_TOKEN)
        return f'Autenticación exitosa. User ID: {USER_ID}, Site ID: {SITE_ID}. Access Token: {ACCESS_TOKEN}', 200
    else:
        return 'Error al obtener el token.', 400
  
@app.route('/webhooks', methods=['POST'])
def webhooks():
    """Recibe notificaciones de MercadoLibre, las imprime y responde con OK."""
    try:
        data = request.json  # Obtiene el JSON enviado por MercadoLibre
        #print(f"Notificación recibida: {data}")  # Imprime en la consola

        # Responder con HTTP 200 para confirmar la recepción
        return jsonify({"status": "received"}), 200
    except Exception as e:
        print(f"Error procesando la notificación: {str(e)}")
        return jsonify({"error": "Bad request"}), 400

def get_access_token(code):
    """Intercambia el código de autorización por un token de acceso."""
    payload = {
        'grant_type': 'authorization_code',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    response = requests.post(TOKEN_URL, data=payload)
    return response.json() if response.status_code == 200 else None

def get_user_data(access_token):
    """Obtiene el User ID y el Site ID del usuario autenticado."""
    if not access_token:
        return None, None
    
    response = requests.get("https://api.mercadolibre.com/users/me", headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
    
    if response.status_code == 200:
        user_data = response.json()
        user_id = user_data.get('id')
        site_id = user_data.get('site_id')
        return user_id, site_id
    else:
        print(f"Error {response.status_code}: {response.text}")
        return None, None

def get_listings_by_sku(access_token: str, user_id: str, seller_sku: str):
    url = f"https://api.mercadolibre.com/users/{user_id}/items/search?seller_sku={seller_sku}"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        return data.get("results", [])
    else:
        print(f"Error {response.status_code}: {response.text}")
        return None


def get_traditional_listings(access_token: str, item_ids: list):
    traditional_listings = []
    for item_id in item_ids:
        url = f"https://api.mercadolibre.com/items/{item_id}?include_attributes=all"
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            item_data = response.json()
            if "catalog_listing" in item_data and item_data["catalog_listing"] is False:
                traditional_listings.append(item_id)
        else:
            print(f"Error {response.status_code}: {response.text}")
    
    return traditional_listings


def get_full_listings(access_token, item_ids):
    """
    Clasifica las publicaciones en full (fulfillment) y no_full (sin fulfillment).
    
    :param access_token: Token de acceso de MercadoLibre.
    :param item_ids: Lista de IDs de publicaciones.
    :return: Diccionario con listas de publicaciones categorizadas.
    """
    full_listings = {"full": [], "no_full": []}
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    for item_id in item_ids:
        url = f"https://api.mercadolibre.com/items/{item_id}?include_attributes=all"
        response = requests.get(url, headers=headers)
        
        print(f"Consultando item_id: {item_id}")  # Depuración para saber qué item estamos procesando
        
        if response.status_code == 200:
            item_data = response.json()
            
            # Verificar si 'shipping' y 'logistic_type' existen
            if "shipping" not in item_data or "logistic_type" not in item_data["shipping"]:
                raise ValueError(f"Logistic type not found for item {item_id}")
            
            logistic_type = item_data["shipping"]["logistic_type"]
            
            # Verificar si es 'fulfillment' para agregarlo a 'full'
            if logistic_type == "fulfillment":
                full_listings["full"].append(item_id)
            else:
                full_listings["no_full"].append(item_id)
        else:
            print(f"Error {response.status_code}: {response.text}")
    
    print(f"Resultado final de get_full_listings: {full_listings}")  # Ver el diccionario final
    return full_listings

def update_flex(access_token, site_id, item_ids, stock):
    """
    Actualiza el estado de 'flex' para cada producto dependiendo del stock.
    
    Si el stock es mayor a cero, activa Flex. Si el stock es cero, desactiva Flex.

    :param access_token: Token de acceso de MercadoLibre.
    :param site_id: ID del sitio de MercadoLibre.
    :param item_ids: Diccionario con listas de item_ids clasificadas por fulfillment ('full' y 'no_full').
    :param stock: El número de unidades en stock.
    """
    headers = {"Authorization": f"Bearer {access_token}"}

    # Iterar a través de las claves 'full' y 'no_full' en el diccionario item_ids
    for fulfillment_type in ["full", "no_full"]:
        if fulfillment_type not in item_ids:
            continue  # Si no hay ítems en esta categoría, pasamos a la siguiente

        for item_id in item_ids[fulfillment_type]:
            url = f"https://api.mercadolibre.com/sites/{site_id}/shipping/selfservice/items/{item_id}"

            # Verificar el estado actual de Flex
            check_response = requests.get(url, headers=headers)

            if check_response.status_code == 204 and stock > 0:
                print(f"Item {item_id} ya tiene flex activado, no es necesario cambiarlo.")
                continue  # No hacer nada si ya está activado
            
            if check_response.status_code == 404 and stock == 0:
                print(f"Item {item_id} ya tiene flex desactivado, no es necesario cambiarlo.")
                continue  # No hacer nada si ya está desactivado

            # Activar o desactivar Flex según el stock
            if stock > 0:
                response = requests.post(url, headers=headers)
                if response.status_code in [200, 204]:
                    print(f"Item {item_id} activado en flex")
                else:
                    print(f"Error al activar flex para {item_id}: {response.status_code} - {response.text}")
            elif stock == 0:
                response = requests.delete(url, headers=headers)
                if response.status_code in [200, 204]:
                    print(f"Item {item_id} desactivado de flex")
                else:
                    print(f"Error al desactivar flex para {item_id}: {response.status_code} - {response.text}")
            else:
                print(f"Item {item_id} no requiere acción porque el stock es negativo.")


def update_stock(access_token, item_ids, sku, stock):
    """
    Actualiza el stock de una variación con un SKU específico solo si el valor cambia.
    También cambia el estado del ítem a "active" si estaba en "paused" y el stock es mayor a 0.

    :param access_token: Token de acceso de MercadoLibre.
    :param item_ids: Diccionario con listas 'full' y 'no_full' de item_ids.
    :param sku: El SKU a actualizar.
    :param stock: El stock a asignar.
    """
    base_url = "https://api.mercadolibre.com/items"
    no_full_items = item_ids.get('no_full', [])

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    for item_id in no_full_items:
        item_url = f"{base_url}/{item_id}?include_attributes=all"
        response = requests.get(item_url, headers=headers)

        if response.status_code == 200:
            item_data = response.json()
            variations = item_data.get("variations", [])
            current_status = item_data.get("status", "")

            variations_to_update = []
            updated_stock = False  # Flag para saber si se debe actualizar el stock
            total_available_stock = 0  # Variable para verificar stock total

            for variation in variations:
                current_quantity = variation.get("available_quantity", 0)
                total_available_stock += current_quantity  # Sumar stock total actual

                for attribute in variation.get("attributes", []):
                    if attribute.get("id") == "SELLER_SKU" and attribute.get("value_name") == sku:
                        # Solo actualizamos si el stock es diferente al actual
                        if current_quantity != stock:
                            variations_to_update.append({
                                "id": variation["id"],
                                "available_quantity": stock
                            })
                            updated_stock = True
                        break  # No es necesario seguir revisando atributos de esta variación

            # Verificamos si debemos cambiar el estado del item a "active"
            needs_status_update = current_status == "paused" and stock > 0

            # Si hay cambios en stock o en el estado, enviamos la actualización
            if updated_stock or needs_status_update:
                update_payload = {}
                
                if updated_stock:
                    update_payload["variations"] = variations_to_update

                if needs_status_update:
                    update_payload["status"] = "active"

                update_url = f"{base_url}/{item_id}"
                update_response = requests.put(update_url, json=update_payload, headers=headers)

                if update_response.status_code == 200:
                    if updated_stock:
                        print(f"Stock actualizado para el item {item_id}.")
                    if needs_status_update:
                        print(f"Estado del item {item_id} cambiado a 'active'.")
                else:
                    print(f"Error al actualizar item {item_id}: {update_response.status_code} - {update_response.text}")
            else:
                print(f"No se realizaron cambios en el item {item_id}, ya que el stock y el estado son los mismos.")

        else:
            print(f"Error al obtener datos del item {item_id}: {response.status_code} - {response.text}")





@app.route('/update_stock', methods=['POST'])
def update_stock_route():
    """Ruta para actualizar el stock de un SKU específico."""
    global ACCESS_TOKEN, USER_ID, SITE_ID  # Asegúrate de tener SITE_ID definido en tu código

    if not ACCESS_TOKEN or not USER_ID:
        return jsonify({"error": "No authenticated user. Please authenticate first."}), 401

    data = request.json
    sku = data.get("sku")
    stock = data.get("stock")

    if not sku or stock is None:
        return jsonify({"error": "Missing SKU or stock"}), 400

    # Obtener item_ids de publicaciones activas
    item_ids = get_listings_by_sku(ACCESS_TOKEN, USER_ID, sku)
    
    if not item_ids:
        return jsonify({"error": "No items found for the given SKU"}), 404

    # Filtrar entre publicaciones tradicionales y full
    traditional_items = get_traditional_listings(ACCESS_TOKEN, item_ids)
    categorized_items = get_full_listings(ACCESS_TOKEN, traditional_items)

    # Actualizar stock
    update_stock(ACCESS_TOKEN, categorized_items, sku, stock)

    # Actualizar estado Flex
    update_flex(ACCESS_TOKEN, SITE_ID, categorized_items, stock)

    return jsonify({"message": "Stock update process initiated", "sku": sku, "stock": stock}), 200



if __name__ == '__main__':
    app.run(debug=True, port=5000)
