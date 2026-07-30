import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union
from certification.v90_schema import V90CertificationRecord

AGRIBRAIN_ROOT = Path(__file__).resolve().parents[1]
V90_CERT_ROOT = AGRIBRAIN_ROOT / "artifacts" / "v90_certifications"

def validate_safe_id(val: str, name: str) -> None:
    """
    Validates that the ID is safe and does not contain directory traversal,
    absolute paths, path separators, empty IDs, or file extensions.
    """
    if not val or not isinstance(val, str):
        raise ValueError(f"Empty or invalid type for {name}")
    
    # Check for empty/whitespace only
    if not val.strip():
        raise ValueError(f"Whitespace-only {name}")

    # Prevent directory traversal and file extensions
    if ".." in val or "." in val:
        raise ValueError(f"Path traversal or file extension detected in {name}: '{val}'")
    
    # Prevent absolute paths on Unix or Windows
    if val.startswith("/") or val.startswith("\\") or (len(val) > 1 and val[1] == ":"):
        raise ValueError(f"Absolute path detected in {name}: '{val}'")
        
    # Prevent path separators
    if "/" in val or "\\" in val:
        raise ValueError(f"Path separator detected in {name}: '{val}'")

def get_certification_paths(
    certification_id: str,
    plot_id: str,
    variable: str,
    cert_root: Optional[Union[str, Path]] = None
) -> Dict[str, Path]:
    """
    Validates IDs and returns paths for active record, index, and revoked archive.
    """
    validate_safe_id(certification_id, "certification_id")
    validate_safe_id(plot_id, "plot_id")
    validate_safe_id(variable, "variable")
    
    root = Path(cert_root) if cert_root else V90_CERT_ROOT
    
    records_dir = root / "records"
    revoked_dir = root / "revoked"
    
    return {
        "root": root,
        "records_dir": records_dir,
        "revoked_dir": revoked_dir,
        "record_path": records_dir / f"{certification_id}.json",
        "revoked_path": revoked_dir / f"{certification_id}.json",
        "index_path": root / "index.jsonl"
    }

class V90Storage:
    def __init__(self, cert_root: Optional[Union[str, Path]] = None):
        self.cert_root = Path(cert_root) if cert_root else V90_CERT_ROOT

    def save_record(self, record: V90CertificationRecord) -> None:
        """
        Saves a certification record to active records and logs to index.jsonl.
        """
        paths = get_certification_paths(
            record.certification_id,
            record.plot_id,
            record.variable,
            cert_root=self.cert_root
        )
        
        # Ensure directories exist
        paths["records_dir"].mkdir(parents=True, exist_ok=True)
        paths["root"].mkdir(parents=True, exist_ok=True)
        
        # Save JSON file atomically
        record_data = record.to_dict()
        temp_record_path = paths["record_path"].with_suffix(".json.tmp")
        with open(temp_record_path, "w", encoding="utf-8") as f:
            json.dump(record_data, f, indent=2, sort_keys=True)
        os.replace(temp_record_path, paths["record_path"])
            
        # Log to index.jsonl atomically
        log_entry = {
            "event": "save",
            "certification_id": record.certification_id,
            "plot_id": record.plot_id,
            "variable": record.variable,
            "status": record.status,
            "certified_at": record.certified_at,
            "certification_hash": record.certification_hash,
            "certification_instance_hash": record.certification_instance_hash
        }
        
        lines = []
        if paths["index_path"].exists():
            with open(paths["index_path"], "r", encoding="utf-8") as f:
                lines = f.readlines()
        lines.append(json.dumps(log_entry) + "\n")
        
        temp_index_path = paths["index_path"].with_suffix(".jsonl.tmp")
        with open(temp_index_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        os.replace(temp_index_path, paths["index_path"])

    def archive_revoked_record(self, record: V90CertificationRecord) -> None:
        """
        Moves a record to revoked folder, updates active record status or removes it, and logs to index.jsonl.
        """
        import hashlib
        
        # Force status to revoked
        record.status = "revoked"
        
        # Calculate a deterministic revocation_event_hash
        revocation_content = {
            "certification_id": record.certification_id,
            "revoked_at": record.revoked_at,
            "revocation_reason": record.revocation_reason,
            "certification_hash": record.certification_hash
        }
        revocation_event_hash = hashlib.sha256(json.dumps(revocation_content, sort_keys=True).encode("utf-8")).hexdigest()
        record.revocation_event_hash = revocation_event_hash
        
        record.certification_instance_hash = record.calculate_certification_instance_hash()
        
        paths = get_certification_paths(
            record.certification_id,
            record.plot_id,
            record.variable,
            cert_root=self.cert_root
        )
        
        paths["revoked_dir"].mkdir(parents=True, exist_ok=True)
        
        # Save in revoked directory atomically
        record_data = record.to_dict()
        temp_revoked_path = paths["revoked_path"].with_suffix(".json.tmp")
        with open(temp_revoked_path, "w", encoding="utf-8") as f:
            json.dump(record_data, f, indent=2, sort_keys=True)
        os.replace(temp_revoked_path, paths["revoked_path"])
            
        # Remove from active records if it exists
        if paths["record_path"].exists():
            paths["record_path"].unlink()
            
        # Log to index.jsonl atomically
        log_entry = {
            "event": "revoke",
            "certification_id": record.certification_id,
            "plot_id": record.plot_id,
            "variable": record.variable,
            "status": "revoked",
            "revoked_at": record.revoked_at,
            "revocation_reason": record.revocation_reason,
            "revocation_event_hash": revocation_event_hash,
            "certification_hash": record.certification_hash,
            "certification_instance_hash": record.certification_instance_hash
        }
        
        lines = []
        if paths["index_path"].exists():
            with open(paths["index_path"], "r", encoding="utf-8") as f:
                lines = f.readlines()
        lines.append(json.dumps(log_entry) + "\n")
        
        temp_index_path = paths["index_path"].with_suffix(".jsonl.tmp")
        with open(temp_index_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        os.replace(temp_index_path, paths["index_path"])

    def load_record(
        self,
        certification_id: str,
        plot_id: str,
        variable: str
    ) -> Optional[V90CertificationRecord]:
        """
        Loads a certification record from active records or revoked archive.
        """
        paths = get_certification_paths(
            certification_id,
            plot_id,
            variable,
            cert_root=self.cert_root
        )
        
        # Check active records first
        if paths["record_path"].exists():
            with open(paths["record_path"], "r", encoding="utf-8") as f:
                data = json.load(f)
                return V90CertificationRecord.from_dict(data)
                
        # Check revoked archives
        if paths["revoked_path"].exists():
            with open(paths["revoked_path"], "r", encoding="utf-8") as f:
                data = json.load(f)
                return V90CertificationRecord.from_dict(data)
                
        return None
