import os
import sys
import argparse
import json
import time
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from supabase import create_client, Client
from models import ProductAnalysis, ProcessingStatus

# --- INIT ---
load_dotenv()

# Env Validation
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not all([SUPABASE_URL, SUPABASE_KEY, GOOGLE_API_KEY]):
    print("❌ ERROR: Missing environment variables in .env")
    sys.exit(1)

# Client Setup
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GOOGLE_API_KEY)

# ZMĚNA: Definice prioritní rotace modelů
# 1. Gemini 2.0 Flash (Rychlý, stabilní)
# 2. Gemini 2.5 Flash (Nejnovější, experimentální)
# 3. Gemini Flash Latest (Obecný alias pro fallback)
MODEL_ROTATION = [
    "models/gemini-2.0-flash",
    "models/gemini-2.5-flash",
    "models/gemini-flash-latest"
]

def list_available_models():
    """DEBUG: Vypíše dostupné modely pro tento API klíč."""
    print("🔍 Checking available Gemini models...")
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"   - {m.name}")
    except Exception as e:
        print(f"⚠️ Could not list models: {e}")

def upload_image(file_path: str, file_name: str) -> str:
    """Uploads image to Supabase Storage 'raw-scans'."""
    bucket_name = "raw-scans"
    try:
        with open(file_path, 'rb') as f:
            response = supabase.storage.from_(bucket_name).upload(
                path=file_name,
                file=f,
                file_options={"content-type": "image/jpeg", "upsert": "true"}
            )
        print(f"✅ Image uploaded to Supabase Storage: {bucket_name}/{file_name}")
        return file_name
    except Exception as e:
        print(f"⚠️ Storage Upload Warning: {e}")
        return "local_only_upload_failed"

def analyze_image_with_gemini(image_path: str) -> ProductAnalysis:
    """Sends image to Gemini using a rotation of models until one succeeds."""
    print(f"🤖 Uploading {image_path} to Gemini File API...")
    
    # 1. Upload souboru (jednou pro všechny pokusy)
    try:
        sample_file = genai.upload_file(path=image_path, display_name="Product Scan")
        
        # Čekání na zpracování
        while sample_file.state.name == "PROCESSING":
            time.sleep(1)
            sample_file = genai.get_file(sample_file.name)
        
        if sample_file.state.name == "FAILED":
            raise ValueError("File upload to Gemini failed state.")
            
    except Exception as e:
        print(f"❌ Critical Error during File Upload: {e}")
        sys.exit(1)

    last_error = None
    success_data = None

    # 2. Rotace modelů (Pokus o generování)
    print(f"🔄 Starting analysis loop. Candidates: {len(MODEL_ROTATION)}")
    
    for model_name in MODEL_ROTATION:
        print(f"\n👉 Attempting with model: {model_name}...")
        
        try:
            model = genai.GenerativeModel(model_name)
            
            prompt = """
            Analyze this product image. Extract all technical, pricing, and composition data exactly according to the schema.
            If a field is not visible, use null.
            Focus on high precision for OCR of ingredients.
            """
            
            # Volání API
            result = model.generate_content(
                [sample_file, prompt],
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=ProductAnalysis
                )
            )
            
            # Pokud API neselhalo, zkusíme parsovat JSON
            data = json.loads(result.text)
            success_data = ProductAnalysis(**data)
            
            print(f"✅ SUCCESS with model: {model_name}")
            break # Vyskočit z cyklu, máme výsledek
            
        except Exception as e:
            print(f"⚠️ Model {model_name} failed. Error: {e}")
            last_error = e
            continue # Zkusit další model v seznamu

    # 3. Úklid (smazání souboru z Google serverů)
    try:
        sample_file.delete()
    except:
        pass

    # 4. Vyhodnocení výsledku
    if success_data:
        return success_data
    else:
        print("\n❌ CRITICAL: All models in rotation failed.")
        if last_error:
            print(f"Last captured error: {last_error}")
        sys.exit(1)

def save_result_to_db(data: ProductAnalysis, image_ref: str):
    """Inserts structured data into Supabase DB."""
    payload = {
        "status": ProcessingStatus.PARSED.value,
        "raw_json": data.model_dump(mode='json'),
        "image_ref": image_ref,
        "product_name": data.product_identity.full_name,
        "scanned_at": "now()"
    }
    
    try:
        response = supabase.table("scans").insert(payload).execute()
        print("✅ Data persisted to Supabase DB (Table: 'scans').")
    except Exception as e:
        print(f"⚠️ DB Insert Error: {e}")

def main():
    parser = argparse.ArgumentParser(description="AI Product Scraper - Vision PoC")
    parser.add_argument("--image", required=True, help="Path to local image file")
    args = parser.parse_args()
    
    if not os.path.exists(args.image):
        print(f"❌ Error: File {args.image} not found.")
        sys.exit(1)

    # List models (DEBUG info)
    # list_available_models()
        
    image_filename = os.path.basename(args.image)
    image_ref = upload_image(args.image, image_filename)
    
    # Spuštění s rotací
    product_data = analyze_image_with_gemini(args.image)
    
    print("\n" + "="*40)
    print("🔍 GEMINI VISION ANALYSIS RESULT")
    print("="*40)
    print(json.dumps(product_data.model_dump(), indent=2, ensure_ascii=False))
    print("="*40 + "\n")
    
    save_result_to_db(product_data, image_ref)

if __name__ == "__main__":
    main()