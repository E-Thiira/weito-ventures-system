import base64
from datetime import datetime

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class MpesaService:
    def __init__(self):
        self.base_url = settings.MPESA_BASE_URL.rstrip("/")
        self.session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "POST"),
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def _get_access_token(self) -> str:
        auth_string = f"{settings.MPESA_CONSUMER_KEY}:{settings.MPESA_CONSUMER_SECRET}"
        encoded_auth = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
        response = self.session.get(
            f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials",
            headers={"Authorization": f"Basic {encoded_auth}"},
            timeout=20,
        )
        response.raise_for_status()
        return response.json().get("access_token", "")

    def stk_push(self, *, phone: str, amount: str, account_reference: str, transaction_desc: str, callback_url: str):
        token = self._get_access_token()
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password_raw = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}"
        password = base64.b64encode(password_raw.encode("utf-8")).decode("utf-8")

        payload = {
            "BusinessShortCode": settings.MPESA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(float(amount)),
            "PartyA": phone,
            "PartyB": settings.MPESA_SHORTCODE,
            "PhoneNumber": phone,
            "CallBackURL": callback_url,
            "AccountReference": account_reference,
            "TransactionDesc": transaction_desc,
        }

        response = self.session.post(
            f"{self.base_url}/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
