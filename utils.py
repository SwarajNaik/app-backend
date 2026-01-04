import requests
from dotenv import load_dotenv
import os
import random
from fastapi import Header, HTTPException
import base64

load_dotenv()

import random
import os
import requests

def send_otp(phone_number):
    try:
        otp = random.randint(100000, 999999)
        url = "https://www.fast2sms.com/dev/bulkV2"
        
        querystring = {
            "authorization": os.getenv('OTP_AUTH_TOKEN'),
            "variables_values": otp,
            "route": "otp",
            "numbers": phone_number
        }

        headers = {
            'cache-control': "no-cache"
        }

        response = requests.request("GET", url, headers=headers, params=querystring)
        
        if response.status_code == 200:
            response_data = response.json()
            
            # If the response contains 'request_id', return it as the verification ID
            if 'request_id' in response_data:
                return response_data['request_id'], otp
            else:
                raise Exception("Request ID not found in the response")
        else:
            raise Exception("Failed to send OTP, status code: {}".format(response.status_code))
    
    except Exception as e:
        raise e


async def verify_admin_token(token: str = Header(None, alias="TOKEN")):
    """FastAPI dependency to verify admin token from TOKEN header."""
    from controllers.admin_controller import auth_middleware
    # auth_middleware raises HTTPException if invalid, so just call it
    auth_middleware(token)
    return True