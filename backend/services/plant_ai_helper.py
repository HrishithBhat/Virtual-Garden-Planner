import json
import math
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Sequence

import requests


@dataclass
class PlantRecord:
    id: Optional[int]
    name: str
    scientific_name: str
    duration_days: Optional[int]
    type: str
    photo_url: str
    description: str
    sunlight: Optional[str]
    spacing_cm: Optional[int]
    watering_needs: Optional[str]
    model_url: Optional[str]
    growth_height_cm: Optional[int]
    growth_width_cm: Optional[int]


class PlantAIHelperError(Exception):
    """Raised when the Plant AI helper cannot fulfill a request."""


_ALLOWED_FIELDS = {
    "name",
    "scientific_name",
    "duration_days",
    "type",
    "photo_url",
    "description",
    "sunlight",
    "spacing_cm",
    "watering_needs",
    "model_url",
    "growth_height_cm",
    "growth_width_cm",
}

_NUMERIC_FIELDS = {
    "duration_days",
    "spacing_cm",
    "growth_height_cm",
    "growth_width_cm",
}


def build_dataset(plants: Sequence[Any]) -> List[PlantRecord]:
    dataset: List[PlantRecord] = []
    for plant in plants:
        dataset.append(
            PlantRecord(
                id=getattr(plant, "id", None),
                name=(getattr(plant, "name", "") or "").strip(),
                scientific_name=(getattr(plant, "scientific_name", "") or "").strip(),
                duration_days=_coerce_int(getattr(plant, "duration_days", None)),
                type=(getattr(plant, "type", "") or "").strip(),
                photo_url=(getattr(plant, "photo_url", "") or "").strip(),
                description=_truncate((getattr(plant, "description", "") or "").strip(), 480),
                sunlight=_clean_optional(getattr(plant, "sunlight", None)),
                spacing_cm=_coerce_int(getattr(plant, "spacing_cm", None)),
                watering_needs=_clean_optional(getattr(plant, "watering_needs", None)),
                model_url=_clean_optional(getattr(plant, "model_url", None)),
                growth_height_cm=_coerce_int(getattr(plant, "growth_height_cm", None)),
                growth_width_cm=_coerce_int(getattr(plant, "growth_width_cm", None)),
            )
        )
    return dataset


def generate_suggestion(
    name: str,
    photo_url: str,
    dataset: Sequence[PlantRecord],
    *,
    api_key: str,
    model: str = "gemini-2.0-flash",
) -> Dict[str, Any]:
    normalized_name = (name or "").strip()
    normalized_photo = (photo_url or "").strip()
    duplicate = _find_duplicate(normalized_name, dataset)

    if duplicate:
        return {
            "message": (
                f"Plant \"{normalized_name}\" already exists in the database as ID {duplicate.id}. "
                "I have loaded its saved details so you can review them instead of adding a duplicate."
            ),
            "fields": _record_to_fields(duplicate, fallback_photo=normalized_photo or duplicate.photo_url),
            "duplicate": True,
            "similar_matches": _similar_matches(normalized_name, dataset, exclude_id=duplicate.id),
        }

    payload = _dataset_to_json(dataset)
    prompt = (
        "You are Verdant AI, supporting an admin who maintains a horticulture knowledge base.\n"
        "You will receive the full plant dataset in JSON and the admin's proposed plant name.\n"
        "Use the dataset to avoid duplicates and to infer missing details.\n"
        "Respond ONLY with a compact JSON object matching this schema:\n"
        "{\\n"
        "  \"message\": string,  \n"
        "  \"fields\": {fields to fill or infer},\n"
        "  \"duplicate\": boolean,\n"
        "  \"similar_matches\": array of strings (sorted best to worst)\n"
        "}\n"
        "Rules:\n"
        "- message: 1-3 short sentences, friendly, professional.\n"
        "- Always include the incoming name and photo_url in fields.\n"
        "- duration_days, spacing_cm, growth_height_cm, growth_width_cm must be integers if known, else null.\n"
        "- If unsure of a value, set it to null rather than guessing wildly.\n"
        "- duplicate must be true ONLY if the dataset already includes this plant by common or scientific name.\n"
        "- similar_matches should list up to 5 existing plant names (with scientific names) ranked by similarity.\n"
        "- Output JSON only, no surrounding prose.\n"
        f"Dataset: {payload}\n"
        f"Proposed plant name: {normalized_name or 'Unknown'}\n"
        f"Provided photo_url: {normalized_photo or 'None'}\n"
    )

    response_text = _call_gemini(prompt, api_key=api_key, model=model, temperature=0.2)
    parsed = _parse_json(response_text)
    fields = _normalize_fields(parsed.get("fields") or {}, fallback_name=normalized_name, fallback_photo=normalized_photo)

    result = {
        "message": (parsed.get("message") or "I have reviewed the plant details. Let's double-check them together.").strip(),
        "fields": fields,
        "duplicate": bool(parsed.get("duplicate")),
        "similar_matches": parsed.get("similar_matches") or _similar_matches(normalized_name, dataset),
    }

    if result["duplicate"]:
        duplicate_result = _find_duplicate(fields.get("name") or normalized_name, dataset)
        if duplicate_result:
            result["fields"] = _record_to_fields(duplicate_result, fallback_photo=fields.get("photo_url") or normalized_photo)
            result["message"] = (
                f"Plant \"{duplicate_result.name}\" already exists (ID {duplicate_result.id}). "
                "I've restored its saved details so you can avoid duplicates."
            )

    return result


