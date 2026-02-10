import os
import sys
from pathlib import Path

def check_artifact(path: Path) -> bool:
    if path.exists():
        print(f"✅ FOUND: {path.name}")
        return True
    else:
        print(f"❌ MISSING ARTIFACT: {path}")
        return False

def run_pre_flight_check():
    print("="*60)
    print("🚀 RDM DEPLOYMENT BRIDGE: PRE-FLIGHT CHECK")
    print("="*60)
    
    # 1. Resolve Paths (Relative to this script location: backend/tests/)
    # Structure:
    #   backend/
    #     requirements.txt
    #     tests/
    #       simulation_runner.py (WE ARE HERE)
    #       conftest.py
    #       unit/
    #         test_schemas.py
    #       integration/
    #         test_etl_service.py
    
    current_dir = Path(__file__).parent.resolve()
    backend_root = current_dir.parent
    
    required_artifacts = [
        backend_root / "requirements.txt",
        current_dir / "conftest.py",
        current_dir / "unit" / "test_schemas.py",
        current_dir / "integration" / "test_etl_service.py"
    ]

    # 2. Validation Loop
    missing_count = 0
    for artifact in required_artifacts:
        if not check_artifact(artifact):
            missing_count += 1

    print("-" * 60)
    
    # 3. Final Decision
    if missing_count == 0:
        print("✅ READY FOR DEPLOYMENT. Run 'pytest' now.")
        sys.exit(0)
    else:
        print(f"❌ CRITICAL FAILURE: {missing_count} artifacts missing.")
        print("   Consult RDM_EVOLUTION_REPORT.md for recovery.")
        sys.exit(1)

if __name__ == "__main__":
    run_pre_flight_check()