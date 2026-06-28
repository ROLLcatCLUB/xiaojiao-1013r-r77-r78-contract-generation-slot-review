import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


class ProviderError(Exception):
    def __init__(self, code, message, meta=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.meta = meta or {}


MODULE_DIR = Path(__file__).resolve().parent
MOCK_DIR = MODULE_DIR / "mock_data"
_OPENCLAW_MINIMAX_TOKEN_CACHE = None
TRUE_VALUES = {"1", "true", "yes", "on"}
PRODUCTION_ENV_VALUES = {"production", "prod"}
CANDIDATE_PROVIDER_ALIASES = {
    "openai_like": "openai_compatible",
    "coze_like": "openai_compatible",
    "coze": "openai_compatible",
}
CREDENTIAL_SOURCE_MOCK = "mock"
CREDENTIAL_SOURCE_ENV = "env"
CREDENTIAL_SOURCE_PROJECT_CONFIG = "project_config"
CREDENTIAL_SOURCE_OPENCLAW_OPT_IN = "openclaw_auth_profile_explicit_opt_in"
CREDENTIAL_SOURCE_DISABLED = "disabled"
CREDENTIAL_SOURCE_MISSING = "missing"
CREDENTIAL_SOURCE_INVALID = "invalid"
PROVIDER_FAMILY_MINIMAX = "minimax"
PROVIDER_FAMILY_OPENAI = "openai"
PROVIDER_FAMILY_ANTHROPIC = "anthropic"
PROVIDER_FAMILY_LOCAL = "local"
PROVIDER_FAMILY_UNKNOWN = "unknown"
ALLOWED_CREDENTIAL_SOURCES = {
    CREDENTIAL_SOURCE_MOCK,
    CREDENTIAL_SOURCE_ENV,
    CREDENTIAL_SOURCE_PROJECT_CONFIG,
    CREDENTIAL_SOURCE_OPENCLAW_OPT_IN,
    CREDENTIAL_SOURCE_DISABLED,
    CREDENTIAL_SOURCE_MISSING,
    CREDENTIAL_SOURCE_INVALID,
}
MOCK_PATCH_INDEX = {
    ("quick_generate", "PREP-G3-U3-L2-QINGLV"): MOCK_DIR / "lesson2_quick_patch.json",
    ("deep_refine", "PREP-G3-U3-L2-QINGLV"): MOCK_DIR / "lesson2_deep_patch.json",
    ("quick_generate", "PREP-G3-U3-L3-QINGLV"): MOCK_DIR / "lesson3_quick_patch.json",
    ("deep_refine", "PREP-G3-U3-L3-QINGLV"): MOCK_DIR / "lesson3_deep_patch.json",
}


def generate_json_patch(input_bundle, prompt_context, options):
    provider = _normalize_provider_name(_resolve_provider_name(options))
    if provider == "mock":
        return _generate_mock_patch(input_bundle, options)
    if provider == "anthropic_compatible":
        return _generate_anthropic_compatible(input_bundle, prompt_context, options)
    if provider == "openai_compatible":
        return _generate_openai_compatible(input_bundle, prompt_context, options)
    raise ProviderError("provider_not_supported", f"Provider '{provider}' is not supported in v1.")


def generate_image_description(name, mime_type, image_base64, prompt, options=None):
    if _has_minimax_credentials() and (os.environ.get("XIAOBEI_MINIMAX_VISION_ENABLED") or "1").strip().lower() not in {"0", "false", "no", "off"}:
        try:
            return _generate_minimax_coding_vlm(name, mime_type, image_base64, prompt, options)
        except ProviderError:
            if (os.environ.get("XIAOBEI_VISION_FALLBACK_OPENAI") or "1").strip().lower() in {"0", "false", "no", "off"}:
                raise

    base_url = _resolve_vision_base_url()
    api_key = _resolve_vision_api_key()
    if not base_url or not api_key:
        raise ProviderError("vision_provider_not_configured", "Vision provider is not configured.")

    model = (
        ((options or {}).get("model") or "").strip()
        or (os.environ.get("XIAOBEI_VISION_MODEL") or "").strip()
        or (os.environ.get("OPENAI_VISION_MODEL") or "").strip()
        or (os.environ.get("OPENAI_MODEL") or "").strip()
        or "gpt-4o-mini"
    )
    timeout_ms = _resolve_timeout_ms(options or {"timeout_ms": 60000})
    image_mime = (mime_type or "image/png").strip() or "image/png"
    data_url = f"data:{image_mime};base64,{image_base64}"
    system_prompt = (
        "你是雕庄智绘教育的图片资料解析助手。"
        "请读取图片中的文字、表格和教学信息，优先输出可被备课系统使用的内容。"
        "如果是教材目录或课表截图，请尽量整理成逐行条目；如果是教材图片，请说明主题、画面元素和可用于美术教学的线索。"
        "回答使用中文，简洁，不要编造图片中没有的信息。"
    )
    body = {
        "model": model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt or f"请解析图片资料：{name}"},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        "max_tokens": int((options or {}).get("max_tokens") or 1200),
    }
    request_data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    endpoint = (os.environ.get("XIAOBEI_VISION_ENDPOINT") or "/chat/completions").strip() or "/chat/completions"
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{endpoint}",
        data=request_data,
        headers=headers,
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout_ms / 1000) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = _read_http_error_detail(exc)
        raise ProviderError("vision_provider_http_error", f"Vision provider HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        reason = str(getattr(exc, "reason", exc))
        raise ProviderError("vision_provider_unavailable", f"Vision provider request failed: {reason}") from exc
    except Exception as exc:
        raise ProviderError("vision_provider_unavailable", f"Vision provider request failed: {exc}") from exc

    latency_ms = round((time.perf_counter() - started) * 1000)
    try:
        parsed = json.loads(response_body)
        raw_text = (
            (((parsed.get("choices") or [])[0] or {}).get("message") or {}).get("content")
            or ""
        )
    except Exception as exc:
        raise ProviderError("vision_provider_response_invalid", f"Vision provider response could not be decoded: {exc}") from exc
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise ProviderError("vision_provider_response_invalid", "Vision provider returned empty message content.")
    return {
        "success": True,
        "raw_text": raw_text.strip(),
        "provider_meta": {
            "provider": "openai_compatible_vision",
            "model": model,
            "base_url": base_url,
            "latency_ms": latency_ms,
        },
    }


def _generate_minimax_coding_vlm(name, mime_type, image_base64, prompt, options=None):
    api_key = _resolve_api_key()
    if not api_key:
        raise ProviderError("minimax_vision_auth_failed", "Missing MiniMax API key for image understanding.")
    api_host = (
        (os.environ.get("MINIMAX_API_HOST") or "").strip()
        or (os.environ.get("MINIAMX_API_HOST") or "").strip()
        or (os.environ.get("XIAOBEI_MINIMAX_API_HOST") or "").strip()
        or "https://api.minimax.chat"
    ).rstrip("/")
    image_mime = (mime_type or "image/png").strip() or "image/png"
    data_url = f"data:{image_mime};base64,{image_base64}"
    body = {
        "prompt": prompt or f"请解析图片资料：{name}",
        "image_url": data_url,
    }
    request_data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "MM-API-Source": "Xiaobei-SmartEdu",
    }
    timeout_ms = _resolve_timeout_ms(options or {"timeout_ms": 70000})
    request = urllib.request.Request(
        f"{api_host}/v1/coding_plan/vlm",
        data=request_data,
        headers=headers,
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout_ms / 1000) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = _read_http_error_detail(exc)
        if exc.code in {401, 403}:
            raise ProviderError("minimax_vision_auth_failed", f"MiniMax VLM authentication failed: {detail}") from exc
        raise ProviderError("minimax_vision_http_error", f"MiniMax VLM HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        reason = str(getattr(exc, "reason", exc))
        raise ProviderError("minimax_vision_unavailable", f"MiniMax VLM request failed: {reason}") from exc
    except TimeoutError as exc:
        raise ProviderError("minimax_vision_timeout", "MiniMax VLM request timed out.") from exc
    except Exception as exc:
        raise ProviderError("minimax_vision_unavailable", f"MiniMax VLM request failed: {exc}") from exc

    latency_ms = round((time.perf_counter() - started) * 1000)
    try:
        parsed = json.loads(response_body)
        base_resp = parsed.get("base_resp") if isinstance(parsed, dict) else None
        if isinstance(base_resp, dict) and base_resp.get("status_code") not in {None, 0, "0"}:
            raise ProviderError(
                "minimax_vision_business_error",
                f"MiniMax VLM business error {base_resp.get('status_code')}: {base_resp.get('status_msg')}",
            )
        raw_text = parsed.get("content") if isinstance(parsed, dict) else ""
    except ProviderError:
        raise
    except Exception as exc:
        raise ProviderError("minimax_vision_response_invalid", f"MiniMax VLM response could not be decoded: {exc}") from exc
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise ProviderError("minimax_vision_response_invalid", "MiniMax VLM returned empty content.")
    return {
        "success": True,
        "raw_text": raw_text.strip(),
        "provider_meta": {
            "provider": "minimax_coding_plan_vlm",
            "base_url": api_host,
            "credential_source": _resolve_credential_source(),
            "latency_ms": latency_ms,
        },
    }


def provider_status():
    """Return a redacted snapshot of model provider capability."""
    provider_name = (os.environ.get("XIAOBEI_AI_PROVIDER_DEFAULT") or "openai_compatible").strip()
    if provider_name == "anthropic_compatible":
        base_url = _resolve_anthropic_base_url()
        generation_resolution = _resolve_anthropic_credential()
        generation_credential = _public_credential_payload(generation_resolution)
    elif provider_name == "mock":
        base_url = _resolve_base_url()
        generation_resolution = _base_credential_payload(
            CREDENTIAL_SOURCE_MOCK,
            True,
            provider_family=PROVIDER_FAMILY_LOCAL,
            reason="mock_provider",
        )
        generation_credential = generation_resolution
    else:
        base_url = _resolve_base_url()
        generation_resolution = _resolve_generation_credential()
        generation_credential = _generation_credential_status(base_url)
    vision_base_url = _resolve_vision_base_url()
    vision_credential = _vision_credential_status(vision_base_url)
    model = (
        (os.environ.get("XIAOBEI_AI_MODEL_DEFAULT") or "").strip()
        or (os.environ.get("MINIMAX_MODEL") or "").strip()
        or (os.environ.get("MINIAMX_MODEL") or "").strip()
        or ("MiniMax-M3" if generation_resolution.get("provider_family") == PROVIDER_FAMILY_MINIMAX and generation_resolution.get("credential_available") else "miniamx-default")
    )
    vision_model = (
        (os.environ.get("XIAOBEI_VISION_MODEL") or "").strip()
        or (os.environ.get("OPENAI_VISION_MODEL") or "").strip()
        or (os.environ.get("OPENAI_MODEL") or "").strip()
        or ("MiniMax-M3" if _has_minimax_credentials() else "")
    )
    return {
        "success": True,
        "provider_name": provider_name,
        "credential_source": generation_credential["credential_source"],
        "credential_available": generation_credential["credential_available"],
        "token_preview": None,
        "external_profile_used": generation_credential["external_profile_used"],
        "openclaw_auth_profile_used": generation_credential["openclaw_auth_profile_used"],
        "safe_for_preview_runtime": True,
        "generation": {
            "provider": provider_name,
            "provider_name": provider_name,
            "model": model,
            "base_url": _redact_base_url(base_url),
            **generation_credential,
            "provider_enabled": bool(generation_credential["credential_available"] or _is_local_base_url(base_url)),
            "fallback_to_mock_allowed": True,
            "safe_for_preview_runtime": True,
        },
        "vision": {
            "enabled": (os.environ.get("XIAOBEI_MINIMAX_VISION_ENABLED") or "1").strip().lower() not in {"0", "false", "no", "off"},
            "provider": "minimax_vlm" if _has_minimax_credentials() else ("openai_vision" if _resolve_vision_api_key() else ""),
            "provider_name": "minimax_vlm" if _has_minimax_credentials() else ("openai_vision" if _resolve_vision_api_key() else "disabled"),
            "model": vision_model,
            "base_url": _redact_base_url(vision_base_url),
            **vision_credential,
            "provider_enabled": bool(vision_credential["credential_available"]),
            "fallback_to_mock_allowed": True,
            "safe_for_preview_runtime": True,
        },
    }


def _resolve_provider_name(options):
    provider = ((options or {}).get("provider") or "").strip()
    if provider:
        return _normalize_provider_name(provider)
    env_default = (os.environ.get("XIAOBEI_AI_PROVIDER_DEFAULT") or "").strip()
    return _normalize_provider_name(env_default) or "openai_compatible"


def _normalize_provider_name(value):
    text = str(value or "").strip()
    if not text:
        return ""
    key = text.lower()
    return CANDIDATE_PROVIDER_ALIASES.get(key, text)


def _generate_mock_patch(input_bundle, options):
    mode = input_bundle.get("mode")
    target = input_bundle.get("target_prep_package_id")
    path = MOCK_PATCH_INDEX.get((mode, target))
    if not path:
        raise ProviderError(
            "mock_patch_not_found",
            f"No mock patch found for mode={mode} target_prep_package_id={target}.",
        )
    raw_text = path.read_text(encoding="utf-8")
    model = (options or {}).get("model") or "mock_qinglv_v1"
    return {
        "success": True,
        "raw_text": raw_text,
        "provider_meta": {
            "provider": "mock",
            "model": model,
            "fixture": path.name,
        },
    }


def _generate_openai_compatible(input_bundle, prompt_context, options):
    base_url = _resolve_base_url()
    api_key = _resolve_api_key()
    if not api_key and not _is_local_base_url(base_url):
        raise ProviderError(
            "provider_auth_failed",
            "Missing MINIAMX_API_KEY / MINIMAX_API_KEY or OPENAI_API_KEY for openai_compatible provider.",
        )

    model = (
        ((options or {}).get("model") or "").strip()
        or (os.environ.get("XIAOBEI_AI_MODEL_DEFAULT") or "").strip()
        or (os.environ.get("MINIMAX_MODEL") or "").strip()
        or (os.environ.get("MINIAMX_MODEL") or "").strip()
        or ("MiniMax-M3" if _has_minimax_credentials() else "miniamx-default")
    )
    timeout_ms = _resolve_timeout_ms(options)
    temperature = _resolve_temperature(options)
    max_tokens = _resolve_max_tokens(options)

    body = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": prompt_context["system_prompt"]},
            {"role": "user", "content": prompt_context["user_prompt"]},
        ],
    }
    if _is_minimax_m3_model(model):
        body["max_completion_tokens"] = max_tokens
        body["thinking"] = _resolve_minimax_m3_thinking(options)
    else:
        body["max_tokens"] = max_tokens
    if _use_response_format(options):
        body["response_format"] = {"type": "json_object"}
    reasoning_split = _use_reasoning_split(options, model, base_url)
    if reasoning_split:
        body["reasoning_split"] = True
    request_data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    endpoint = _resolve_openai_compatible_endpoint(base_url)
    request = urllib.request.Request(
        f"{base_url}{endpoint}",
        data=request_data,
        headers=headers,
        method="POST",
    )

    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout_ms / 1000) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = _read_http_error_detail(exc)
        if exc.code in {401, 403}:
            raise ProviderError("provider_auth_failed", f"Provider authentication failed: {detail}") from exc
        if _is_retryable_overloaded_http_error(exc.code, detail):
            raise ProviderError(
                "provider_overloaded_retryable",
                f"Provider overloaded: {detail}",
                meta={"http_status": exc.code, "retryable": True},
            ) from exc
        raise ProviderError("provider_internal_error", f"Provider HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        reason = str(getattr(exc, "reason", exc))
        if "timed out" in reason.lower():
            raise ProviderError("provider_timeout", "Provider request timed out.") from exc
        raise ProviderError("provider_internal_error", f"Provider request failed: {reason}") from exc
    except TimeoutError as exc:
        raise ProviderError("provider_timeout", "Provider request timed out.") from exc
    except Exception as exc:
        raise ProviderError("provider_internal_error", f"Provider request failed: {exc}") from exc

    latency_ms = round((time.perf_counter() - started) * 1000)
    try:
        parsed = json.loads(response_body)
        _raise_openai_compatible_business_error(parsed, base_url)
        raw_text = (
            (((parsed.get("choices") or [])[0] or {}).get("message") or {}).get("content")
            or ""
        )
    except Exception as exc:
        raise ProviderError("provider_response_invalid", f"Provider response could not be decoded: {exc}") from exc

    if not isinstance(raw_text, str) or not raw_text.strip():
        raise ProviderError("provider_response_invalid", "Provider returned empty message content.")
    raw_text = _sanitize_openai_compatible_text(raw_text, base_url)

    return {
        "success": True,
        "raw_text": raw_text,
        "provider_meta": {
            "provider": "openai_compatible",
            "model": model,
            "base_url": base_url,
            "credential_source": _resolve_credential_source(),
            "reasoning_split": reasoning_split,
            "latency_ms": latency_ms,
        },
    }


def _is_minimax_m3_model(model):
    return str(model or "").strip().lower() == "minimax-m3"


def _resolve_minimax_m3_thinking(options):
    value = str((options or {}).get("minimax_m3_thinking") or os.environ.get("MINIMAX_M3_THINKING") or "disabled").strip().lower()
    if value in {"adaptive", "on", "true", "1", "yes"}:
        return {"type": "adaptive"}
    return {"type": "disabled"}


def _generate_anthropic_compatible(input_bundle, prompt_context, options):
    base_url = _resolve_anthropic_base_url()
    api_key = _resolve_anthropic_api_key()
    if not api_key and not _is_local_base_url(base_url):
        raise ProviderError(
            "provider_auth_failed",
            "Missing MINIMAX / ANTHROPIC API key for anthropic_compatible provider.",
        )

    model = (
        ((options or {}).get("model") or "").strip()
        or (os.environ.get("XIAOBEI_AI_MODEL_DEFAULT") or "").strip()
        or (os.environ.get("MINIMAX_MODEL") or "").strip()
        or (os.environ.get("MINIAMX_MODEL") or "").strip()
        or "MiniMax-M3"
    )
    timeout_ms = _resolve_timeout_ms(options)
    temperature = _resolve_temperature(options)
    max_tokens = _resolve_max_tokens(options)
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "system": prompt_context["system_prompt"],
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt_context["user_prompt"],
                    }
                ],
            }
        ],
        "temperature": temperature,
    }
    request_data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    request = urllib.request.Request(
        f"{base_url}/v1/messages",
        data=request_data,
        headers=headers,
        method="POST",
    )

    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout_ms / 1000) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = _read_http_error_detail(exc)
        if exc.code in {401, 403}:
            raise ProviderError("provider_auth_failed", f"Provider authentication failed: {detail}") from exc
        if _is_retryable_overloaded_http_error(exc.code, detail):
            raise ProviderError(
                "provider_overloaded_retryable",
                f"Provider overloaded: {detail}",
                meta={"http_status": exc.code, "retryable": True},
            ) from exc
        raise ProviderError("provider_internal_error", f"Provider HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        reason = str(getattr(exc, "reason", exc))
        if "timed out" in reason.lower():
            raise ProviderError("provider_timeout", "Provider request timed out.") from exc
        raise ProviderError("provider_internal_error", f"Provider request failed: {reason}") from exc
    except TimeoutError as exc:
        raise ProviderError("provider_timeout", "Provider request timed out.") from exc
    except Exception as exc:
        raise ProviderError("provider_internal_error", f"Provider request failed: {exc}") from exc

    latency_ms = round((time.perf_counter() - started) * 1000)
    try:
        parsed = json.loads(response_body)
        raw_text = _extract_anthropic_text_content(parsed)
    except Exception as exc:
        raise ProviderError("provider_response_invalid", f"Provider response could not be decoded: {exc}") from exc

    if not isinstance(raw_text, str) or not raw_text.strip():
        raise ProviderError("provider_response_invalid", "Provider returned empty text content.")

    return {
        "success": True,
        "raw_text": raw_text,
        "provider_meta": {
            "provider": "anthropic_compatible",
            "model": model,
            "base_url": base_url,
            "credential_source": _resolve_anthropic_credential_source(),
            "latency_ms": latency_ms,
        },
    }


def _resolve_timeout_ms(options):
    option_timeout = (options or {}).get("timeout_ms")
    if isinstance(option_timeout, int) and option_timeout >= 5000:
        return option_timeout
    env_timeout = (os.environ.get("XIAOBEI_AI_TIMEOUT_MS") or "").strip()
    if env_timeout.isdigit():
        return max(int(env_timeout), 5000)
    return 45000


def _resolve_temperature(options):
    value = (options or {}).get("temperature")
    if isinstance(value, (int, float)):
        return max(0.0, min(float(value), 1.0))
    return 0.2


def _resolve_max_tokens(options):
    value = (options or {}).get("max_tokens")
    if isinstance(value, int) and value > 0:
        return value
    env_value = (os.environ.get("XIAOBEI_AI_MAX_TOKENS") or "").strip()
    if env_value.isdigit():
        return max(int(env_value), 256)
    return 4000


def _use_response_format(options):
    opt_value = (options or {}).get("use_response_format")
    if isinstance(opt_value, bool):
        return opt_value
    env_value = (os.environ.get("XIAOBEI_AI_USE_RESPONSE_FORMAT") or "").strip().lower()
    if env_value in {"0", "false", "no", "off"}:
        return False
    return True


def _use_reasoning_split(options, model, base_url):
    opt_value = (options or {}).get("use_reasoning_split")
    if isinstance(opt_value, bool):
        return opt_value
    env_value = (os.environ.get("XIAOBEI_AI_USE_REASONING_SPLIT") or "").strip().lower()
    if env_value in {"0", "false", "no", "off"}:
        return False
    if env_value in {"1", "true", "yes", "on"}:
        return True
    model_text = (model or "").lower()
    base_text = (base_url or "").lower()
    return "minimax" in model_text or "minimaxi" in base_text


def _read_http_error_detail(exc):
    try:
        body = exc.read().decode("utf-8")
        if body:
            return _redact_secret_text(body[:500])
    except Exception:
        pass
    return _redact_secret_text(exc.reason or "unknown provider error")


def _is_retryable_overloaded_http_error(status_code, detail):
    detail_text = (detail or "").lower()
    if status_code in {429, 529}:
        if any(token in detail_text for token in ["overloaded_error", "too many requests", "rate limit", "请求拥挤"]):
            return True
    return False


def _is_local_base_url(base_url):
    return base_url.startswith("http://127.0.0.1") or base_url.startswith("http://localhost")


def _redact_base_url(base_url):
    text = str(base_url or "").strip().rstrip("/")
    if not text:
        return ""
    return text


def _resolve_api_key():
    return str(_resolve_generation_credential().get("token") or "")


def _resolve_anthropic_api_key():
    return str(_resolve_anthropic_credential().get("token") or "")


def _resolve_base_url():
    resolution = _resolve_generation_credential()
    family = resolution.get("provider_family")
    if family == PROVIDER_FAMILY_MINIMAX and resolution.get("credential_available"):
        explicit = _explicit_minimax_generation_base_url()
        if explicit:
            return _normalize_generation_base_url(explicit)
        return "https://api.minimaxi.com/v1"
    if family == PROVIDER_FAMILY_OPENAI and resolution.get("credential_available"):
        explicit = _explicit_openai_generation_base_url()
        if explicit:
            return _normalize_generation_base_url(explicit)
        return "https://api.openai.com/v1"
    explicit = _explicit_generation_base_url()
    if explicit and _is_local_base_url(_normalize_generation_base_url(explicit)):
        return _normalize_generation_base_url(explicit)
    return "https://api.openai.com/v1"


def _resolve_vision_api_key():
    return _first_env_token(["XIAOBEI_VISION_API_KEY", "OPENAI_API_KEY"])


def _resolve_vision_base_url():
    explicit = (
        (os.environ.get("XIAOBEI_VISION_BASE_URL") or "").strip()
        or (os.environ.get("OPENAI_BASE_URL") or "").strip()
    )
    if explicit:
        return explicit.rstrip("/")
    if _resolve_vision_api_key():
        return "https://api.openai.com/v1"
    return ""


def _resolve_anthropic_base_url():
    resolution = _resolve_anthropic_credential()
    family = resolution.get("provider_family")
    if family == PROVIDER_FAMILY_MINIMAX and resolution.get("credential_available"):
        explicit = _explicit_minimax_anthropic_base_url()
        if explicit:
            return explicit.rstrip("/")
        return "https://api.minimaxi.com/anthropic"
    if family == PROVIDER_FAMILY_ANTHROPIC and resolution.get("credential_available"):
        explicit = _explicit_native_anthropic_base_url()
        if explicit:
            return explicit.rstrip("/")
        return "https://api.anthropic.com"
    explicit = _explicit_anthropic_base_url()
    if explicit and _is_local_base_url(explicit.rstrip("/")):
        return explicit.rstrip("/")
    return "https://api.anthropic.com"


def _resolve_credential_source():
    return _resolve_generation_credential()["credential_source"]


def _resolve_anthropic_credential_source():
    return _resolve_anthropic_credential()["credential_source"]


def _has_minimax_credentials():
    if _first_env_token(["MINIAMX_API_KEY", "MINIMAX_API_KEY"]):
        return True
    if _first_env_token(["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "XIAOBEI_VISION_API_KEY"]):
        return False
    generation = _resolve_generation_credential()
    return bool(generation.get("provider_family") == PROVIDER_FAMILY_MINIMAX and generation.get("credential_available"))


def _first_env_token(names):
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def _explicit_generation_base_url():
    return (
        (os.environ.get("MINIAMX_BASE_URL") or "").strip()
        or (os.environ.get("MINIMAX_BASE_URL") or "").strip()
        or (os.environ.get("MINIMAX_API_BASE") or "").strip()
        or (os.environ.get("MINIAMX_API_BASE") or "").strip()
        or (os.environ.get("OPENAI_BASE_URL") or "").strip()
    )


def _explicit_minimax_generation_base_url():
    return (
        (os.environ.get("MINIAMX_BASE_URL") or "").strip()
        or (os.environ.get("MINIMAX_BASE_URL") or "").strip()
        or (os.environ.get("MINIMAX_API_BASE") or "").strip()
        or (os.environ.get("MINIAMX_API_BASE") or "").strip()
    )


def _explicit_openai_generation_base_url():
    return (os.environ.get("OPENAI_BASE_URL") or "").strip()


def _explicit_anthropic_base_url():
    return (
        (os.environ.get("MINIMAX_ANTHROPIC_BASE_URL") or "").strip()
        or (os.environ.get("MINIAMX_ANTHROPIC_BASE_URL") or "").strip()
        or (os.environ.get("ANTHROPIC_BASE_URL") or "").strip()
    )


def _explicit_minimax_anthropic_base_url():
    return (
        (os.environ.get("MINIMAX_ANTHROPIC_BASE_URL") or "").strip()
        or (os.environ.get("MINIAMX_ANTHROPIC_BASE_URL") or "").strip()
    )


def _explicit_native_anthropic_base_url():
    return (os.environ.get("ANTHROPIC_BASE_URL") or "").strip()


def _truthy_env(name):
    return (os.environ.get(name) or "").strip().lower() in TRUE_VALUES


def _is_production_mode():
    for name in ["APP_ENV", "FLASK_ENV", "ENV", "NODE_ENV", "XIAOBEI_ENV"]:
        if (os.environ.get(name) or "").strip().lower() in PRODUCTION_ENV_VALUES:
            return True
    return False


def _base_credential_payload(source, available, **extra):
    payload = {
        "credential_source": source if source in ALLOWED_CREDENTIAL_SOURCES else CREDENTIAL_SOURCE_INVALID,
        "credential_available": bool(available),
        "token_preview": None,
        "external_profile_used": False,
        "openclaw_auth_profile_used": False,
    }
    payload.update(extra)
    return payload


def _credential_resolution(source, available, token="", provider_family=PROVIDER_FAMILY_UNKNOWN, **extra):
    payload = _base_credential_payload(
        source,
        bool(available),
        provider_family=provider_family,
        reason=extra.pop("reason", ""),
        **extra,
    )
    payload["token"] = token if available else ""
    return payload


def _resolve_generation_credential():
    minimax_token = _first_env_token(["MINIAMX_API_KEY", "MINIMAX_API_KEY"])
    if minimax_token:
        return _credential_resolution(CREDENTIAL_SOURCE_ENV, True, minimax_token, PROVIDER_FAMILY_MINIMAX, reason="minimax_env")
    openai_token = _first_env_token(["OPENAI_API_KEY"])
    if openai_token:
        return _credential_resolution(CREDENTIAL_SOURCE_ENV, True, openai_token, PROVIDER_FAMILY_OPENAI, reason="openai_env")
    if _first_env_token(["ANTHROPIC_API_KEY"]):
        return _credential_resolution(
            CREDENTIAL_SOURCE_MISSING,
            False,
            "",
            PROVIDER_FAMILY_UNKNOWN,
            reason="anthropic_env_not_valid_for_openai_compatible",
        )
    openclaw_status = _openclaw_auth_profile_status(read_token=True)
    if openclaw_status.get("credential_source") == CREDENTIAL_SOURCE_INVALID:
        return _credential_resolution(
            CREDENTIAL_SOURCE_INVALID,
            False,
            "",
            PROVIDER_FAMILY_UNKNOWN,
            reason=openclaw_status.get("reason") or "openclaw_auth_profile_invalid",
            profile_path_redacted=openclaw_status.get("profile_path_redacted") or "",
        )
    openclaw_token = str(openclaw_status.get("_token") or "").strip()
    if openclaw_token:
        return _credential_resolution(
            CREDENTIAL_SOURCE_OPENCLAW_OPT_IN,
            True,
            openclaw_token,
            PROVIDER_FAMILY_MINIMAX,
            external_profile_used=True,
            openclaw_auth_profile_used=True,
            profile_path_redacted="<OPENCLAW_AUTH_PROFILE_PATH_REDACTED>",
            reason="openclaw_auth_profile_explicit_opt_in",
        )
    explicit_base = _explicit_generation_base_url()
    if explicit_base and _is_local_base_url(_normalize_generation_base_url(explicit_base)):
        return _credential_resolution(CREDENTIAL_SOURCE_DISABLED, True, "", PROVIDER_FAMILY_LOCAL, reason="local_provider_without_token")
    return _credential_resolution(CREDENTIAL_SOURCE_MISSING, False, "", PROVIDER_FAMILY_UNKNOWN, reason="missing_generation_credentials")


def _resolve_anthropic_credential():
    minimax_token = _first_env_token(["MINIAMX_API_KEY", "MINIMAX_API_KEY"])
    if minimax_token:
        return _credential_resolution(CREDENTIAL_SOURCE_ENV, True, minimax_token, PROVIDER_FAMILY_MINIMAX, reason="minimax_env")
    anthropic_token = _first_env_token(["ANTHROPIC_API_KEY"])
    if anthropic_token:
        return _credential_resolution(CREDENTIAL_SOURCE_ENV, True, anthropic_token, PROVIDER_FAMILY_ANTHROPIC, reason="anthropic_env")
    if _first_env_token(["OPENAI_API_KEY"]):
        return _credential_resolution(
            CREDENTIAL_SOURCE_MISSING,
            False,
            "",
            PROVIDER_FAMILY_UNKNOWN,
            reason="openai_env_not_valid_for_anthropic_compatible",
        )
    openclaw_status = _openclaw_auth_profile_status(read_token=True)
    if openclaw_status.get("credential_source") == CREDENTIAL_SOURCE_INVALID:
        return _credential_resolution(
            CREDENTIAL_SOURCE_INVALID,
            False,
            "",
            PROVIDER_FAMILY_UNKNOWN,
            reason=openclaw_status.get("reason") or "openclaw_auth_profile_invalid",
            profile_path_redacted=openclaw_status.get("profile_path_redacted") or "",
        )
    openclaw_token = str(openclaw_status.get("_token") or "").strip()
    if openclaw_token:
        return _credential_resolution(
            CREDENTIAL_SOURCE_OPENCLAW_OPT_IN,
            True,
            openclaw_token,
            PROVIDER_FAMILY_MINIMAX,
            external_profile_used=True,
            openclaw_auth_profile_used=True,
            profile_path_redacted="<OPENCLAW_AUTH_PROFILE_PATH_REDACTED>",
            reason="openclaw_auth_profile_explicit_opt_in",
        )
    explicit_base = _explicit_anthropic_base_url()
    if explicit_base and _is_local_base_url(explicit_base.rstrip("/")):
        return _credential_resolution(CREDENTIAL_SOURCE_DISABLED, True, "", PROVIDER_FAMILY_LOCAL, reason="local_provider_without_token")
    return _credential_resolution(CREDENTIAL_SOURCE_MISSING, False, "", PROVIDER_FAMILY_UNKNOWN, reason="missing_anthropic_credentials")


def _generation_credential_status(base_url=""):
    resolution = _resolve_generation_credential()
    if not resolution.get("credential_available") and _is_local_base_url(base_url):
        resolution = _credential_resolution(CREDENTIAL_SOURCE_DISABLED, True, "", PROVIDER_FAMILY_LOCAL, reason="local_provider_without_token")
    return _public_credential_payload(resolution)


def _vision_credential_status(vision_base_url=""):
    if _first_env_token(["MINIAMX_API_KEY", "MINIMAX_API_KEY", "XIAOBEI_VISION_API_KEY", "OPENAI_API_KEY"]):
        return _base_credential_payload(CREDENTIAL_SOURCE_ENV, True)
    if _first_env_token(["ANTHROPIC_API_KEY"]):
        return _base_credential_payload(
            CREDENTIAL_SOURCE_MISSING,
            False,
            reason="anthropic_env_not_valid_for_vision_provider",
        )
    openclaw_status = _openclaw_auth_profile_status(read_token=True)
    if openclaw_status.get("credential_available"):
        return _public_openclaw_credential_status(openclaw_status)
    if openclaw_status.get("credential_source") == CREDENTIAL_SOURCE_INVALID:
        return _public_openclaw_credential_status(openclaw_status)
    if _is_local_base_url(vision_base_url):
        return _base_credential_payload(CREDENTIAL_SOURCE_DISABLED, True)
    return _base_credential_payload(CREDENTIAL_SOURCE_MISSING, False)


def _public_openclaw_credential_status(status):
    source = status.get("credential_source") or CREDENTIAL_SOURCE_INVALID
    return _base_credential_payload(
        source,
        bool(status.get("credential_available")),
        external_profile_used=bool(status.get("external_profile_used")),
        openclaw_auth_profile_used=bool(status.get("openclaw_auth_profile_used")),
        profile_path_redacted=status.get("profile_path_redacted") or "",
        reason=status.get("reason") or "",
    )


def _public_credential_payload(resolution):
    public = {
        key: deepcopy_value
        for key, deepcopy_value in dict(resolution or {}).items()
        if key not in {"token", "_token", "_path"}
    }
    public["token_preview"] = None
    public["credential_source"] = public.get("credential_source") if public.get("credential_source") in ALLOWED_CREDENTIAL_SOURCES else CREDENTIAL_SOURCE_INVALID
    public["credential_available"] = bool(public.get("credential_available"))
    public["external_profile_used"] = bool(public.get("external_profile_used"))
    public["openclaw_auth_profile_used"] = bool(public.get("openclaw_auth_profile_used"))
    return public


def _redact_secret_text(value):
    text = str(value or "")
    replacements = [
        (r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer <REDACTED>"),
        (r"sk-[A-Za-z0-9._\-]{8,}", "sk-<REDACTED>"),
        (r"(api[_-]?key[\"'\s:=]+)[A-Za-z0-9._\-]+", r"\1<REDACTED>"),
        (r"(access[_-]?token[\"'\s:=]+)[A-Za-z0-9._\-]+", r"\1<REDACTED>"),
        (r"(refresh[_-]?token[\"'\s:=]+)[A-Za-z0-9._\-]+", r"\1<REDACTED>"),
        (r"(secret[\"'\s:=]+)[A-Za-z0-9._\-]+", r"\1<REDACTED>"),
        (r"C:\\Users\\Administrator", r"<USER_HOME_REDACTED>"),
    ]
    for pattern, replacement in replacements:
        text = __import__("re").sub(pattern, replacement, text, flags=__import__("re").IGNORECASE)
    return text


def _resolve_openai_compatible_endpoint(base_url):
    base_text = (base_url or "").lower()
    if base_text.endswith("/text/chatcompletion_v2"):
        return ""
    if "api.minimaxi.com" in base_text:
        return "/text/chatcompletion_v2"
    return "/chat/completions"


def _normalize_generation_base_url(value):
    text = str(value or "").strip().rstrip("/")
    lower = text.lower()
    if lower.endswith("/text/chatcompletion_v2"):
        return text[: -len("/text/chatcompletion_v2")]
    if lower.endswith("/chat/completions"):
        return text[: -len("/chat/completions")]
    return text


def _raise_openai_compatible_business_error(parsed, base_url):
    if not isinstance(parsed, dict):
        return
    base_resp = parsed.get("base_resp")
    if not isinstance(base_resp, dict):
        return
    status_code = base_resp.get("status_code")
    if status_code in {None, "", 0, "0"}:
        return
    status_text = str(status_code)
    status_msg = str(base_resp.get("status_msg") or "").strip()
    detail = f"Provider business error {status_text}"
    if status_msg:
        detail = f"{detail}: {status_msg}"
    if str(status_code) in {"2049", "401"} or "invalid api key" in status_msg.lower():
        raise ProviderError("provider_auth_failed", detail, meta={"base_url": base_url, "status_code": status_code})
    raise ProviderError("provider_internal_error", detail, meta={"base_url": base_url, "status_code": status_code})


def _sanitize_openai_compatible_text(raw_text, base_url):
    if not isinstance(raw_text, str):
        return raw_text
    if "api.minimaxi.com" in (base_url or "").lower():
        return _unwrap_fenced_json(raw_text)
    return raw_text


def _extract_anthropic_text_content(parsed):
    content = parsed.get("content")
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    return _unwrap_fenced_json("\n".join(parts).strip())


def _unwrap_fenced_json(text):
    if not isinstance(text, str):
        return ""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return stripped


def _resolve_openclaw_minimax_api_key():
    status = _openclaw_auth_profile_status(read_token=True)
    return str(status.get("_token") or "").strip()


def _candidate_openclaw_auth_profile_paths():
    status = _openclaw_auth_profile_status(read_token=False)
    path = status.get("_path")
    return [path] if isinstance(path, Path) else []


def _openclaw_auth_profile_status(read_token=False):
    if not _truthy_env("XIAOBEI_ALLOW_OPENCLAW_AUTH_PROFILE"):
        return _base_credential_payload(
            CREDENTIAL_SOURCE_DISABLED,
            False,
            reason="openclaw_auth_profile_disabled",
        )
    explicit = (os.environ.get("XIAOBEI_OPENCLAW_AUTH_PROFILE_PATH") or "").strip()
    if not explicit:
        return _base_credential_payload(
            CREDENTIAL_SOURCE_INVALID,
            False,
            reason="missing_explicit_openclaw_auth_profile_path",
        )
    if _is_production_mode():
        return _base_credential_payload(
            CREDENTIAL_SOURCE_INVALID,
            False,
            reason="openclaw_auth_profile_disabled_in_production",
            profile_path_redacted="<OPENCLAW_AUTH_PROFILE_PATH_REDACTED>",
        )
    path = Path(explicit).expanduser()
    if not _is_allowed_openclaw_profile_path(path):
        return _base_credential_payload(
            CREDENTIAL_SOURCE_INVALID,
            False,
            reason="openclaw_auth_profile_path_not_allowlisted",
            profile_path_redacted="<OPENCLAW_AUTH_PROFILE_PATH_REDACTED>",
        )
    if not read_token:
        payload = _base_credential_payload(
            CREDENTIAL_SOURCE_OPENCLAW_OPT_IN,
            False,
            external_profile_used=False,
            openclaw_auth_profile_used=False,
            profile_path_redacted="<OPENCLAW_AUTH_PROFILE_PATH_REDACTED>",
            reason="openclaw_auth_profile_explicit_opt_in_not_read",
        )
        payload["_path"] = path
        return payload
    token = _read_openclaw_minimax_token(path)
    payload = _base_credential_payload(
        CREDENTIAL_SOURCE_OPENCLAW_OPT_IN if token else CREDENTIAL_SOURCE_MISSING,
        bool(token),
        external_profile_used=bool(token),
        openclaw_auth_profile_used=bool(token),
        profile_path_redacted="<OPENCLAW_AUTH_PROFILE_PATH_REDACTED>",
        reason="openclaw_auth_profile_explicit_opt_in" if token else "openclaw_auth_profile_token_missing",
    )
    payload["_path"] = path
    payload["_token"] = token
    return payload


def _is_allowed_openclaw_profile_path(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except Exception:
        return False
    if resolved.name != "auth-profiles.json":
        return False
    roots = []
    explicit_root = (os.environ.get("XIAOBEI_OPENCLAW_AUTH_PROFILE_ALLOWLIST_ROOT") or "").strip()
    if explicit_root:
        roots.append(Path(explicit_root).expanduser())
    else:
        roots.append(Path.home() / ".openclaw" / "agents")
    for root in roots:
        try:
            resolved_root = root.resolve()
            if resolved == resolved_root or resolved_root in resolved.parents:
                return True
        except Exception:
            continue
    return False


def _read_openclaw_minimax_token(path: Path):
    try:
        if not path.exists():
            return ""
        parsed = json.loads(path.read_text(encoding="utf-8"))
        profiles = parsed.get("profiles") if isinstance(parsed, dict) else None
        if not isinstance(profiles, dict):
            return ""
        record = profiles.get("minimax-portal:default")
        if not isinstance(record, dict):
            return ""
        return str(record.get("access") or "").strip()
    except Exception:
        return ""


def generate_raw_response_from_payload(payload, provider="mock", model="mock_qinglv_v1"):
    return {
        "success": True,
        "raw_text": json.dumps(payload, ensure_ascii=False),
        "provider_meta": {
            "provider": provider,
            "model": model,
            "fixture": "inline_override",
        },
    }
