"""
Crop Intelligence v6.0B — Label Store.

Abstract interface + in-memory implementation for label storage.
Production MongoLabelStore reads/writes the same MongoDB collection
that Prisma defines (ConfirmedCropLabel).

Conflict resolution rules:
  - Same plot + overlapping dates + different crop → supersede older label
  - Same plot + same crop + same dates → deduplicate (return existing)
  - Same plot + changed geometry_hash → accept + warning
  - Source trust upgrade (historical → farmer) → supersede

Date-overlap rules (Adjustment #4):
  - If both labels have planting/harvest dates → interval overlap
  - If one label has only planting date → planting + default duration
  - If no dates → same-season (same calendar year) conflict
  - Impossible dates → flag as warning
"""

import abc
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .label_schema import (
    CropLabel,
    LABEL_SCHEMA_VERSION,
)

logger = logging.getLogger("agribrain.labels.store")

# Default crop cycle durations (days) when harvest_date is missing
# Rough estimates per crop group for overlap detection
_DEFAULT_DURATION_DAYS: Dict[str, int] = {
    "winter_cereal": 210,
    "summer_cereal": 150,
    "pseudo_cereal": 120,
    "rice": 140,
    "cool_legume": 150,
    "warm_legume": 120,
    "solanaceae_veg": 150,
    "cucurbit_veg": 100,
    "root_tuber": 130,
    "leafy_veg": 90,
    "oilseed": 130,
    "cotton_fiber": 180,
    "sugar_crop": 200,
    "herb_spice": 120,
    "forage": 300,
    "evergreen_orchard": 365,
    "deciduous_orchard": 240,
    "tropical_palm": 365,
    "non_crop": 365,
}

DEFAULT_DURATION_FALLBACK = 150  # days


def _parse_date(s: Optional[str]) -> Optional[datetime]:
    """Parse ISO date string to datetime, or None."""
    if not s:
        return None
    try:
        # Handle date-only strings
        if "T" not in s:
            return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None



def _estimate_end_date(
    start: datetime,
    crop_group: str,
) -> datetime:
    """Estimate harvest date from planting date + default duration."""
    from datetime import timedelta
    days = _DEFAULT_DURATION_DAYS.get(crop_group, DEFAULT_DURATION_FALLBACK)
    return start + timedelta(days=days)


def normalize_feature_snapshot(fv: Dict, version: str = "6.0.0") -> Dict:
    """Normalize and enforce structure on the feature vector snapshot."""
    import warnings
    if not isinstance(fv, dict):
        warnings.warn("Feature vector snapshot is invalid (not a dictionary). Rejecting snapshot.")
        raise ValueError("Invalid feature vector: must be a dictionary.")

    # Check if it's already normalized
    if "flat_features" in fv:
        flat = fv["flat_features"]
        full = fv.get("full_json", fv)
        comp = fv.get("data_completeness", flat.get("data_completeness", 1.0))
        avail = fv.get("feature_availability_by_level", {})
        created = fv.get("created_at") or datetime.now(timezone.utc).isoformat() + "Z"
        return {
            "feature_vector_version": fv.get("feature_vector_version", version),
            "flat_features": flat,
            "full_json": full,
            "data_completeness": comp,
            "feature_availability_by_level": avail,
            "created_at": created,
        }

    # Otherwise it is a raw flat dict. Structure it:
    flat_features = dict(fv)
    full_json = dict(fv)
    data_completeness = flat_features.get("data_completeness", 1.0)
    
    # Calculate feature availability by level for L0
    l0_features = ["peak_ndvi", "base_ndvi", "amplitude", "cv_ndvi", "vv_mean_db", "vh_mean_db", "n_seasons", "is_evergreen"]
    l0_available = sum(1 for f in l0_features if flat_features.get(f) is not None)
    l0_availability = l0_available / len(l0_features) if l0_features else 1.0
    availability = flat_features.get("feature_availability_by_level") or {"L0": l0_availability}
    
    timestamp = datetime.now(timezone.utc).isoformat() + "Z"
    
    return {
        "feature_vector_version": version,
        "flat_features": flat_features,
        "full_json": full_json,
        "data_completeness": data_completeness,
        "feature_availability_by_level": availability,
        "created_at": timestamp,
    }


