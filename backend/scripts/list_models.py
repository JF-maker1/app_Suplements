import sys
import os
import google.generativeai as genai
from dotenv import load_dotenv

# 1. SETUP
# Load .env manually if running as script
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_root = os.path.dirname(current_dir)
env_path = os.path.join(backend_root, '.env') # Assuming .env is in backend root or parent
if os.path.exists(env_path):
    load_dotenv(env_path)

def list_gemini_models():
    print("🔍 RDM DIAGNOSTIC: GEMINI MODEL CHECK")
    print("=" * 60)
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ CRITICAL: GOOGLE_API_KEY not found in environment.")
        sys.exit(1)

    # Obfuscated Key Print
    print(f"🔑 API Key detected: ...{api_key[-4:]}")

    try:
        genai.configure(api_key=api_key)
        
        print("📡 Contacting Google API...")
        models = list(genai.list_models())
        
        embedding_models = [m for m in models if 'embedContent' in m.supported_generation_methods]
        generation_models = [m for m in models if 'generateContent' in m.supported_generation_methods]

        print(f"✅ CONNECTION SUCCESSFUL. Found {len(models)} models total.")
        
        print("\n🧠 GENERATION MODELS:")
        for m in generation_models:
            print(f"   - {m.name} (Limit: {m.input_token_limit})")

        print("\n🧬 EMBEDDING MODELS:")
        for m in embedding_models:
            print(f"   - {m.name}")

    except Exception as e:
        print(f"❌ CONNECTION FAILED: {e}")
        print("   Hint: Check if your API Key has 'Generative Language API' enabled in Google Cloud Console.")
        sys.exit(1)

if __name__ == "__main__":
    list_gemini_models()