def chat_response(
    message: str,
    conversation: Sequence[Dict[str, str]],
    fields: Dict[str, Any],
    dataset: Sequence[PlantRecord],
    *,
    api_key: str,
    model: str = "gemini-2.0-flash",
) -> Dict[str, Any]:
    normalized_message = (message or "").strip()
    if not normalized_message:
        raise PlantAIHelperError("Message is required")

    payload = _dataset_to_json(dataset)
    conversation_payload = json.dumps(_sanitize_conversation(conversation), ensure_ascii=False)
    fields_payload = json.dumps(_normalize_fields(fields, fallback_name=fields.get("name"), fallback_photo=fields.get("photo_url")), ensure_ascii=False)

    prompt = (
        "You are Verdant AI assisting an admin creating plants in a horticulture database.\n"
        "You have strict responsibilities:\n"
        "1. Never allow duplicates: if the name or scientific_name already exists, set duplicate=true and warn the admin.\n"
        "2. When updating values, return only the specific fields that need updating inside field_updates.\n"
        "3. Keep replies concise (2-3 sentences).\n"
        "4. Always reply with JSON only, matching this schema:\n"
        "{\\n"
        "  \"message\": string,\n"
        "  \"field_updates\": { field: value },\n"
        "  \"duplicate\": boolean,\n"
        "  \"similar_matches\": array of strings\n"
        "}\n"
        "Dataset JSON: "
        f"{payload}\n"
        "Conversation history (oldest first) as JSON array of {role, content}:\n"
        f"{conversation_payload}\n"
        "Current draft fields JSON:\n"
        f"{fields_payload}\n"
        "Admin message: "
        f"{normalized_message}\n"
        "Remember: respond with JSON only."
    )

    response_text = _call_gemini(prompt, api_key=api_key, model=model, temperature=0.25)
    parsed = _parse_json(response_text)

    field_updates = _normalize_fields(parsed.get("field_updates") or {}, fallback_name=None, fallback_photo=None)
    if field_updates:
        merged_fields = {**fields, **field_updates}
    else:
        merged_fields = dict(fields)

    duplicate_candidate = _find_duplicate(merged_fields.get("name"), dataset) or _find_duplicate_by_scientific(
        merged_fields.get("scientific_name"), dataset
    )

    duplicate_flag = bool(parsed.get("duplicate")) or duplicate_candidate is not None

    if duplicate_candidate:
        duplicate_message = (
            f"Plant \"{duplicate_candidate.name}\" already exists (ID {duplicate_candidate.id}). "
            "I've reloaded the saved values so you can adjust instead of duplicating."
        )
        field_updates = _record_to_fields(duplicate_candidate)
        merged_fields = field_updates
        parsed_message = parsed.get("message") or duplicate_message
        message_out = f"{parsed_message.strip()} {duplicate_message}".strip()
    else:
        message_out = (parsed.get("message") or "Done. I've applied those updates.").strip()

    return {
        "message": message_out,
        "field_updates": field_updates,
        "duplicate": duplicate_flag,
        "similar_matches": parsed.get("similar_matches") or _similar_matches(fields.get("name", ""), dataset),
        "merged_fields": _normalize_fields(merged_fields, fallback_name=None, fallback_photo=None),
    }


