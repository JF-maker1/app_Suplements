import asyncio
import sys
import os
import logging
from typing import List, Tuple

# Path Setup pro importy z 'app'
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_root = os.path.dirname(current_dir)
sys.path.append(backend_root)

from app.services.data_access import IntentService

# Logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("EVAL")

# --- TEST DATASET (Ground Truth) ---
# Format: (Query, Expected_Intent)
TEST_CASES: List[Tuple[str, str]] = [
    # 1. SQL_ANALYSIS (Hard Facts)
    ("Jaká je cena SuperKick?", "SQL_ANALYSIS"),
    ("Najdi nejlevnější protein", "SQL_ANALYSIS"),
    ("Srovnej ceny hořčíků", "SQL_ANALYSIS"),
    ("Kolik stojí produkt X?", "SQL_ANALYSIS"),
    ("Vypiš všechny produkty značky PowerGym", "SQL_ANALYSIS"),
    ("Který produkt má nejvíce bílkovin?", "SQL_ANALYSIS"),
    
    # 2. VECTOR_SEARCH (Needs, Effects, Vagueness)
    ("Něco na spaní", "VECTOR_SEARCH"),
    ("Jsem stále unavený", "VECTOR_SEARCH"),
    ("Hledám hořčík, který neprohání", "VECTOR_SEARCH"),
    ("Doporuč mi něco na klouby", "VECTOR_SEARCH"),
    ("Co je dobré na regeneraci po běhu?", "VECTOR_SEARCH"),
    ("Chci produkt s melatoninem", "VECTOR_SEARCH"),
    ("Vitamín C", "VECTOR_SEARCH"),
    
    # 3. GENERAL_CHAT (Off-topic, Greetings)
    ("Ahoj, kdo jsi?", "GENERAL_CHAT"),
    ("Jak se máš?", "GENERAL_CHAT"),
    ("Napiš mi básničku", "GENERAL_CHAT"),
    ("Co si myslíš o AI?", "GENERAL_CHAT"),
    ("Díky, to je vše", "GENERAL_CHAT")
]

async def run_eval():
    print("\n🧠 STARTING INTENT CLASSIFIER EVALUATION")
    print("=" * 60)
    
    service = IntentService()
    
    score = 0
    total = len(TEST_CASES)
    failed_cases = []

    for query, expected in TEST_CASES:
        print(f"🔹 Testing: '{query}'...", end=" ", flush=True)
        
        try:
            result = await service.classify_intent(query)
            predicted = result.get("intent", "UNKNOWN")
            
            if predicted == expected:
                print(f"✅ OK ({predicted})")
                score += 1
            else:
                print(f"❌ FAIL (Exp: {expected} | Got: {predicted})")
                failed_cases.append({
                    "query": query,
                    "expected": expected,
                    "got": predicted
                })
                
        except Exception as e:
            print(f"⚠️ ERROR: {e}")
            
    # --- REPORT ---
    accuracy = (score / total) * 100
    
    print("\n📊 EVALUATION REPORT")
    print("=" * 60)
    print(f"Total Tests: {total}")
    print(f"Passed:      {score}")
    print(f"Failed:      {total - score}")
    print(f"Accuracy:    {accuracy:.1f}%")
    
    if failed_cases:
        print("\n⚠️ FAILED CASES (Analyze for Prompt Engineering):")
        for case in failed_cases:
            print(f" - '{case['query']}' -> AI myslela '{case['got']}', ale mělo být '{case['expected']}'")
            
    print("=" * 60)
    
    if accuracy < 80:
        print("❌ FAILED: Accuracy below 80%. Prompt adjustment required.")
        sys.exit(1)
    else:
        print("✅ PASSED: Intent Classifier is robust.")

if __name__ == "__main__":
    asyncio.run(run_eval())