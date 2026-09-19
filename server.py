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
    
    # 1. Filter for emails that actually have at least 2 attachments
    emails_with_docs = [e for e in all_emails if e.get("attachments") and len(e.get("attachments")) >= 2]
    
    for email in emails_with_docs[:10]:
        email_id = email.get("email_id")
        attachments = email.get("attachments", [])
        
        try:
            # 2. Sort the attachments to ensure we know which is which
            si_filename = next((f for f in attachments if "_SI" in f), attachments[0])
            bl_filename = next((f for f in attachments if "_BL" in f), attachments[1])
            
            full_si_path = os.path.join("data", "attachments", si_filename)
            full_bl_path = os.path.join("data", "attachments", bl_filename)
            
            # 3. Helper function to read different file types
            def extract_content(filename, full_path):
                if filename.lower().endswith('.txt'):
                    return inbox.read_text(filename)
                elif filename.lower().endswith('.xlsx'):
                    df = pd.read_excel(full_path)
                    return df.to_csv(index=False)
                elif filename.lower().endswith('.pdf'):
                    return client.files.upload(file=full_path)
                return ""

            si_content = extract_content(si_filename, full_si_path)
            bl_content = extract_content(bl_filename, full_bl_path)
            
            # 4. The Dual-Document Prompt
            prompt = """
            You are an expert logistics document verifier. 
            I will provide a Shipping Instruction (SI) and a Bill of Lading (BL).
            
            Extract the following 7 fields from BOTH documents:
            shipper, consignee, notify_party, port_of_loading, port_of_discharge, container_count, gross_weight_kg.
            
            Compare the extracted fields. If the information logically matches, set the status to "MATCH". If there is a discrepancy, set the status to "MISMATCH".
            
            Return ONLY a raw JSON object in this exact format. Do not include markdown formatting:
            {
              "fields": {
                "shipper": {"si": "...", "bl": "...", "status": "MATCH"},
                "consignee": {"si": "...", "bl": "...", "status": "MISMATCH"},
                "notify_party": {"si": "...", "bl": "...", "status": "MATCH"},
                "port_of_loading": {"si": "...", "bl": "...", "status": "MATCH"},
                "port_of_discharge": {"si": "...", "bl": "...", "status": "MATCH"},
                "container_count": {"si": "...", "bl": "...", "status": "MATCH"},
                "gross_weight_kg": {"si": "...", "bl": "...", "status": "MATCH"}
              }
            }
            """
            
            # 5. Send both documents and the prompt to the working model
            response = client.models.generate_content(
                model='gemini-1.5-flash-8b', 
                contents=[
                    prompt, 
                    "\n--- SI DOCUMENT ---\n", si_content, 
                    "\n--- BL DOCUMENT ---\n", bl_content
                ]
            )
            
            clean_text = response.text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text.replace("```json", "").replace("```", "").strip()
                
            extracted_data = json.loads(clean_text)
            
            results.append({
                "id": email_id,
                "category": "document-comparison",
                "comparisonData": extracted_data
            })
            
        except Exception as e:
            import traceback
            print(f"FAILED on {email_id}.")
            print(traceback.format_exc())
            
    return results