def _call_gemini(prompt: str, *, api_key: str, model: str, temperature: float) -> str:
    if not api_key:
        raise PlantAIHelperError("Gemini API key is not configured")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"Content-Type": "application/json", "X-goog-api-key": api_key}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": max(0.0, min(1.0, temperature))},
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        text = _extract_text(data)
        if not text:
            raise PlantAIHelperError("Gemini returned an empty response")
        return text
    except requests.RequestException as exc:
        raise PlantAIHelperError(f"Gemini request failed: {exc}") from exc


def _extract_text(data: Dict[str, Any]) -> str:
    if isinstance(data, dict):
        candidates = data.get("candidates")
        if isinstance(candidates, list):
            for candidate in candidates:
                parts = candidate.get("content", {}).get("parts") if isinstance(candidate, dict) else None
                if isinstance(parts, list):
                    for part in parts:
                        text = part.get("text") if isinstance(part, dict) else None
                        if text:
                            return text
        # Fallback: depth-first search
        for value in data.values():
            text = _extract_text(value) if isinstance(value, dict) else None
            if text:
                return text
    elif isinstance(data, list):
        for item in data:
            text = _extract_text(item)
            if text:
                return text
    elif isinstance(data, str):
        return data
    return ""


def _parse_json(raw: str) -> Dict[str, Any]:
    if not raw:
        return {}
    text = raw.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        return {}
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = text[start : end + 1]
            try:
                parsed = json.loads(snippet)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return {}
    return {}


def _normalize_fields(
    values: Dict[str, Any],
    *,
    fallback_name: Optional[str],
    fallback_photo: Optional[str],
) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for key, value in values.items():
        if key not in _ALLOWED_FIELDS:
            continue
        if key in _NUMERIC_FIELDS:
            normalized[key] = _coerce_int(value)
        else:
            normalized[key] = _clean_optional(value)
    if fallback_name and not normalized.get("name"):
        normalized["name"] = fallback_name.strip()
    if fallback_photo and not normalized.get("photo_url"):
        normalized["photo_url"] = fallback_photo.strip()
    return normalized


def _record_to_fields(record: PlantRecord, *, fallback_photo: Optional[str] = None) -> Dict[str, Any]:
    return {
        "name": record.name,
        "scientific_name": record.scientific_name,
        "duration_days": record.duration_days,
        "type": record.type,
        "photo_url": fallback_photo or record.photo_url,
        "description": record.description,
        "sunlight": record.sunlight,
        "spacing_cm": record.spacing_cm,
        "watering_needs": record.watering_needs,
        "model_url": record.model_url,
        "growth_height_cm": record.growth_height_cm,
        "growth_width_cm": record.growth_width_cm,
    }


def _find_duplicate(name: Optional[str], dataset: Sequence[PlantRecord]) -> Optional[PlantRecord]:
    if not name:
        return None
    target = name.strip().lower()
    for record in dataset:
        if record.name.lower() == target:
            return record
    return None


def _find_duplicate_by_scientific(scientific_name: Optional[str], dataset: Sequence[PlantRecord]) -> Optional[PlantRecord]:
    if not scientific_name:
        return None
    target = scientific_name.strip().lower()
    for record in dataset:
        if record.scientific_name.lower() == target:
            return record
    return None


def _similar_matches(name: str, dataset: Sequence[PlantRecord], *, exclude_id: Optional[int] = None) -> List[str]:
    target = (name or "").strip().lower()
    if not target:
        return []
    scored: List[Dict[str, Any]] = []
    for record in dataset:
        if exclude_id is not None and record.id == exclude_id:
            continue
        combined = f"{record.name} ({record.scientific_name})".strip()
        comparison_name = record.name.lower()
        score = SequenceMatcher(None, target, comparison_name).ratio()
        if record.scientific_name:
            score = max(score, SequenceMatcher(None, target, record.scientific_name.lower()).ratio())
        if score > 0.45:
            scored.append({"text": combined, "score": score})
    scored.sort(key=lambda item: item["score"], reverse=True)
    return [item["text"] for item in scored[:5]]


