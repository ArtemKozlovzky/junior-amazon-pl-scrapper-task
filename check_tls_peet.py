#!/usr/bin/env python3
import requests
from curl_cffi import requests as curl_requests
import json

URL = "https://tls.peet.ws/api/all"

r1 = requests.get(URL)
print("requests")
print(json.dumps(r1.json(), ensure_ascii=False, indent=2))

r2 = curl_requests.get(URL, impersonate="chrome124")
print("curl_cffi")
print(json.dumps(r2.json(), ensure_ascii=False, indent=2))
