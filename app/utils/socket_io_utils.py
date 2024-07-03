import requests
import json

def get_session_id():
    url = "http://localhost:3001/api/v1/typebots/clxkpr0gv000a3mjtrp5zvjej/preview/startChat"
    payload = {}
    headers = {
        'Authorization': 'Bearer 99vV3HcU34hwpDuxrtNoOd0q'
        }
    response = requests.request("POST", url, headers=headers, data=payload)
    parsed_data = json.loads(response.text)
    return parsed_data['sessionId']



def typebot_chat_flow(message:str, sessionId:str):
    url = f"http://localhost:3001/api/v1/sessions/{sessionId}/continueChat"
    
    payload = json.dumps({
      "message": message
    })
    headers = {
      'Content-Type': 'application/json'
    }
    
    response = requests.request("POST", url, headers=headers, data=payload)
    print(response.text)




typebot_chat_flow("chayan@aplusolution.com","cly650u5z000chgr8mpk5s0i7")