def compute_similar_matches(name: str, dataset: Sequence[PlantRecord], *, exclude_id: Optional[int] = None) -> List[str]:
    return _similar_matches(name, dataset, exclude_id=exclude_id)


def record_fields(record: PlantRecord, *, fallback_photo: Optional[str] = None) -> Dict[str, Any]:
    return _record_to_fields(record, fallback_photo=fallback_photo)


def detect_duplicate_by_name(name: Optional[str], dataset: Sequence[PlantRecord]) -> Optional[PlantRecord]:
    return _find_duplicate(name, dataset)


def detect_duplicate_by_scientific(scientific_name: Optional[str], dataset: Sequence[PlantRecord]) -> Optional[PlantRecord]:
    return _find_duplicate_by_scientific(scientific_name, dataset)


def _sanitize_conversation(conversation: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    sanitized: List[Dict[str, str]] = []
    for entry in conversation or []:
        role = (entry.get("role") or "user").strip().lower()
        if role not in {"user", "assistant"}:
            role = "user"
        content = (entry.get("content") or "").strip()
        if not content:
            continue
        sanitized.append({"role": role, "content": content})
    return sanitized[-12:]


def _dataset_to_json(dataset: Sequence[PlantRecord]) -> str:
    serializable = []
    for record in dataset:
        serializable.append(
            {
                "id": record.id,
                "name": record.name,
                "scientific_name": record.scientific_name,
                "duration_days": record.duration_days,
                "type": record.type,
                "photo_url": record.photo_url,
                "description": record.description,
                "sunlight": record.sunlight,
                "spacing_cm": record.spacing_cm,
                "watering_needs": record.watering_needs,
                "model_url": record.model_url,
                "growth_height_cm": record.growth_height_cm,
                "growth_width_cm": record.growth_width_cm,
            }
        )
    return json.dumps(serializable, ensure_ascii=False)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _coerce_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (float, int)) and not math.isnan(value):
            return int(value)
        if isinstance(value, str):
            return int(float(value.strip()))
    except (ValueError, TypeError):
        return None
    return None


def _clean_optional(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    if isinstance(value, (int, float)):
        return str(value)
    return None


def web_enrich_fields(name: str) -> Dict[str, Any]:
    """Fetch basic plant details from Wikipedia and infer fields.

    Best-effort enrichment without API keys. Returns a dict with:
      - message: short summary of findings
      - field_updates: fields to propose (excluding name/photo_url)
      - sources: list of source URLs used
    """
    title = (name or '').strip()
    if not title:
        return {"message": "No name provided.", "field_updates": {}, "sources": []}

    import re
    sources: List[str] = []
    summary = ""
    sci_name: Optional[str] = None
    ptype: Optional[str] = None

    try:
        url_title = requests.utils.quote(title.replace(' ', '_'))
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{url_title}"
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            jd = r.json() or {}
            extract = (jd.get('extract') or '').strip()
            if extract:
                summary = _truncate(extract, 480)
                sources.append(jd.get('content_urls', {}).get('desktop', {}).get('page') or jd.get('canonicalurl') or f"https://en.wikipedia.org/wiki/{url_title}")
                # Try to infer scientific binomial (Genus species)
                m = re.search(r"([A-Z][a-z]+\s+[a-z]+)\b", extract)
                if m:
                    sci_name = m.group(1)
                text_lc = extract.lower()
                if any(k in text_lc for k in ['fruit', 'berry', 'citrus']):
                    ptype = 'fruit'
                elif any(k in text_lc for k in ['vegetable', 'root vegetable', 'leaf vegetable']):
                    ptype = 'vegetable'
                elif 'herb' in text_lc:
                    ptype = 'herb'
                elif any(k in text_lc for k in ['flower', 'ornamental']):
                    ptype = 'flower'
    except Exception:
        pass

    updates: Dict[str, Any] = {}
    if sci_name:
        updates['scientific_name'] = sci_name
    if ptype:
        updates['type'] = ptype
    if summary:
        updates['description'] = summary

    message_parts = []
    if updates:
        message_parts.append("I found reference details online. Review and apply?")
    else:
        message_parts.append("Couldn't find reliable public details. You can still proceed.")
    if sources:
        message_parts.append("Source: " + (sources[0] or 'Wikipedia'))

    return {"message": " ".join(message_parts), "field_updates": updates, "sources": sources}