def dates_overlap(
    label_a: CropLabel,
    label_b: CropLabel,
) -> bool:
    """Check if two labels have overlapping crop cycles.

    Date-overlap rules (user requirement):
      1. Both have planting+harvest → interval overlap
      2. One has only planting → use planting + default duration
      3. No dates on either → same calendar year = overlap
      4. Impossible dates (harvest < planting) → no overlap (flagged separately)
    """
    start_a = _parse_date(label_a.planting_date)
    end_a = _parse_date(label_a.harvest_date)
    start_b = _parse_date(label_b.planting_date)
    end_b = _parse_date(label_b.harvest_date)

    # Case 3: No dates → check if same calendar year
    if start_a is None and start_b is None:
        # Both dateless — assume overlap on same plot within same year
        year_a = _parse_date(label_a.created_at)
        year_b = _parse_date(label_b.created_at)
        if year_a and year_b:
            return year_a.year == year_b.year
        return True  # Cannot determine — assume overlap

    # Case 2: Estimate missing end dates
    if start_a is not None and end_a is None:
        end_a = _estimate_end_date(start_a, label_a.crop_group)
    if start_b is not None and end_b is None:
        end_b = _estimate_end_date(start_b, label_b.crop_group)

    # If we still have None start, use created_at as proxy
    if start_a is None:
        start_a = _parse_date(label_a.created_at)
        if start_a and end_a is None:
            end_a = _estimate_end_date(start_a, label_a.crop_group)
    if start_b is None:
        start_b = _parse_date(label_b.created_at)
        if start_b and end_b is None:
            end_b = _estimate_end_date(start_b, label_b.crop_group)

    # If still can't determine, assume overlap
    if start_a is None or end_a is None or start_b is None or end_b is None:
        return True

    # Case 4: Impossible dates
    if end_a < start_a or end_b < start_b:
        return False

    # Case 1: Standard interval overlap
    return start_a <= end_b and start_b <= end_a


class ConflictResult:
    """Result of conflict checking between labels."""

    def __init__(
        self,
        conflict_type: Optional[str] = None,
        existing_label_id: Optional[str] = None,
        action: str = "insert",
        warnings: Optional[List[str]] = None,
    ):
        self.conflict_type = conflict_type  # "duplicate" | "supersede" | "trust_upgrade" | None
        self.existing_label_id = existing_label_id
        self.action = action  # "insert" | "deduplicate" | "supersede"
        self.warnings = warnings or []


# ── Abstract Base ────────────────────────────────────────────────────────────

