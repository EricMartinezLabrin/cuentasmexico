import json
import requests


def send_push_notification(device_token, title, body, url=None, data={}):
    payload = {
        "to": device_token,
        "title": title,
        "body": body,
        "data": {
            "url": url,
            "data": data
        }
    }
    headers = {
        "Content-Type": "application/json"
    }
    response = requests.post(
        "https://exp.host/--/api/v2/push/send", data=json.dumps(payload), headers=headers)

    if response.status_code == 200:
        return f"Notification sent successfully {response}"
    else:
        return f"Notification failed with error code {response.status_code}"
