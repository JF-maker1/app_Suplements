from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class ProcessingStatus(str, Enum):
    """Lifecycle status for the scanned entity."""
    NEW = "NEW"
    SCANNED = "SCANNED"
    PARSED = "PARSED"
    VERIFIED = "VERIFIED"

# NOTE: Removed default values to prevent protobuf schema errors in google-generativeai SDK

class ProductIdentity(BaseModel):
    full_name: str = Field(description="Přesný komerční název z obalu")
    brand: str = Field(description="Výrobce nebo značka")
    variant_sku: Optional[str] = Field(description="EAN nebo kód výrobce, je-li čitelný")
    category_inference: str = Field(description="Odvozená kategorie (např. 'Doplňky stravy')")

class PricingData(BaseModel):
    detected_price: Optional[float] = Field(description="Detekovaná číselná cena")
    currency_symbol: Optional[str] = Field(description="Symbol měny (např. Kč, €)")
    unit_price_string: Optional[str] = Field(description="Přepočet na jednotku (např. 100g)")

class NutritionalTable(BaseModel):
    energy_kcal: Optional[str] = Field(description="Energie v kcal")
    protein: Optional[str] = Field(description="Bílkoviny")
    carbohydrates: Optional[str] = Field(description="Sacharidy")
    fat: Optional[str] = Field(description="Tuky")

class CompositionAnalysis(BaseModel):
    ingredients_text_raw: str = Field(description="Kompletní text složení 'jak je' na obalu")
    ingredients_list: List[str] = Field(description="Rozparsovaný seznam ingrediencí")
    nutritional_table: NutritionalTable
    allergen_warning: List[str] = Field(description="Detekované alergeny")

class TechSpecs(BaseModel):
    net_quantity: Optional[str] = Field(description="Např. 500g, 90 kapslí")
    storage_conditions: Optional[str] = Field(description="Podmínky skladování")
    expiry_date_indicated: bool = Field(description="Zda je uveden datum expirace")

class MarketingContent(BaseModel):
    claims: List[str] = Field(description="Marketingová tvrzení (Bio, Vegan...)")
    description_short: Optional[str] = Field(description="Hlavní popisný text")

class ProductAnalysis(BaseModel):
    """Root model for Gemini 1.5 Flash structured output."""
    product_identity: ProductIdentity
    pricing_data: PricingData
    composition_analysis: CompositionAnalysis
    tech_specs: TechSpecs
    marketing_content: MarketingContent