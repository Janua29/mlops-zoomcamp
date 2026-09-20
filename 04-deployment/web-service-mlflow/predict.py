import os
import pickle

import mlflow
from flask import Flask, request, jsonify


#_______ Initial command of the course : use of AWS S3 bucket and MLFlow2.0 ________________

#RUN_ID = os.getenv('RUN_ID')
#logged_model = f's3://mlflow-models-alexey/1/{RUN_ID}/artifacts/model'--> mlflow 2.X
# logged_model = f'runs:/{RUN_ID}/model' --> mlflow 2.X
# model = mlflow.pyfunc.load_model(logged_model) --> mlflow 2.X


#_______ Command use when no docker container is used, and with MLflow 3.0 ________________

'''
mlflow.set_tracking_uri("http://127.0.0.1:5000")  #indique qu'il faut interroger le port 5000 du codespace. C'est le port réservé pour MLflow (mlflow est hébergé sur le codespace et utilise le port 5000 pour communiquer)
MODEL_URI = os.getenv('MODEL_URI', 'models:/m-5e276730f7004842b7c3a36ea11b5044')   # récupère la variable 'MODEL_URI' stocké par le shell via la commande écrit dans le terminal "export MODEL_URI='xxxx'"
# le deuxième arguùent de os.getenv est la valeur pardéfaut si la variable 'MODEL_URI' a un problème. Ici, 'models:/m-5e276730f7004842b7c3a36ea11b5044' est là où est stocké le model sur mlflow
model = mlflow.pyfunc.load_model(MODEL_URI). # on load le model depuis mlflow
'''

#_______ Command use when docker container is used, and with MLflow 3.0 ________________

MLFLOW_TRACKING_URI = os.getenv('MLFLOW_TRACKING_URI', 'http://127.0.0.1:5000')
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
MODEL_URI = os.getenv('MODEL_URI')
model = mlflow.pyfunc.load_model(MODEL_URI)

def prepare_features(ride):
    features = {}
    features['PU_DO'] = '%s_%s' % (ride['PULocationID'], ride['DOLocationID'])
    features['trip_distance'] = ride['trip_distance']
    return features


def predict(features):
    preds = model.predict(features)
    return float(preds[0])


app = Flask('duration-prediction')


@app.route('/predict', methods=['POST'])
def predict_endpoint():
    ride = request.get_json()

    features = prepare_features(ride)
    pred = predict(features)

    result = {
        'duration': pred,
        'model_version': MODEL_URI #RUN_ID
    }

    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=9696)
