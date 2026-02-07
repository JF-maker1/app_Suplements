from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator

# --- ENUMS ---
class ProcessingStatus(str, Enum):
    NEW = "NEW"
    SCANNED = "SCANNED"
    PARSED = "PARSED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"

# --- NESTED MODELS (JSONB Structures) ---

class Ingredient(BaseModel):
    model_config = ConfigDict(extra='ignore') 
    name: str = Field(description="Název účinné látky")
    amount: Optional[str] = Field(None, description="Množství na dávku (např. 500mg)")

class NutritionalInfo(BaseModel):
    model_config = ConfigDict(extra='ignore')
    # Validátor pro čištění "null" stringů v nutričních hodnotách
    @field_validator('*', mode='before')
    @classmethod
    def sanitize_strings(cls, v):
        if isinstance(v, str) and v.lower() in ('null', 'none', 'n/a', '', 'nan'):
            return None
        return v

    energy_kcal: Optional[str] = Field(None, description="Energie v kcal")
    protein: Optional[str] = Field(None, description="Bílkoviny")
    carbohydrates: Optional[str] = Field(None, description="Sacharidy")
    fat: Optional[str] = Field(None, description="Tuky")

class CompositionData(BaseModel):
    model_config = ConfigDict(extra='allow')
    active_ingredients: List[Ingredient] = Field(default_factory=list, description="Seznam účinných látek")
    excipients: List[str] = Field(default_factory=list, description="Pomocné látky")
    nutritional_table: Optional[NutritionalInfo] = Field(None, description="Nutriční hodnoty")
    allergen_warning: List[str] = Field(default_factory=list, description="Alergeny")

class ProductSpecs(BaseModel):
    model_config = ConfigDict(extra='allow')
    net_quantity: Optional[str] = Field(None, description="Obsah balení (g, ml, ks)")
    storage_conditions: Optional[str] = Field(None, description="Skladování")
    expiry_date_indicated: bool = Field(False, description="Datum spotřeby nalezeno")
    dosage: Optional[str] = Field(None, description="Doporučené dávkování")

class MarketingData(BaseModel):
    model_config = ConfigDict(extra='allow')
    claims: List[str] = Field(default_factory=list, description="Marketingová tvrzení")
    description: Optional[str] = Field(None, description="Popis produktu")

# --- CORE RESPONSE MODEL ---

class ProductAnalysisResult(BaseModel):
    """
    Hlavní model pro Gemini Structured Output.
    """
    model_config = ConfigDict(extra='ignore')

    # SANITIZER: Toto je ta klíčová ochrana databáze
    @field_validator('source_url', 'currency', 'category', 'full_name', mode='before')
    @classmethod
    def sanitize_strings(cls, v):
        # Pokud AI vrátí string "null", "None" nebo prázdný string, převedeme ho na None
        if isinstance(v, str) and v.lower() in ('null', 'none', 'n/a', '', 'nan'):
            return None
        return v

    full_name: str = Field(..., description="Přesný název produktu")
    brand: str = Field(..., description="Značka nebo výrobce")
    category: str = Field(..., description="Kategorie produktu")
    
    composition: CompositionData = Field(..., description="Složení a nutriční hodnoty")
    specs: ProductSpecs = Field(..., description="Technické specifikace")
    marketing: MarketingData = Field(..., description="Marketingová data")
    
    detected_price: Optional[float] = Field(None, description="Cena (číselná)")
    currency: Optional[str] = Field(None, description="Měna")
    source_url: Optional[str] = Field(None, description="Zdrojová URL (E-shop)")

# --- API DTOs ---

class ScanResponse(BaseModel):
    """
    FIXED: Added populate_by_name=True to allow instantiation via both field names (code) and aliases (DB).
    """
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True 
    )
    
    # Mapování: DB 'id' -> API 'scan_id'
    scan_id: str = Field(validation_alias="id")
    
    status: ProcessingStatus
    
    # Mapování: DB 'extra_metadata' -> API 'data'
    data: Optional[ProductAnalysisResult] = Field(validation_alias="extra_metadata")
    
    image_url: Optional[str]
    source_url: Optional[str] = None
    created_at: Optional[str] = None
    
    # I zde přidáme sanitizer pro jistotu, kdyby data šla přímo z DB "špinavá"
    @field_validator('source_url', mode='before')
    @classmethod
    def sanitize_source_url(cls, v):
        if isinstance(v, str) and v.lower() in ('null', 'none', ''):
            return None
        return v

class ScanUpdate(BaseModel):
    """
    Model pro PATCH requesty.
    """
    model_config = ConfigDict(extra='forbid')

    full_name: Optional[str] = None
    source_url: Optional[str] = None
    detected_price: Optional[float] = None
    currency: Optional[str] = None

    # Sanitizer pro URL
    @field_validator('source_url', mode='before')
    @classmethod
    def sanitize_url(cls, v):
        if isinstance(v, str) and v.lower() in ('null', 'none', ''):
            return None
        return v

    # FIX: Sanitizer pro Cenu (řeší 422 chybu při prázdném stringu)
    # TENTO VALIDÁTOR VÁM CHYBĚL
    @field_validator('detected_price', mode='before')
    @classmethod
    def sanitize_price(cls, v):
        # Frontend může poslat prázdný string "" pokud user smaže hodnotu.
        # Pydantic by to normálně odmítl (není float), proto to musíme převést na None.
        if v == "" or v is None:
            return None
        return v