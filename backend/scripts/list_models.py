import sys
import os
import google.generativeai as genai

# 1. PATH SETUP (To load app.config)
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_root = os.path.dirname(current_dir)
sys.path.append(backend_root)

# 2. IMPORTS
try:
    from app.config import settings
except ImportError as e:
    print(f"❌ CRITICAL IMPORT ERROR: {e}")
    sys.exit(1)

def list_embedding_models():
    print("🔍 AUTHENTICATING WITH GOOGLE GEN AI...")
    
    # Check Key
    if not settings.GOOGLE_API_KEY:
        print("❌ Error: No GOOGLE_API_KEY found in settings.")
        return

    # Configure
    genai.configure(api_key=settings.GOOGLE_API_KEY)

    print("📡 FETCHING AVAILABLE MODELS...")
    print("-" * 60)
    
    try:
        count = 0
        # Iterate over all models available to the key
        for m in genai.list_models():
            # Check specifically for Embedding capability
            if 'embedContent' in m.supported_generation_methods:
                print(f"✅ MODEL: {m.name}")
                print(f"   • Description: {m.description}")
                print(f"   • Input Limit: {m.input_token_limit}")
                print("-" * 60)
                count += 1
        
        if count == 0:
            print("⚠️ No models found that support 'embedContent'.")
            print("   Possible Cause: API Key restrictions or Region lock.")
        else:
            print(f"\n✨ Total Embedding Models Available: {count}")

    except Exception as e:
        print(f"❌ CRITICAL ERROR calling list_models(): {e}")

if __name__ == "__main__":
    list_embedding_models()