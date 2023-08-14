import requests
from flask_app import _get_config


url = 'http://{}:{}'.format(_get_config.REMOTE_HOST, _get_config.REMOTE_PORT)
print(url)


def send_train_request(mid, version, unit):
    try:
        token_url = url + '/api/token'
        model_url = url + '/api/model/train_remote'
        headers = {
        "Content-Type":"application/json",
        "unit": str(unit)
        }
        token_data = {
        "username": 1,
        "password": 1
        }
        response = requests.post(url=token_url, headers=headers, json=token_data)
        token = response.json()['data']['token']
        print(token)
        model_data = {
            "mid": mid,
            "version": version
        }
        headers['Authorization'] = 'Bearer '+token
        response = requests.post(url=model_url, headers=headers, json=model_data)
        status = response.json()['status']
        return status
    except:
        return False


def send_stop_request(mid, version, unit):
    try:
        token_url = url + '/api/token'
        model_url = url + '/api/model/train_remote?mid={}&version={}'.format(str(mid), str(version))
        headers = {
        "Content-Type":"application/json",
        "unit": str(unit)
        }
        token_data = {
        "username": 1,
        "password": 1
        }
        response = requests.post(url=token_url, headers=headers, json=token_data)
        token = response.json()['data']['token']
        print(token)
        headers['Authorization'] = 'Bearer '+token
        response = requests.delete(url=model_url, headers=headers)
        print(response.json())
        status = response.json()['status']
        return status
    except:
        return False
    
# print(send_train_request(60,1,3))
# print(send_stop_request(55,1,3))