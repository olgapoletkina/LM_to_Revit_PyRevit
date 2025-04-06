# 🏢 Fine-Tuned Room Classifier for German NUF Codes

https://huggingface.co/olgapoletkina/fine-tuned-nuf-room-classifier 

This model is a fine-tuned multilingual sentence-transformer that classifies German room names into their appropriate **NUF (Nutzenfläche)** categories. It’s trained on real architectural data (from Sachsen’s NC catalog) to support Revit automation workflows using pyRevit and Machine Learning.

---

## 🔍 What This Model Does

Given a room name (e.g., `"Wohnung"`), the model returns the top predicted **NUF category**, such as `NUF_1`, `NUF_2`, etc., based on semantic similarity.

It’s designed for use in **BIM automation**, particularly inside Autodesk Revit, where it can suggest room classifications and auto-fill parameters.

---

## 🧠 Model Architecture

- **Base model**: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`
- **Fine-tuned on**: German room names grouped by NUF class using contrastive learning
- **Loss function**: `CosineSimilarityLoss`
- **Training strategy**: Pairs of room names labeled as "same class" (1) or "different class" (0)
- **Framework**: `sentence-transformers`, `sklearn`, `PyTorch`

---

## 📦 Intended Use

This model was built for integration with:

- 🧩 **pyRevit custom buttons** (scripts that classify rooms inside Revit projects)
- 🌐 **Flask APIs** (for lightweight local prediction services)
- 🏗️ **Architectural data annotation**, classification, or exploration

---

## 💡 Example

```python
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import json

# Load model and NUF class embeddings
model = SentenceTransformer("olgapoletkina/fine-tuned-nuf-room-classifier")

with open("class_embeddings.json", "r") as f:
    class_embeddings = json.load(f)
    class_embeddings = {k: np.array(v) for k, v in class_embeddings.items()}

# Classify a new room name
text = "Wohnung"
embedding = model.encode(text, normalize_embeddings=True)

scores = {
    k: float(cosine_similarity([embedding], [v])[0][0])
    for k, v in class_embeddings.items()
}

predicted_class = max(scores, key=scores.get)
print(f"Predicted NUF class: {predicted_class}")
