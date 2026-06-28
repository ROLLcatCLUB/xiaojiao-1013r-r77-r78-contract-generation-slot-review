import json

from .controlled_json_extractor import ControlledExtractionError, extract_minimax_json_object


class OutputParserError(Exception):
    def __init__(self, code, message, parse_subcode=None, diagnostics=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.parse_subcode = parse_subcode
        self.diagnostics = diagnostics or {}


def parse_patch_output(raw_text, provider_meta=None):
    if isinstance(raw_text, dict):
        return raw_text, {
            "parser_mode": "strict_json_parser",
            "provider_output_sanitized": False,
            "sanitize_method": None,
            "raw_prefix_type": "native_object",
            "raw_response_has_think_tag": False,
            "raw_response_saved": False,
        }

    if not isinstance(raw_text, str):
        raise OutputParserError("json_parse_error", "Provider output must be a JSON string.", "non_string_output")

    text = raw_text.strip()
    if not text:
        raise OutputParserError("json_parse_error", "Provider output is empty.", "empty_output")

    if text.startswith("```"):
        raise OutputParserError(
            "json_parse_error",
            "Provider output must be plain JSON, not fenced markdown.",
            "fenced_markdown_output",
            _build_diagnostics(text),
        )

    if text.startswith("<think>"):
        if _is_minimax_provider(provider_meta):
            try:
                return extract_minimax_json_object(raw_text)
            except ControlledExtractionError as extraction_error:
                diagnostics = _build_diagnostics(text)
                diagnostics.update(extraction_error.diagnostics)
                diagnostics["controlled_extraction_error"] = extraction_error.code
                raise OutputParserError(
                    "json_parse_error",
                    "Provider returned <think> preamble before JSON.",
                    "non_json_preamble_think_tag",
                    diagnostics,
                )
        raise OutputParserError(
            "json_parse_error",
            "Provider returned <think> preamble before JSON.",
            "non_json_preamble_think_tag",
            _build_diagnostics(text),
        )

    try:
        payload = json.loads(text)
        return payload, {
            "parser_mode": "strict_json_parser",
            "provider_output_sanitized": False,
            "sanitize_method": None,
            "raw_prefix_type": _build_diagnostics(text).get("raw_response_prefix_type"),
            "raw_response_has_think_tag": "<think>" in text.lower(),
            "raw_response_saved": False,
        }
    except json.JSONDecodeError as exc:
        parse_error = OutputParserError(
            "json_parse_error",
            f"Provider output is not valid JSON: {exc.msg}",
            _guess_parse_subcode(text),
            _build_diagnostics(text),
        )
        if _is_minimax_provider(provider_meta) and parse_error.parse_subcode == "non_json_preamble_think_tag":
            try:
                return extract_minimax_json_object(raw_text)
            except ControlledExtractionError as extraction_error:
                diagnostics = dict(parse_error.diagnostics)
                diagnostics.update(extraction_error.diagnostics)
                diagnostics["controlled_extraction_error"] = extraction_error.code
                raise OutputParserError(
                    parse_error.code,
                    parse_error.message,
                    parse_error.parse_subcode,
                    diagnostics,
                ) from exc
        raise parse_error from exc


def _guess_parse_subcode(text):
    lowered = text.lstrip().lower()
    if lowered.startswith("<think>"):
        return "non_json_preamble_think_tag"
    if lowered.startswith("```"):
        return "fenced_markdown_output"
    if lowered.startswith("here is") or lowered.startswith("下面是"):
        return "non_json_preamble_explanatory_text"
    return "invalid_json_output"


def _build_diagnostics(text):
    stripped = text.lstrip()
    prefix_type = "unknown"
    if stripped.startswith("<think>"):
        prefix_type = "think_tag"
    elif stripped.startswith("```"):
        prefix_type = "markdown_fence"
    elif stripped.startswith("{"):
        prefix_type = "json_object"
    elif stripped:
        prefix_type = "text_preamble"
    return {
        "raw_response_has_think_tag": "<think>" in text.lower(),
        "raw_response_prefix_type": prefix_type,
        "raw_response_saved": False,
    }


def _is_minimax_provider(provider_meta):
    if not isinstance(provider_meta, dict):
        return False
    model = str(provider_meta.get("model") or "")
    base_url = str(provider_meta.get("base_url") or "")
    credential_source = str(provider_meta.get("credential_source") or "")
    return (
        "minimax" in model.lower()
        or "minimaxi" in base_url.lower()
        or credential_source in {"MINIMAX", "MINIAMX"}
    )
