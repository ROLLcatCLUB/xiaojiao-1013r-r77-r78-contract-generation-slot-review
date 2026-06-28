from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "outputs" / "PREP_ROOM_RENDER_CANVAS_DEEPEN_V1" / "1013R_R77_CONTRACT_ID_STATIC_SAMPLE_PAGE"
MODEL_OUTPUTS = OUT_DIR / "r77_generation_slot_model_outputs.json"
RESULT = OUT_DIR / "validate_1013R_R78_r77_generation_slot_model_smoke_result.json"


TARGET_SLOTS = [
    {
        "contract_id": "R77-DOC-SECTION-BASIS",
        "canonical_field_key": "curriculum_basis",
        "visible_context": "一、本课依据：本课对应三年级第二单元《多彩的世界》第1课《色彩的渐变》，教材页码为第6页。",
        "teacher_intent": "把本课依据写清楚一点，但不要编造教材原文。",
    },
    {
        "contract_id": "R77-ANALYSIS-TEXT-01",
        "canonical_field_key": "student_starting_point",
        "visible_context": "二、学情分析：三年级学生能直观看到颜色深浅、浓淡和鲜灰差异，但容易把渐变理解为混几种颜色。",
        "teacher_intent": "生成一条更像老师能用的学情判断。",
    },
    {
        "contract_id": "R77-PROCESS-TEXT-01",
        "canonical_field_key": "lesson_task_chain",
        "visible_context": "六、教学过程：1. 看见渐变：出示自然图片和教材页。展示差异、指认方向、收住发现。",
        "teacher_intent": "把导入环节生成成更具体、可执行的课堂步骤。",
    },
    {
        "contract_id": "R77-MATERIAL-PROMPT",
        "canonical_field_key": "material_requests",
        "visible_context": "资料补充：缺学生作品样例、评价维度、教材OCR、课堂条件。",
        "teacher_intent": "生成资料补充提示，只提示老师需要补什么，不写进正式课包。",
    },
]


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_json_object(raw_text: str) -> dict[str, Any]:
    text = str(raw_text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].lstrip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    if not text.startswith("{"):
        match = re.search(r"\{.*\}", text, flags=re.S)
        text = match.group(0).strip() if match else text
    return json.loads(text)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    from backend.xiaobei_ai import providers
    from backend.xiaobei_ai import prep_room_in_page_model_quality_loop_1013R_R45_R47 as r45_r47

    system_prompt = (
        "你是师维智教里的小教生成槽 smoke 测试器。只输出 JSON 对象，不要 Markdown。"
        "你正在给一个静态样板页的蓝色生成槽生成预览候选。"
        "所有内容必须 preview_only，不保存、不导出、不写库、不写飞书、不写记忆、不正式采纳。"
        "每个 generated_text 要短、具体、像老师能看懂的备课内容。"
    )
    user_prompt = json.dumps(
        {
            "lesson": "三年级美术 2-1《色彩的渐变》",
            "page": "R77 contract id static sample page",
            "required_output_schema": {
                "generated_slots": [
                    {
                        "contract_id": "must equal input contract_id",
                        "canonical_field_key": "must equal input canonical_field_key",
                        "generated_text": "string, 1-3 teacher-facing sentences",
                        "preview_only": True,
                        "formal_apply_allowed": False,
                    }
                ]
            },
            "target_slots": TARGET_SLOTS,
        },
        ensure_ascii=False,
        indent=2,
    )
    provider_status = r45_r47._provider_status()
    started = time.perf_counter()
    model_log: dict[str, Any] = {
        "call_id": "R78_r77_generation_slot_model_smoke",
        "stage": "1013R_R78_R77_GENERATION_SLOT_MODEL_SMOKE",
        "provider_called": False,
        "model_called": False,
        "status": "not_started",
        "prompt_hash": hashlib.sha256((system_prompt + "\n" + user_prompt).encode("utf-8")).hexdigest(),
    }
    generated_slots: list[dict[str, Any]] = []
    safe_error = ""
    try:
        provider_response = providers.generate_json_patch(
            {"stage": model_log["stage"], "sandbox_only": True, "target": "r77_generation_slots"},
            {"system_prompt": system_prompt, "user_prompt": user_prompt},
            {
                "provider": "openai_compatible",
                "model": provider_status.get("model") or "MiniMax-M3",
                "response_format": "json_object",
                "temperature": 0.25,
                "max_tokens": 2600,
                "timeout_ms": 120000,
            },
        )
        model_log["provider_called"] = True
        model_log["model_called"] = True
        parsed = parse_json_object(provider_response.get("raw_text") or "")
        raw_slots = parsed.get("generated_slots") if isinstance(parsed, dict) else []
        allowed_ids = {slot["contract_id"] for slot in TARGET_SLOTS}
        allowed_fields = {slot["contract_id"]: slot["canonical_field_key"] for slot in TARGET_SLOTS}
        for item in raw_slots if isinstance(raw_slots, list) else []:
            if not isinstance(item, dict):
                continue
            contract_id = str(item.get("contract_id") or "").strip()
            generated_text = str(item.get("generated_text") or "").strip()
            if contract_id not in allowed_ids or not generated_text:
                continue
            generated_slots.append(
                {
                    "stage": model_log["stage"],
                    "contract_id": contract_id,
                    "canonical_field_key": allowed_fields[contract_id],
                    "generated_text": generated_text,
                    "preview_only": True,
                    "formal_apply_allowed": False,
                    "source": "real_model_smoke",
                }
            )
        model_log.update(
            {
                "status": "success",
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "output_slot_count": len(generated_slots),
                "provider_meta": {
                    key: value
                    for key, value in dict(provider_response.get("provider_meta") or {}).items()
                    if key not in {"token", "api_key", "authorization"}
                },
            }
        )
    except Exception as exc:
        safe_error = str(exc)[:1000]
        model_log.update(
            {
                "status": "failed",
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "safe_error": safe_error,
            }
        )

    result = {
        "stage": model_log["stage"],
        "generated_at": now(),
        "status": "PASS" if len(generated_slots) == len(TARGET_SLOTS) else "FAIL",
        "target_page": str((OUT_DIR / "prep_room_contract_id_static_sample_1013R_R77.html").relative_to(ROOT)),
        "model_outputs_file": str(MODEL_OUTPUTS.relative_to(ROOT)),
        "checks": {
            "provider_called": model_log.get("provider_called") is True,
            "model_called": model_log.get("model_called") is True,
            "model_log_success": model_log.get("status") == "success",
            "all_target_slots_generated": len(generated_slots) == len(TARGET_SLOTS),
            "formal_apply_allowed_false": all(slot.get("formal_apply_allowed") is False for slot in generated_slots),
            "preview_only_true": all(slot.get("preview_only") is True for slot in generated_slots),
            "main_r21_modified": False,
        },
        "target_slots": TARGET_SLOTS,
        "generated_slots": generated_slots,
        "model_call_log_redacted": model_log,
        "safe_error": safe_error,
        "boundary": {
            "sandbox_only": True,
            "provider_called": model_log.get("provider_called") is True,
            "model_called": model_log.get("model_called") is True,
            "formal_apply_performed": False,
            "database_written": False,
            "feishu_written": False,
            "memory_written": False,
            "main_r21_modified": False,
            "r77_static_sample_modified": True,
        },
    }
    MODEL_OUTPUTS.write_text(
        json.dumps(
            {
                "stage": model_log["stage"],
                "generated_at": result["generated_at"],
                "generated_slots": generated_slots,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    RESULT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
