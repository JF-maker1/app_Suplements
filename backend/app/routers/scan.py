import os
import uuid
import logging
from typing import List, Optional
from tempfile import NamedTemporaryFile
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Path, Body
from starlette.concurrency import run_in_threadpool

from app.services.gemini_service import GeminiService
from app.services.db import SupabaseService
from app.schemas import ScanResponse, ProcessingStatus, ProductAnalysisResult, ScanUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scan", tags=["Scanning"])

# Services Initialization
gemini_service = GeminiService()
db_service = SupabaseService()

# --- SPRINT 04 NEW ENDPOINTS ---

@router.get("/list", response_model=List[ScanResponse])
async def list_scans(
    q: Optional[str] = Query(None, description="Fulltext search query (název produktu)"),
    source_url: Optional[str] = Query(None, description="Filtrování podle přesné URL zdroje"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimální cena"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximální cena"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    [Non-blocking] Načte seznam scanů s filtrováním.
    Implements FR-01: Advanced Search API.
    """
    try:
        scans = await run_in_threadpool(
            db_service.get_scans,
            limit=limit,
            offset=offset,
            search_query=q,
            source_url=source_url,
            min_price=min_price,
            max_price=max_price
        )
        return scans
    except Exception as e:
        logger.error(f"List scans failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch scans")

@router.patch("/{scan_id}", response_model=ScanResponse)
async def update_scan(
    scan_id: str = Path(..., description="UUID scanu"),
    update_data: ScanUpdate = Body(..., description="Data k aktualizaci")
):
    """
    [Non-blocking] Aktualizuje metadata scanu (název, cena, URL).
    Implements FR-04: Data Mutation.
    CRITICAL: Uses exclude_unset=True to prevent 'Null Trap'.
    """
    try:
        # 1. Prepare data (Filter out None/Unset values)
        # Toto zajistí, že pokud pošlu jen {"detected_price": 200},
        # ostatní pole jako full_name zůstanou nedotčena.
        clean_data = update_data.model_dump(exclude_unset=True)
        
        if not clean_data:
            raise HTTPException(status_code=400, detail="No valid fields provided for update")

        # 2. Execute Update via Service Layer
        updated_record = await run_in_threadpool(
            db_service.update_scan_data,
            scan_id=scan_id,
            update_data=clean_data
        )

        if not updated_record:
            raise HTTPException(status_code=404, detail="Scan not found or update failed")

        return updated_record

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Update scan {scan_id} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- EXISTING ENDPOINTS (Sprint 01-03) ---

@router.post("/analyze", response_model=ScanResponse)
async def analyze_product(
    file: UploadFile = File(...),
):
    """
    Robust Async Endpoint Implementation:
    1. Async Read (Non-blocking).
    2. Threadpool Upload.
    3. EXTENDED TRANSACTION SCOPE:
       - If AI Analysis fails -> Rollback (Delete Image).
       - If DB Insert fails -> Rollback (Delete Image).
    """
    
    # 1. Input Validation
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Generate Identifiers
    file_ext = file.filename.split('.')[-1] if '.' in file.filename else "jpg"
    unique_filename = f"scan_{uuid.uuid4()}.{file_ext}"
    temp_file = NamedTemporaryFile(delete=False, suffix=f".{file_ext}")
    
    try:
        # A) Read Content (Native Async)
        content = await file.read()
        
        # B) Save to Temp (Sync - Fast Disk I/O)
        with open(temp_file.name, "wb") as f:
            f.write(content)
            
        # ---------------------------------------------------------
        # STEP 1: UPLOAD IMAGE (Blocking I/O -> Threadpool)
        # ---------------------------------------------------------
        logger.info("1. Uploading image to Supabase (Threadpool)...")
        # Pokud toto selže, nic se neděje (nic není uloženo), vyhodí to error a konec.
        image_url = await run_in_threadpool(
            db_service.upload_file,
            file_bytes=content,
            file_name=unique_filename,
            content_type=file.content_type
        )

        # START OF ATOMIC TRANSACTION
        # Od teď, pokud cokoliv selže, musíme smazat obrázek (Rollback).
        try:
            # ---------------------------------------------------------
            # STEP 2: ANALYZE (Native Async)
            # ---------------------------------------------------------
            logger.info("2. Analyzing with Gemini (Async)...")
            analysis_result: ProductAnalysisResult = await gemini_service.analyze_image(
                temp_file.name, 
                file.content_type
            )

            # ---------------------------------------------------------
            # STEP 3: SAVE DATA (Blocking I/O -> Threadpool)
            # ---------------------------------------------------------
            logger.info("3. Saving result to DB (Threadpool)...")
            
            db_payload = {
                "status": ProcessingStatus.PARSED.value,
                "full_name": analysis_result.full_name,
                "image_url": image_url,
                "extra_metadata": analysis_result.model_dump(mode='json'),
                # SPRINT 04: Pokud AI vrátí source_url (zatím ne, ale model to má), uložíme ho.
                "source_url": analysis_result.source_url 
            }

            db_record = await run_in_threadpool(
                db_service.insert_scan_data,
                scan_data=db_payload
            )
            
            logger.info(f"✅ Transaction Complete. ID: {db_record.get('id')}")
            
            return ScanResponse(
                scan_id=str(db_record.get("id")),
                status=ProcessingStatus.PARSED,
                data=analysis_result,
                image_url=image_url,
                source_url=db_payload.get("source_url")
            )

        except Exception as transaction_error:
            # -----------------------------------------------------
            # STEP 4: GLOBAL ROLLBACK
            # -----------------------------------------------------
            logger.error(f"Transaction Failed ({transaction_error}). executing Rollback...")
            await run_in_threadpool(
                db_service.delete_file,
                file_name=unique_filename
            )
            raise transaction_error

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Critical System Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        # Cleanup local temp file
        if os.path.exists(temp_file.name):
            os.remove(temp_file.name)