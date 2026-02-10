Pravidla pro přispívání do testů (Contributing)1. Zlaté Pravidlo: Mockujte Externí SlužbyNIKDY nevolejte reálné Google Gemini API v unit testech.Používejte unittest.mock nebo pytest-mock (fixture mocker).Pokud testujete logiku, která musí volat API, patří do sekce integration a musí běžet proti speciálnímu testovacímu projektu, ne produkci.2. Naming Conventions (Jmenné konvence)Soubory testů: test_<nazev_modulu>.pyFunkce testů: test_<co_testujeme>_<ocekavany_vysledek>Příklad: test_etl_process_happy_path nebo test_sql_injection_blocked3. Struktura Testu (AAA Pattern)Každý test by měl mít jasnou strukturu:Arrange (Příprava): Nastavení dat, mocků a fixtures.Act (Akce): Zavolání testované funkce.Assert (Ověření): Kontrola výsledku.def test_example(mocker):
    # ARRANGE
    mock_service = mocker.patch("app.services.MyService")
    
    # ACT
    result = perform_action()
    
    # ASSERT
    assert result == "Success"
    mock_service.assert_called_once()
4. Checklist před Commitem[ ] Všechny testy procházejí lokálně (pytest).[ ] Nový kód má odpovídající testy.[ ] Nepřidali jste žádné API klíče přímo do kódu (Hardcoded secrets).
