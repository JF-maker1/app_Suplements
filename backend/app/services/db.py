import logging
import sys
from typing import Dict, Any, Optional, List
from supabase import create_client, Client
from app.config import settings

logger = logging.getLogger(__name__)

class SupabaseService:
    def __init__(self):
        # 1. FAIL-FAST VALIDATION (Boot Check)
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            logger.critical("❌ CRITICAL: Missing SUPABASE_URL or SUPABASE_KEY in environment.")
            sys.exit(1)
            
        self.url = settings.SUPABASE_URL
        self.key = settings.SUPABASE_KEY
        self.bucket = settings.SUPABASE_BUCKET
        
        try:
            self.client: Client = create_client(self.url, self.key)
            logger.info("✅ Supabase Client initialized successfully.")
        except Exception as e:
            logger.critical(f"❌ Failed to initialize Supabase Client: {e}")
            sys.exit(1)

    # NOTE: Metody jsou SYNCHRONNÍ (Blocking I/O).
    # V routeru (scan.py) jsou volány přes run_in_threadpool.

    def upload_file(self, file_bytes: bytes, file_name: str, content_type: str) -> str:
        """[Blocking I/O] Uploads file to Supabase Storage."""
        try:
            logger.info(f"Uploading file to storage: {file_name}")
            self.client.storage.from_(self.bucket).upload(
                path=file_name,
                file=file_bytes,
                file_options={"content-type": content_type, "upsert": "false"}
            )
            return self.client.storage.from_(self.bucket).get_public_url(file_name)
        except Exception as e:
            logger.error(f"❌ Upload failed: {e}")
            raise e

    def delete_file(self, file_name: str):
        """[Blocking I/O] Rollback method."""
        try:
            self.client.storage.from_(self.bucket).remove([file_name])
            logger.warning(f"⚠️ Rollback executed: Deleted {file_name}")
        except Exception as e:
            logger.error(f"❌ Rollback failed for {file_name}: {e}")

    def insert_scan_data(self, scan_data: Dict[str, Any]) -> Dict[str, Any]:
        """[Blocking I/O] Inserts metadata into 'scans' table."""
        try:
            logger.info(f"Inserting DB record for: {scan_data.get('full_name')}")
            response = self.client.table("scans").insert(scan_data).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            else:
                raise ValueError("DB Insert returned no data.")
        except Exception as e:
            logger.error(f"❌ DB Insert failed: {e}")
            raise e

    # --- SPRINT 04 NEW METHODS (Validated against Snapshot) ---

    def get_scans(self, 
                  limit: int = 20, 
                  offset: int = 0, 
                  search_query: Optional[str] = None,
                  source_url: Optional[str] = None,
                  min_price: Optional[float] = None,
                  max_price: Optional[float] = None
                  ) -> List[Dict[str, Any]]:
        """
        [Blocking I/O] Fetches scans with dynamic filtering.
        Implements FR-01: Advanced Search API.
        """
        try:
            # 1. Base Query
            query = self.client.table("scans").select("*")

            # 2. Dynamic Filters
            if source_url:
                query = query.eq("source_url", source_url)
            
            if search_query:
                # Fulltext search nad názvem (case-insensitive)
                query = query.ilike("full_name", f"%{search_query}%")
                
            # Filtrování nad JSONB (extra_metadata -> detected_price)
            if min_price is not None:
                query = query.gte("extra_metadata->detected_price", min_price)
            
            if max_price is not None:
                query = query.lte("extra_metadata->detected_price", max_price)

            # 3. Sorting & Pagination
            query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
            
            # 4. Execute
            response = query.execute()
            return response.data if response.data else []

        except Exception as e:
            logger.error(f"❌ Fetch Scans failed: {e}")
            raise e

    def update_scan_data(self, scan_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        [Blocking I/O] Updates a scan record.
        Handles merging of top-level columns and JSONB data to prevent data loss.
        """
        if not update_data:
            return None

        try:
            logger.info(f"Updating scan {scan_id} with keys: {list(update_data.keys())}")
            
            # 1. Split data into Top-Level Columns vs JSONB Updates
            top_level_fields = ["full_name", "source_url", "status"]
            db_payload = {}
            json_updates = {}

            for key, value in update_data.items():
                if key in top_level_fields:
                    db_payload[key] = value
                elif key in ["detected_price", "currency"]:
                    # Price/Currency are stored inside extra_metadata in current architecture
                    json_updates[key] = value
                else:
                    logger.warning(f"Ignored unknown field in update: {key}")

            # 2. JSONB Merge Logic (Safety)
            if json_updates:
                current_record = self.client.table("scans").select("extra_metadata").eq("id", scan_id).single().execute()
                if current_record.data:
                    current_metadata = current_record.data.get("extra_metadata", {}) or {}
                    current_metadata.update(json_updates) # Merge changes
                    db_payload["extra_metadata"] = current_metadata
            
            # 3. Execute Update
            if db_payload:
                response = self.client.table("scans").update(db_payload).eq("id", scan_id).execute()
                return response.data[0] if response.data else None
            
            return None

        except Exception as e:
            logger.error(f"❌ Update Scan failed: {e}")
            raise e