class LabelStoreBase(abc.ABC):
    """Abstract label storage interface.

    Production: MongoLabelStore (reads/writes ConfirmedCropLabel collection)
    Tests: InMemoryLabelStore (dict-based, no MongoDB)
    """

    @abc.abstractmethod
    def save_label(self, label: CropLabel) -> Tuple[str, ConflictResult]:
        """Insert or handle a label.

        Returns (label_id, ConflictResult).
        """

    @abc.abstractmethod
    def get_labels_for_plot(
        self, plot_id: str, active_only: bool = True
    ) -> List[CropLabel]:
        """Retrieve all labels for a plot."""

    @abc.abstractmethod
    def get_label_by_id(self, label_id: str) -> Optional[CropLabel]:
        """Retrieve a label by its stable UUID."""

    @abc.abstractmethod
    def get_all_labels(
        self,
        active_only: bool = True,
        crop_groups: Optional[List[str]] = None,
        label_sources: Optional[List[str]] = None,
    ) -> List[CropLabel]:
        """Retrieve all labels matching filters."""

    @abc.abstractmethod
    def supersede_label(self, old_label_id: str, new_label_id: str) -> bool:
        """Mark old label as superseded by new label."""

    @abc.abstractmethod
    def attach_feature_vector(
        self, label_id: str, feature_vector: Dict, version: str = "6.0.0"
    ) -> bool:
        """Attach a CropFeatureVector snapshot to an existing label."""

    @abc.abstractmethod
    def get_label_stats(self) -> Dict:
        """Return summary statistics."""

    def check_conflicts(
        self,
        new_label: CropLabel,
        current_geometry_hash: Optional[str] = None,
    ) -> ConflictResult:
        """Check for conflicts with existing labels.

        Rules:
          1. Same plot + same crop + same dates → deduplicate
          2. Same plot + overlapping dates + different crop → supersede
          3. Source trust upgrade (historical → farmer) → supersede
          4. Geometry change → warning
        """
        existing = self.get_labels_for_plot(new_label.plot_id, active_only=True)
        warnings = []

        # Check geometry change
        if current_geometry_hash and new_label.geometry_hash != current_geometry_hash:
            warnings.append("geometry_changed")

        for existing_label in existing:
            # Check date overlap
            if not dates_overlap(new_label, existing_label):
                continue

            # Same crop + same dates → deduplicate
            if existing_label.crop_code == new_label.crop_code:
                return ConflictResult(
                    conflict_type="duplicate",
                    existing_label_id=existing_label.label_id,
                    action="deduplicate",
                    warnings=warnings,
                )

            # Different crop + overlapping dates → supersede
            # Also handle trust upgrade
            from .label_schema import SOURCE_TRUST
            old_trust = SOURCE_TRUST.get(existing_label.label_source, 0.5)
            new_trust = SOURCE_TRUST.get(new_label.label_source, 0.5)

            if new_trust >= old_trust:
                ctype = "trust_upgrade" if new_trust > old_trust else "supersede"
                return ConflictResult(
                    conflict_type=ctype,
                    existing_label_id=existing_label.label_id,
                    action="supersede",
                    warnings=warnings,
                )
            else:
                # Lower trust trying to override higher trust — still supersede
                # but add warning
                warnings.append("lower_trust_override")
                return ConflictResult(
                    conflict_type="supersede",
                    existing_label_id=existing_label.label_id,
                    action="supersede",
                    warnings=warnings,
                )

        return ConflictResult(action="insert", warnings=warnings)


# ── In-Memory Implementation (for tests) ────────────────────────────────────

class InMemoryLabelStore(LabelStoreBase):
    """Dict-based label store for testing. No MongoDB dependency."""

    def __init__(self):
        self._labels: Dict[str, CropLabel] = {}  # label_id → CropLabel

    def save_label(self, label: CropLabel) -> Tuple[str, ConflictResult]:
        """Insert label with conflict resolution."""
        if label.feature_vector_snapshot:
            label.feature_vector_snapshot = normalize_feature_snapshot(
                label.feature_vector_snapshot, label.feature_vector_version
            )
        conflict = self.check_conflicts(label)

        if conflict.action == "deduplicate":
            return conflict.existing_label_id, conflict

        if conflict.action == "supersede" and conflict.existing_label_id:
            self.supersede_label(conflict.existing_label_id, label.label_id)

        self._labels[label.label_id] = label
        return label.label_id, conflict

    def get_labels_for_plot(
        self, plot_id: str, active_only: bool = True
    ) -> List[CropLabel]:
        results = []
        for label in self._labels.values():
            if label.plot_id != plot_id:
                continue
            if active_only and not label.is_active:
                continue
            results.append(label)
        return results

    def get_label_by_id(self, label_id: str) -> Optional[CropLabel]:
        return self._labels.get(label_id)

    def get_all_labels(
        self,
        active_only: bool = True,
        crop_groups: Optional[List[str]] = None,
        label_sources: Optional[List[str]] = None,
    ) -> List[CropLabel]:
        results = []
        for label in self._labels.values():
            if active_only and not label.is_active:
                continue
            if crop_groups and label.crop_group not in crop_groups:
                continue
            if label_sources and label.label_source not in label_sources:
                continue
            results.append(label)
        return results

    def supersede_label(self, old_label_id: str, new_label_id: str) -> bool:
        old = self._labels.get(old_label_id)
        if old is None:
            return False
        old.is_active = False
        old.superseded_by = new_label_id
        return True

    def attach_feature_vector(
        self, label_id: str, feature_vector: Dict, version: str = "6.0.0"
    ) -> bool:
        label = self._labels.get(label_id)
        if label is None:
            return False
        try:
            normalized = normalize_feature_snapshot(feature_vector, version)
            label.feature_vector_snapshot = normalized
            label.feature_vector_version = normalized["feature_vector_version"]
            return True
        except Exception as e:
            import warnings
            warnings.warn(f"Feature attachment failed validation: {e}")
            return False

    def get_label_stats(self) -> Dict:
        active = [l for l in self._labels.values() if l.is_active]
        by_source: Dict[str, int] = {}
        by_group: Dict[str, int] = {}
        by_confidence: Dict[str, int] = {}

        for l in active:
            by_source[l.label_source] = by_source.get(l.label_source, 0) + 1
            by_group[l.crop_group] = by_group.get(l.crop_group, 0) + 1
            by_confidence[l.label_confidence] = by_confidence.get(l.label_confidence, 0) + 1

        return {
            "total_labels": len(self._labels),
            "active_labels": len(active),
            "by_source": by_source,
            "by_group": by_group,
            "by_confidence": by_confidence,
        }


