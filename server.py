import os
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from google import genai
from loader import Inbox 

# Load the .env file so the client can find GEMINI_API_KEY
load_dotenv()

# Initialize the new SDK client
client = genai.Client()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

inbox = Inbox("data") 

@app.get("/api/emails")
def get_processed_emails():
    results = []

    all_emails = list(inbox.emails())
    print(f"DEBUG: Found {len(all_emails)} emails in the inbox folder")

    for email in list(inbox.emails())[:10]:
        email_id = email.get("email_id")
        si_path = email["attachments"][0]
        si_raw_text = inbox.read_text(si_path)
        
        prompt = f"""
        Extract the following 7 fields from this shipping document:
        shipper, consignee, notify_party, port_of_loading, port_of_discharge, container_count, gross_weight_kg.
        
        Return ONLY a raw JSON object with these exact keys. Do not include markdown formatting.
        
        Document Text:
        {si_raw_text}
        """
        
        # The new generation syntax
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=prompt
        )
        
        extracted_data = json.loads(response.text)
        
        results.append({
            "id": email_id,
            "category": "document-comparison",
            "siData": extracted_data
        })
        
    return results