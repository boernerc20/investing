#!/usr/bin/env python3
"""
Debug Alpha Vantage API to see raw response
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('ALPHA_VANTAGE_API_KEY')

print("Alpha Vantage Debug")
print("=" * 70)
print(f"API Key: {api_key}")
print()

# Test request
url = 'https://www.alphavantage.co/query'
params = {
    'function': 'TIME_SERIES_DAILY_ADJUSTED',
    'symbol': 'SPY',
    'outputsize': 'compact',
    'apikey': api_key
}

print("Making request...")
response = requests.get(url, params=params, timeout=30)

print(f"Status Code: {response.status_code}")
print()
print("Response JSON:")
print("-" * 70)

import json
data = response.json()
print(json.dumps(data, indent=2)[:1000])  # First 1000 chars

print()
print("Keys in response:", list(data.keys()))

# Check for common issues
if 'Error Message' in data:
    print("\n❌ API Error:", data['Error Message'])
elif 'Note' in data:
    print("\n⚠️  Rate Limit:", data['Note'])
elif 'Information' in data:
    print("\n⚠️  API Message:", data['Information'])
elif 'Time Series (Daily)' in data:
    print("\n✓ Data received successfully!")
    print(f"  Days of data: {len(data['Time Series (Daily)'])}")
else:
    print("\n❓ Unexpected response format")
