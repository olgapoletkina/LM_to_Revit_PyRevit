#!python3

# To properly build the pyRevit button and manage the correct interpreter for using CPython in pyRevit, watch the following videos by Erik Frits:

# https://www.youtube.com/watch?v=B1CJTK-4U8g
# https://www.youtube.com/watch?v=-r-HSIC6wf8&t=305s

import sys
import clr

sys.path.append(r"C:\Users\poletkina\AppData\Local\Programs\Python\Python38\Lib\site-packages")
sys.path.append(r"C:\Users\poletkina\AppData\Local\Programs\Python\Python38\Lib")

clr.AddReference('ProtoGeometry')
clr.AddReference('RevitServices')
clr.AddReference('RevitNodes')
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')

from RevitServices.Persistence import DocumentManager

from Autodesk.Revit import DB
from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType

clr.AddReference('System.Windows.Forms')
from System.Windows.Forms import DialogResult, MessageBox, MessageBoxButtons, MessageBoxIcon

import pyrevit

import requests
import json 

uiapp = __revit__
doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
app = __revit__.Application

    
room_ref = uidoc.Selection.PickObject(ObjectType.Element, "Pick an element")
name = doc.GetElement(room_ref.ElementId).LookupParameter('Name').AsString()
name_to_model = name.lower() # Model is case sensitive , was trained on lower case

url = "http://127.0.0.1:5002/predict"
data = {
    "text": name_to_model  # The room name you'd like to classify
}
response = requests.post(url, json=data)

if response.status_code == 200:
    response_json = response.json()
    if "all_class_scores" in response_json:
        response_json["all_class_scores"] = {
            key: round(value, 3) for key, value in response_json["all_class_scores"].items()
        }

    formatted_response = json.dumps(response_json, indent=4, ensure_ascii=False)
    print("Response from model:\n", formatted_response)
else:
    print(f"Error: Received status code {response.status_code} from the model server.")
    print("Response text:", response.text)


predicted_class = response.json()['predicted_class']
confidence_percentage = response.json()['confidence_percentage']

result = MessageBox.Show(
    f"Room Name: {name}\nPredicted Class: {predicted_class}\nConfidence: {confidence_percentage}\nDo you want to apply this to the Comments parameter?",
    "Confirmation",
    MessageBoxButtons.YesNo,
    MessageBoxIcon.Question
)

if result == DialogResult.Yes:
    transaction = DB.Transaction(doc, 'NUF application')
    try:
        transaction.Start()
        room = doc.GetElement(room_ref.ElementId)
        comment_parameter = room.LookupParameter('Comments')  # Adjust name as needed
        if comment_parameter:
            comment_parameter.Set(predicted_class)
            print("Comment updated successfully.")
        else:
            print("Comment parameter not found.")
        transaction.Commit()
    except Exception as e:
        print("Error during transaction:", e)
        transaction.RollBack()
else:
    print("Operation canceled by the user.")