# ── MongoDB Implementation (for production) ─────────────────────────────────

class MongoLabelStore(LabelStoreBase):
    """Production MongoDB-backed label store using PyMongo.

    Reads/writes the ConfirmedCropLabel collection mapped by Prisma.
    Parses dates to real datetime objects to keep Prisma compatible.
    """

    def __init__(self, db_uri: Optional[str] = None):
        import os
        from pymongo import MongoClient
        uri = db_uri or os.environ.get("MONGODB_URI") or os.environ.get("DATABASE_URL", "")
        if not uri:
            raise ValueError("MongoDB URI must be provided or set in environment variables.")
        
        self.client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        # Parse database name from URI
        db_name = uri.split("/")[-1].split("?")[0] if "/" in uri else "agriwise"
        if not db_name or db_name == uri:
            db_name = "agriwise"
        self.db = self.client[db_name]
        self.collection = self.db["ConfirmedCropLabel"]

        # Ensure indexes (matching Prisma and query requirements)
        for idx_spec in [
            ([("plotId", 1), ("isActive", 1)], {}),
            ([("cropCode", 1), ("cropGroup", 1)], {}),
            ([("labelSource", 1)], {}),
            ([("qualityTier", 1)], {}),
            ([("plotId", 1), ("plantingDate", 1)], {}),
            ([("labelId", 1)], {"unique": True}),
        ]:
            try:
                self.collection.create_index(idx_spec[0], **idx_spec[1])
            except Exception as e:
                logger.warning(f"Index creation skipped/failed for {idx_spec[0]}: {e}")


    def _doc_to_label(self, doc: Dict) -> CropLabel:
        """Convert MongoDB document back to CropLabel instance."""
        d = dict(doc)
        if "_id" in d:
            del d["_id"]
        # Convert BSON plotId ObjectId back to str
        if "plotId" in d and not isinstance(d["plotId"], str):
            d["plotId"] = str(d["plotId"])
        # Convert supersededBy back to str if it's an ObjectId or anything else
        if "supersededBy" in d and d["supersededBy"] is not None and not isinstance(d["supersededBy"], str):
            d["supersededBy"] = str(d["supersededBy"])
        for f in ["plantingDate", "harvestDate", "createdAt"]:
            if isinstance(d.get(f), datetime):
                # Format to standard ISO string
                d[f] = d[f].isoformat().replace("+00:00", "Z")
        return CropLabel.from_dict(d)

    def save_label(self, label: CropLabel) -> Tuple[str, ConflictResult]:
        """Insert or supersede label with conflict resolution."""
        if label.feature_vector_snapshot:
            label.feature_vector_snapshot = normalize_feature_snapshot(
                label.feature_vector_snapshot, label.feature_vector_version
            )
        conflict = self.check_conflicts(label)

        if conflict.action == "deduplicate" and conflict.existing_label_id:
            return conflict.existing_label_id, conflict

        if conflict.action == "supersede" and conflict.existing_label_id:
            self.supersede_label(conflict.existing_label_id, label.label_id)

        # Compute quality details for db fields
        from .label_quality import compute_label_quality
        quality = compute_label_quality(label)

        doc = label.to_dict()
        
        # Populate quality fields
        doc["qualityScore"] = quality.overall_quality
        doc["qualityTier"] = quality.quality_tier
        doc["qualityDetails"] = quality.to_dict()

        # Parse date fields to real Datetime objects for Prisma
        for f in ["plantingDate", "harvestDate", "createdAt"]:
            if doc.get(f):
                doc[f] = _parse_date(doc[f])
        doc["updatedAt"] = datetime.now(timezone.utc)

        # Convert plotId to ObjectId (or fallback with warning)
        warnings_list = []
        try:
            from bson import ObjectId
            plot_oid = ObjectId(label.plot_id)
            doc["plotId"] = plot_oid
        except Exception:
            doc["plotId"] = label.plot_id
            warnings_list.append("plot_id_not_objectid_string_fallback")

        self.collection.insert_one(doc)
        if warnings_list:
            conflict.warnings.extend(warnings_list)
        return label.label_id, conflict

    def get_labels_for_plot(
        self, plot_id: str, active_only: bool = True
    ) -> List[CropLabel]:
        from bson import ObjectId
        query_id = plot_id
        try:
            query_id = ObjectId(plot_id)
        except Exception:
            pass

        if isinstance(query_id, ObjectId):
            query = {"plotId": {"$in": [query_id, plot_id]}}
        else:
            query = {"plotId": query_id}

        if active_only:
            query["isActive"] = True
        
        cursor = self.collection.find(query)
        return [self._doc_to_label(doc) for doc in cursor]

    def get_label_by_id(self, label_id: str) -> Optional[CropLabel]:
        doc = self.collection.find_one({"labelId": label_id})
        return self._doc_to_label(doc) if doc else None

    def get_all_labels(
        self,
        active_only: bool = True,
        crop_groups: Optional[List[str]] = None,
        label_sources: Optional[List[str]] = None,
    ) -> List[CropLabel]:
        query = {}
        if active_only:
            query["isActive"] = True
        if crop_groups:
            query["cropGroup"] = {"$in": crop_groups}
        if label_sources:
            query["labelSource"] = {"$in": label_sources}

        cursor = self.collection.find(query)
        return [self._doc_to_label(doc) for doc in cursor]

    def supersede_label(self, old_label_id: str, new_label_id: str) -> bool:
        res = self.collection.update_one(
            {"labelId": old_label_id},
            {
                "$set": {
                    "isActive": False,
                    "supersededBy": new_label_id,
                    "updatedAt": datetime.now(timezone.utc)
                }
            }
        )
        return res.modified_count > 0

    def attach_feature_vector(
        self, label_id: str, feature_vector: Dict, version: str = "6.0.0"
    ) -> bool:
        try:
            normalized = normalize_feature_snapshot(feature_vector, version)
        except Exception as e:
            import warnings
            warnings.warn(f"Feature attachment failed validation: {e}")
            return False

        res = self.collection.update_one(
            {"labelId": label_id},
            {
                "$set": {
                    "featureVectorSnapshot": normalized,
                    "featureVectorVersion": normalized["feature_vector_version"],
                    "updatedAt": datetime.now(timezone.utc)
                }
            }
        )
        return res.modified_count > 0

    def get_label_stats(self) -> Dict:
        total = self.collection.count_documents({})
        active_query = {"isActive": True}
        active = self.collection.count_documents(active_query)

        by_source = {}
        for item in self.collection.aggregate([
            {"$match": active_query},
            {"$group": {"_id": "$labelSource", "count": {"$sum": 1}}}
        ]):
            if item["_id"]:
                by_source[item["_id"]] = item["count"]

        by_group = {}
        for item in self.collection.aggregate([
            {"$match": active_query},
            {"$group": {"_id": "$cropGroup", "count": {"$sum": 1}}}
        ]):
            if item["_id"]:
                by_group[item["_id"]] = item["count"]

        by_confidence = {}
        for item in self.collection.aggregate([
            {"$match": active_query},
            {"$group": {"_id": "$labelConfidence", "count": {"$sum": 1}}}
        ]):
            if item["_id"]:
                by_confidence[item["_id"]] = item["count"]

        return {
            "total_labels": total,
            "active_labels": active,
            "by_source": by_source,
            "by_group": by_group,
            "by_confidence": by_confidence,
        }

