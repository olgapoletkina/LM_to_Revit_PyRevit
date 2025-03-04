from flask import Flask, request, jsonify
from sentence_transformers import SentenceTransformer
import torch
import numpy as np
import json
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)

MODEL_PATH = './fine_tuned_model_for_NUF_clustering_v5'

device = 'cuda' if torch.cuda.is_available() else 'cpu'
model = SentenceTransformer(MODEL_PATH, device=device)

with open("class_embeddings.json", "r") as f:
    class_embeddings = json.load(f)

for class_label, embedding_list in class_embeddings.items():
    class_embeddings[class_label] = np.array(embedding_list)

@app.route("/predict", methods=["POST"])
def predict():
    """
    Expects JSON input like:
    {
      "text": "room name to classify"
    }
    """
    data = request.get_json()  # parse JSON
    if not data or "text" not in data:
        return jsonify({"error": "Invalid input. JSON with 'text' required."}), 400

    input_text = data["text"]
    if not input_text.strip():
        return jsonify({"error": "Text cannot be empty."}), 400

    new_embedding = model.encode(input_text, convert_to_numpy=True, normalize_embeddings=True)

    class_scores = {}
    for label, prototype in class_embeddings.items():
        similarity = cosine_similarity(
            new_embedding.reshape(1, -1),
            prototype.reshape(1, -1)
        )[0][0]
        class_scores[label] = float(similarity)  # convert numpy float to Python float

    sum_of_scores = sum(class_scores.values())
    best_class = max(class_scores, key=class_scores.get)  # label with highest similarity
    best_score = class_scores[best_class]

    if sum_of_scores > 0:
        confidence = (best_score / sum_of_scores) * 100
    else:
        confidence = 0.0

    response = {
        "input_text": input_text,
        "predicted_class": best_class,
        "confidence_percentage": round(confidence, 2),
        "all_class_scores": class_scores
    }

    formatted_response = json.dumps(response, indent=4)
    print(formatted_response)
    
    return response, 200

if __name__ == "__main__":
    # Start the Flask development server
    # "debug=True" auto-reloads on code changes
    app.run(host="0.0.0.0", port=5002, debug=True)
