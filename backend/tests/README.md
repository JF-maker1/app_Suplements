RDM SUPERSPORT - Test Suite Documentation🚀 Rychlý Start (Quick Start)Jak spustit testy lokálněPředpoklad: Máte nainstalované závislosti (pip install -r requirements.txt).Spuštění VŠECH testů:cd backend
pytest
Spuštění pouze rychlých Unit testů (bez DB):pytest tests/unit/
Spuštění integračních testů (vyžaduje DB):pytest tests/integration/
Spuštění testů s Coverage reportem:pytest --cov=app --cov-report=term-missing
🛡️ Bezpečnostní Strategie "Poison Pill"V tomto projektu používáme striktní bezpečnostní mechanismus nazvaný Poison Pill, který zabraňuje nechtěnému použití produkčních API klíčů během testování.Jak to funguje:V souboru conftest.py je fixture poison_google_credentials, která má autouse=True.Tato fixture automaticky přepíše proměnné prostředí GOOGLE_API_KEY na hodnotu "TEST_GUARD_KEY_POISONED".Pokud se jakýkoli test pokusí zavolat reálné Google API bez "mockování" (simulace), volání okamžitě selže na chybu autentizace.Důsledek: Nikdy nemůže dojít k vyčerpání produkční kvóty nebo úniku dat omylem.📁 Struktura Testůtests/
├── unit/               # Izolované testy (bez DB, bez sítě)
│   ├── test_security.py       # SQL Injection, validace
│   └── test_orchestrator.py   # Logika routování
│
├── integration/        # Testy služeb s reálnou DB (Supabase Test Instance)
│   ├── test_etl_pipeline.py   # Upload -> Vision -> DB
│   ├── test_vector_service.py # Semantic search
│   └── test_sql_service.py    # NL to SQL
│
├── fixtures/           # Sdílená testovací data (zatím v conftest.py)
└── conftest.py         # Globální konfigurace a Poison Pill
🔧 Řešení Problémů (Troubleshooting)Chyba: google.api_core.exceptions.InvalidArgument: 400 API key not valid.Příčina: Váš test se snaží volat reálné API, ale Poison Pill ho zablokoval.Řešení: Musíte použít mock (např. unittest.mock.patch) pro simulaci odpovědi od Google API. Podívejte se do tests/unit/test_orchestrator.py na příklad.Chyba: OperationalError: connection refusedPříčina: Integrační testy nemají přístup k databázi.Řešení: Ujistěte se, že máte nastavené SUPABASE_URL a SUPABASE_KEY (pro testovací instanci) v .env souboru nebo v prostředí.
