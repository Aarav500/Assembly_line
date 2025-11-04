from typing import Dict, List, Any, Optional
from dataclasses import asdict
from gap_analyzer.ideater_manifest import Manifest
from gap_analyzer.detector import DetectionResult
import logging

logger = logging.getLogger(__name__)


def _classify_gap(manifest_status: str, detected_status: str) -> str:
    """Classify the gap between manifest and detected status."""
    try:
        # Alignment mapping
        if manifest_status == "implemented" and detected_status == "implemented":
            return "aligned"
        if manifest_status == "in-progress" and detected_status in ("in-progress", "implemented"):
            return "aligned"
        if manifest_status == "planned" and detected_status == "not-detected":
            return "not-started"
        if manifest_status == "planned" and detected_status in ("in-progress", "implemented"):
            return "ahead-of-manifest"
        if manifest_status == "in-progress" and detected_status == "not-detected":
            return "possibly-stale"
        if manifest_status == "implemented" and detected_status != "implemented":
            return "missing-evidence"
        if manifest_status == "deprecated" and detected_status in ("in-progress", "implemented", "referenced"):
            return "should-be-removed"
        if manifest_status == "deprecated" and detected_status == "not-detected":
            return "aligned"
        return "review"
    except Exception as e:
        logger.error(f"Error classifying gap for manifest_status={manifest_status}, detected_status={detected_status}: {e}")
        return "review"


def _evidence_payload(ev: Any) -> Dict[str, Any]:
    """Extract evidence payload from detection evidence."""
    try:
        return {
            "occurrences": len(ev.occurrences) if hasattr(ev, 'occurrences') and ev.occurrences else 0,
            "files": list(set([occ.file for occ in ev.occurrences])) if hasattr(ev, 'occurrences') and ev.occurrences else [],
        }
    except Exception as e:
        logger.error(f"Error extracting evidence payload: {e}")
        return {"occurrences": 0, "files": []}


def analyze_gaps(manifest: Manifest, detection: DetectionResult) -> Dict[str, Any]:
    """Analyze gaps between manifest and detected project state."""
    try:
        ideas_index = {idea.id: idea for idea in manifest.ideas}
        analyzed: List[Dict[str, Any]] = []

        counts = {
            "total_manifest_ideas": len(manifest.ideas),
            "implemented_in_manifest": 0,
            "detected_implemented": 0,
            "gaps": {
                "not-started": 0,
                "possibly-stale": 0,
                "missing-evidence": 0,
                "ahead-of-manifest": 0,
                "should-be-removed": 0,
                "aligned": 0,
                "review": 0,
            },
        }

        # Analyze manifest ideas
        for idea in manifest.ideas:
            try:
                if idea.status == "implemented":
                    counts["implemented_in_manifest"] += 1
                ev = detection.features.get(idea.id)
                detected_status = ev.inferred_status if ev else "not-detected"
                if detected_status == "implemented":
                    counts["detected_implemented"] += 1
                gap = _classify_gap(idea.status, detected_status)
                counts["gaps"][gap] = counts["gaps"].get(gap, 0) + 1
                analyzed.append({
                    "id": idea.id,
                    "title": idea.title,
                    "manifest_status": idea.status,
                    "detected_status": detected_status,
                    "gap": gap,
                    "evidence": _evidence_payload(ev) if ev else {"occurrences": 0, "files": []},
                })
            except Exception as e:
                logger.error(f"Error analyzing idea {idea.id}: {e}")
                analyzed.append({
                    "id": idea.id,
                    "title": getattr(idea, 'title', 'Unknown'),
                    "manifest_status": getattr(idea, 'status', 'unknown'),
                    "detected_status": "error",
                    "gap": "review",
                    "evidence": {"occurrences": 0, "files": []},
                })

        # Orphans: detected features not present in manifest
        orphans: List[Dict[str, Any]] = []
        try:
            for fid, ev in detection.features.items():
                try:
                    if fid not in ideas_index:
                        orphans.append({
                            "id": fid,
                            "detected_status": ev.inferred_status,
                            "gap": "orphan-implementation",
                            "evidence": _evidence_payload(ev),
                        })
                except Exception as e:
                    logger.error(f"Error processing orphan feature {fid}: {e}")
        except Exception as e:
            logger.error(f"Error processing orphan features: {e}")

        summary = counts

        return {
            "summary": summary,
            "analyzed": analyzed,
            "orphans": orphans,
        }
    except Exception as e:
        logger.error(f"Critical error in analyze_gaps: {e}")
        return {
            "summary": {
                "total_manifest_ideas": 0,
                "implemented_in_manifest": 0,
                "detected_implemented": 0,
                "gaps": {},
            },
            "analyzed": [],
            "orphans": [],
            "error": str(e),
        }