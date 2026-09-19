import os
import pickle

import mlflow
from flask import Flask, request, jsonify


#RUN_ID = os.getenv('RUN_ID')

#logged_model = f's3://mlflow-models-alexey/1/{RUN_ID}/artifacts/model'--> mlflow 2.X
# logged_model = f'runs:/{RUN_ID}/model' --> mlflow 2.X
# model = mlflow.pyfunc.load_model(logged_model) --> mlflow 2.X


mlflow.set_tracking_uri("http://127.0.0.1:5000")
MODEL_URI = os.getenv('MODEL_URI', 'models:/m-5e276730f7004842b7c3a36ea11b5044')   # ton vrai URI
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
