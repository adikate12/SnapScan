import os
import time
import uuid
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from azure.cosmos import CosmosClient, PartitionKey
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Cosmos DB
COSMOS_URL = os.getenv("COSMOS_URL")
COSMOS_KEY = os.getenv("COSMOS_KEY")
COSMOS_DB_NAME = os.getenv("COSMOS_DB_NAME")
COSMOS_CONTAINER = os.getenv("COSMOS_CONTAINER")

cosmos_client = CosmosClient(COSMOS_URL, COSMOS_KEY)
database = cosmos_client.create_database_if_not_exists(id=COSMOS_DB_NAME)
container = database.create_container_if_not_exists(
    id=COSMOS_CONTAINER,
    partition_key=PartitionKey(path="/userId"),
    offer_throughput=400
)

# Blob Storage
AZURE_BLOB_CONNECTION_STRING = os.getenv("AZURE_BLOB_CONNECTION_STRING")
BLOB_CONTAINER_NAME = os.getenv("BLOB_CONTAINER_NAME")

blob_service_client = BlobServiceClient.from_connection_string(AZURE_BLOB_CONNECTION_STRING)
blob_container_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)

# Vision API
AZURE_KEY = os.getenv("AZURE_KEY")
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
VISION_CAPTION_URL = AZURE_ENDPOINT + "vision/v3.2/describe"
VISION_READ_URL = AZURE_ENDPOINT + "vision/v3.2/read/analyze"

@app.route("/analyze", methods=["POST"])
def analyze_image():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    image = request.files["image"]
    user_id = request.form.get("userId", "guest_user")

    image_filename = str(uuid.uuid4()) + os.path.splitext(image.filename)[1]

    try:
        blob_client = blob_container_client.get_blob_client(image_filename)
        image_bytes = image.read()
        blob_client.upload_blob(image_bytes, overwrite=True)
        image_url = blob_client.url
    except Exception as e:
        return jsonify({"error": f"Failed to upload image: {str(e)}"}), 500

    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_KEY,
        "Content-Type": "application/octet-stream",
    }

    # Caption
    caption_response = requests.post(VISION_CAPTION_URL, headers=headers, data=image_bytes)
    caption_response.raise_for_status()
    caption_data = caption_response.json()
    caption = caption_data["description"]["captions"][0]["text"] if caption_data["description"]["captions"] else "No caption found"

    # OCR
    image.seek(0)
    read_response = requests.post(VISION_READ_URL, headers=headers, data=image.read())
    if read_response.status_code != 202:
        return jsonify({"error": "Failed to initiate OCR"}), 500

    operation_url = read_response.headers["Operation-Location"]

    analysis = {}
    for _ in range(10):
        result = requests.get(operation_url, headers={"Ocp-Apim-Subscription-Key": AZURE_KEY})
        result = result.json()
        if result["status"] == "succeeded":
            analysis = result
            break
        time.sleep(1)

    extracted_text = ""
    if "analyzeResult" in analysis:
        for page in analysis["analyzeResult"]["readResults"]:
            for line in page["lines"]:
                extracted_text += line["text"] + "\n"

    item = {
        "id": str(uuid.uuid4()),
        "userId": user_id,
        "caption": caption,
        "text": extracted_text.strip(),
        "imageUrl": image_url,
        "timestamp": datetime.utcnow().isoformat()
    }

    container.create_item(body=item)

    return jsonify({
        "caption": caption,
        "text": extracted_text.strip() or "No text detected",
        "imageUrl": image_url
    })

@app.route("/history", methods=["GET"])
def get_history():
    user_id = request.args.get("userId", "guest_user")
    query = f"SELECT * FROM c WHERE c.userId = '{user_id}'"
    items = list(container.query_items(query=query, enable_cross_partition_query=True))
    return jsonify(items)

if __name__ == "__main__":
    app.run(debug=True)
