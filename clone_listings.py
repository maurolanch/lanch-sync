import requests
import json
from shopi import get_url_pics_sku
from flask import Flask, request, jsonify
from auth import load_tokens, get_user_info
from ml import get_traditional_listings

app = Flask(__name__)

def obtener_datos_publicacion(ml_item_id, access_token):
    print("Obteniendo datos de la publicación...")
    url = f"https://api.mercadolibre.com/items/{ml_item_id}?include_attributes=all&access_token={access_token}"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None
def clonar_publicacion(sku, access_token_cuenta1, access_token_cuenta2):
    try:
        user_id = get_user_info('cuenta1')['id']
        search_url = f"https://api.mercadolibre.com/users/{user_id}/items/search?seller_sku={sku}&access_token={access_token_cuenta1}"
        search_response = requests.get(search_url).json()

        if not search_response.get("results"):
            return f"No se encontró ninguna publicación con SKU: {sku}"

        results = search_response["results"]
        item_id = get_traditional_listings(access_token_cuenta1, results)[0]
        # 2. Obtener detalles del producto original
        datos_originales = obtener_datos_publicacion(item_id, access_token_cuenta1)
        if not datos_originales:
            return "Error al obtener los datos del producto."
        
        with open("original.json", "w", encoding="utf-8") as file:
            json.dump(datos_originales, file, indent=4, ensure_ascii=False)  # `indent=4` para que sea legible

        print("JSON exportado correctamente a 'original.json'")

        # 3. Obtener imágenes desde Shopify (función ya existente)
        imagenes_sku = get_url_pics_sku(sku)
        if not imagenes_sku:
            return "Error al obtener las imágenes del SKU."
        # 4. Crear el nuevo payload (excluyendo imágenes originales y seller_id)
    
        nuevo_payload = {
            "title": datos_originales["title"],
            "category_id": datos_originales["category_id"],
            "price": datos_originales["price"],
            "currency_id": datos_originales["currency_id"],
            "available_quantity": datos_originales["available_quantity"],
            "buying_mode": datos_originales["buying_mode"],
            "condition": datos_originales["condition"],
            "listing_type_id": datos_originales["listing_type_id"],
            "sale_terms": [
                {"id": term["id"], "value_name": term["value_name"]}
                for term in datos_originales.get("sale_terms", [])
                if term["id"] in ["WARRANTY_TYPE", "WARRANTY_TIME"]
            ],
            "pictures": [{"source": img} for img in imagenes_sku],
            "shipping": {
                "mode": datos_originales.get("shipping", {}).get("mode", "me2"),  # Valor por defecto "me2"
                "tags": datos_originales.get("shipping", {}).get("tags", [])  # Extrae los tags o lista vacía si no existe
            },
            "attributes": [
                {"id": attr["id"], "value_name": attr["value_name"]}
                for attr in datos_originales.get("attributes", [])  # 🔥 Asegura que `attributes` exista
                if attr.get("value_name") is not None  # 🔍 Filtra solo los que tienen `value_name`
            ],
            "variations": [
            {
                "price": var["price"],
                "attribute_combinations": [
                    attr for attr in var["attribute_combinations"]
                    if attr["name"] != "Compatibilidad" or attr.get("value_name")
                ],
                "available_quantity": var["available_quantity"],
                "picture_ids": imagenes_sku,
                "attributes": var["attributes"]
            }
            for var in datos_originales["variations"]
        ]
        }

        with open("publicacion.json", "w", encoding="utf-8") as file:
            json.dump(nuevo_payload, file, indent=4, ensure_ascii=False)  # `indent=4` para que sea legible

        print("JSON exportado correctamente a 'publicacion.json'")


        # 5. Publicar en la cuenta 2
        url_publicar = f"https://api.mercadolibre.com/items"
        headers = {"Authorization": f"Bearer {access_token_cuenta2}","Content-Type": "application/json"}
        response = requests.post(url_publicar, json=nuevo_payload, headers=headers)
        #response.raise_for_status()  # Lanza una excepción si hay un error HTTP
        return response.json() if response.status_code == 201 else f"Error: {response.text}"

    except requests.exceptions.RequestException as e:
        return f"Error al clonar publicación: {e}"
    except Exception as e:
        return f"Error inesperado al clonar publicación: {e}"
    
@app.route("/clonar/<sku>", methods=["GET"])
def clonar_producto(sku):
    try:
        tokens = load_tokens()
        
        # Verificamos que ambas cuentas tengan access_token
        if "cuenta1" not in tokens or "cuenta2" not in tokens:
            return jsonify({"error": "No se encontraron tokens para ambas cuentas."}), 400

        access_token_cuenta1 = tokens["cuenta1"]["access_token"]
        access_token_cuenta2 = tokens["cuenta2"]["access_token"]
        resultado = clonar_publicacion(sku, access_token_cuenta1, access_token_cuenta2)
        return jsonify({"resultado": resultado})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)