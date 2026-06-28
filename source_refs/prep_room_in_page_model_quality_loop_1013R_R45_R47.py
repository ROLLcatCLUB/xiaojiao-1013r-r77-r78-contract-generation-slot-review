from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from . import prep_room_model_quality_loop_1013R_R40_R44 as r40_r44
from . import prep_room_single_lesson_viewmodel_1013R_R10 as r10_viewmodel


STAGE_ID = "1013R_R45_R47_IN_PAGE_MODEL_QUALITY_LOOP_INTEGRATION"
STATE_ROUTE = "/api/prep-room/model-quality/state"
GENERATE_ROUTE = "/api/prep-room/model-quality/generate"
REGENERATE_ROUTE = "/api/prep-room/model-quality/regenerate"

DEFAULT_CONTEXT = {
    "lesson": "三年级美术 2-1《色彩的渐变》",
    "source": "current_workbench_prep_room",
    "context_source": "workbench/index.html in-page component",
    "before_text": r40_r44.CASE_BEFORE_TEXT,
    "teacher_problem": r40_r44.CASE_INPUT,
}

CANDIDATE_TYPES = [
    {
        "id": "teaching_process_cleanup",
        "label": "教学过程整理",
        "target_slot": "当前教案教学过程预览槽",
    },
    {
        "id": "courseware_script_candidate",
        "label": "课件脚本候选",
        "target_slot": "右侧课件/课件制作预览",
    },
    {
        "id": "classroom_display_candidate",
        "label": "大屏呈现候选",
        "target_slot": "大屏草稿预览",
    },
    {
        "id": "worksheet_candidate",
        "label": "学习单候选",
        "target_slot": "学生任务单预览",
    },
    {
        "id": "assessment_rubric_candidate",
        "label": "评价维度候选",
        "target_slot": "评价表预览",
    },
]

CANONICAL_FIELD_BINDINGS = {
    "teaching_process_cleanup": {
        "default": ("lesson_task_chain", "lesson_task_chain", "lesson_chain"),
        "teacher_action": ("learning_progression", "learning_progression", "learning_progression"),
        "student_action": ("lesson_task_chain", "lesson_task_chain", "lesson_chain"),
        "screen_seed": ("skills_materials_scaffolds", "skills_materials_scaffolds", "materials_scaffolds"),
        "evidence": ("assessment_evidence", "assessment_evidence", "assessment_evidence"),
        "section_item": ("lesson_task_chain", "lesson_task_chain", "lesson_chain"),
    },
    "courseware_script_candidate": {
        "default": ("skills_materials_scaffolds", "skills_materials_scaffolds", "materials_scaffolds"),
        "courseware_screen": ("skills_materials_scaffolds", "skills_materials_scaffolds", "materials_scaffolds"),
    },
    "classroom_display_candidate": {
        "default": ("skills_materials_scaffolds", "skills_materials_scaffolds", "materials_scaffolds"),
        "big_screen_short_text": ("skills_materials_scaffolds", "skills_materials_scaffolds", "materials_scaffolds"),
    },
    "worksheet_candidate": {
        "default": ("assessment_evidence", "assessment_evidence", "assessment_evidence"),
        "section_item": ("assessment_evidence", "assessment_evidence", "assessment_evidence"),
    },
    "assessment_rubric_candidate": {
        "default": ("assessment_evidence", "assessment_evidence", "assessment_evidence"),
        "section_item": ("assessment_evidence", "assessment_evidence", "assessment_evidence"),
        "evidence": ("assessment_evidence", "assessment_evidence", "assessment_evidence"),
    },
}


def _boundary(provider_called: bool = False, model_called: bool = False) -> dict[str, Any]:
    boundary = r40_r44.boundary_flags(STAGE_ID, provider_called, model_called)
    boundary.update(
        {
            "in_page_integration": True,
            "main_outcome_is_workbench_component": True,
            "standalone_html_is_main_outcome": False,
            "formal_apply_allowed": False,
            "save_allowed": False,
            "export_allowed": False,
            "archive_allowed": False,
            "database_write_allowed": False,
            "feishu_write_allowed": False,
            "memory_write_allowed": False,
            "overwrite_original_allowed": False,
        }
    )
    return boundary


def _provider_status() -> dict[str, Any]:
    return r40_r44._provider_public_status()


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value in (None, ""):
        return []
    return [str(value)]


def _candidate_label(candidate_type: str) -> str:
    for item in CANDIDATE_TYPES:
        if item["id"] == candidate_type:
            return item["label"]
    return candidate_type


def _target_slot(candidate_type: str) -> str:
    for item in CANDIDATE_TYPES:
        if item["id"] == candidate_type:
            return item["target_slot"]
    return "当前页面候选预览槽"


def _canonical_binding(candidate_type: str, target_field: str) -> dict[str, str]:
    bindings = CANONICAL_FIELD_BINDINGS.get(candidate_type) or {}
    canonical, target, alias = bindings.get(target_field) or bindings.get("default") or ("lesson_task_chain", "lesson_task_chain", "lesson_chain")
    return {
        "canonical_field_key": canonical,
        "target_field_key": target,
        "explicit_alias_of": canonical,
        "current_alias": alias,
    }


def _has_required_canonical_binding(patch: dict[str, Any]) -> bool:
    return all(str(patch.get(key) or "").strip() for key in ("canonical_field_key", "target_field_key", "explicit_alias_of"))


def _with_canonical_binding(candidate_type: str, target_field: str, patch: dict[str, Any]) -> dict[str, Any]:
    return {**_canonical_binding(candidate_type, target_field), **patch}


def _prompt(candidate_type: str, before_text: str, adjustment_text: str = "", previous_text: str = "") -> tuple[str, str]:
    label = _candidate_label(candidate_type)
    lesson = r10_viewmodel.build_current_lesson()
    compact_context = {
        "sections": [
            {"section_id": item.get("id"), "title": item.get("title"), "items": item.get("items", [])}
            for item in lesson.get("sections", [])
        ],
        "process_steps": [
            {
                "step_id": item.get("id"),
                "title": item.get("title"),
                "teacher_action": item.get("teacher_action"),
                "student_action": item.get("student_action"),
                "screen_seed": item.get("screen_seed"),
                "evidence": item.get("evidence"),
            }
            for item in lesson.get("process_steps", [])
        ],
        "big_screen_short_text": lesson.get("big_screen_short_text", []),
    }
    system = (
        "你是师维智教里的小教页面内候选生成器。只输出 JSON。"
        "候选只能用于当前工作台页面预览和质量观察，不能保存、导出、归档、写数据库、写飞书、写记忆或覆盖原教案。"
        "必须贴合三年级美术《色彩的渐变》，缺依据时要写 missing_requirements 或 blocked。"
        "你必须先根据教学设计字段形成整体判断，再拆成字段补丁，不要只输出一整段教案。"
    )
    user = {
        "stage": STAGE_ID,
        "candidate_type": candidate_type,
        "candidate_label": label,
        "lesson": DEFAULT_CONTEXT["lesson"],
        "lesson_design_field_context": compact_context,
        "before_text": before_text or DEFAULT_CONTEXT["before_text"],
        "previous_candidate": previous_text,
        "teacher_adjustment": adjustment_text,
        "target_slot": _target_slot(candidate_type),
        "rules": [
            "不要虚构教材页码、学生数据、真实班级情况或不存在的素材",
            "输出要让老师能直接二次编辑",
            "评价维度依据不足时可以 blocked",
            "候选内容不自动采纳",
            "field_patch_candidates 必须落到 section_id 或 step_id + target_field",
            "field_patch_candidates 必须携带 canonical_field_key、target_field_key、explicit_alias_of；缺任一项会被拒绝进入页面编辑卡",
            "work_object_patch.review_status 必须为 pending_teacher_review，applied 必须为 false",
        ],
        "output_schema": {
            "candidate_id": "string",
            "status": "generated | blocked",
            "lesson_design_brief": {
                "core_learning_problem": "string",
                "target_shift": "string",
                "teaching_route": ["string"],
                "evidence_plan": ["string"],
            },
            "target_resolution": [
                {
                    "section_id": "basis | analysis | goals | keypoints | preparation | teaching_process | assessment | reflection",
                    "step_id": "intro | sense | explore | make | share | empty",
                    "target_field": "teacher_action | student_action | screen_seed | evidence | section_item | big_screen_short_text | courseware_screen",
                    "reason": "string",
                }
            ],
            "before_or_context": "string",
            "candidate_content": "string",
            "field_patch_candidates": [
                {
                    "field_patch_id": "string",
                    "target_section": "string",
                    "target_step_id": "string",
                    "target_field": "string",
                    "canonical_field_key": "unit_basic_info | curriculum_basis | core_literacy_goals | student_starting_point | unit_questions | knowledge_and_skills | performance_task | learning_progression | lesson_task_chain | assessment_evidence | skills_materials_scaffolds | material_requests",
                    "target_field_key": "string",
                    "explicit_alias_of": "canonical field key",
                    "before_summary": "string",
                    "after_candidate": "string",
                    "reasoning_basis": ["string"],
                    "impact_scope": ["string"],
                    "teacher_review_required": True,
                    "formal_apply_performed": False,
                }
            ],
            "impact_scope": [
                {
                    "affected_object": "big_screen | worksheet | assessment_rubric | courseware_screen | teacher_action | student_activity",
                    "impact_summary": "string",
                    "requires_teacher_confirmation": True,
                }
            ],
            "work_object_patch": {
                "patch_id": "string",
                "target_work_object": "prep_room.current_lesson",
                "changed_fields": ["string"],
                "review_status": "pending_teacher_review",
                "applied": False,
                "rollback_available": True,
            },
            "xiaojiao_suggestion": "string",
            "missing_requirements": ["string"],
            "risk_notes": ["string"],
        },
    }
    return system, json.dumps(user, ensure_ascii=False, indent=2)


def _field_patch_id(candidate_type: str, step_id: str, field: str) -> str:
    return f"{candidate_type}_{step_id}_{field}"


def _fallback_field_patches(candidate_type: str, content: str, before_text: str) -> list[dict[str, Any]]:
    if candidate_type == "teaching_process_cleanup":
        return [
            _with_canonical_binding(candidate_type, "teacher_action", {
                "field_patch_id": _field_patch_id(candidate_type, "intro", "teacher_action"),
                "target_section": "teaching_process",
                "target_step_id": "intro",
                "target_field": "teacher_action",
                "before_summary": "出示自然图片和教材页，引导学生找变化。",
                "after_candidate": "先出示教材页和自然渐变图，让学生沿色带说出颜色从哪里到哪里、明暗或鲜灰如何变化。",
                "reasoning_basis": ["先把观察任务说清楚，避免学生只说好看。"],
                "impact_scope": ["大屏需要一张自然渐变图", "学生回答形成本课观察证据"],
                "teacher_review_required": True,
                "formal_apply_performed": False,
            }),
            _with_canonical_binding(candidate_type, "student_action", {
                "field_patch_id": _field_patch_id(candidate_type, "sense", "student_action"),
                "target_section": "teaching_process",
                "target_step_id": "sense",
                "target_field": "student_action",
                "before_summary": "比较哪一格更亮、哪一格更灰，并尝试排序。",
                "after_candidate": "学生按深浅、鲜灰或明暗把 3 到 5 张色卡重新排序，并用一句话说明排序依据。",
                "reasoning_basis": ["把比较变成学生可操作的判断任务。"],
                "impact_scope": ["学习单可增加色阶排序记录", "评价看学生能否说出依据"],
                "teacher_review_required": True,
                "formal_apply_performed": False,
            }),
            _with_canonical_binding(candidate_type, "evidence", {
                "field_patch_id": _field_patch_id(candidate_type, "explore", "evidence"),
                "target_section": "teaching_process",
                "target_step_id": "explore",
                "target_field": "evidence",
                "before_summary": "试色纸保留过程。",
                "after_candidate": "保留每一步试色纸，并让学生圈出最自然的一组渐变，作为过程证据。",
                "reasoning_basis": ["让生成内容落到评价证据，而不是只变成流程文字。"],
                "impact_scope": ["评价表需要过程证据项", "课后档案可收试色照片"],
                "teacher_review_required": True,
                "formal_apply_performed": False,
            }),
        ]
    if candidate_type == "courseware_script_candidate":
        return [
            _with_canonical_binding(candidate_type, "courseware_screen", {
                "field_patch_id": _field_patch_id(candidate_type, "courseware", "courseware_screen"),
                "target_section": "courseware_script",
                "target_step_id": "",
                "target_field": "courseware_screen",
                "before_summary": "8 屏课件草稿已有标题和状态。",
                "after_candidate": content or "按观察、比较、试色、展示四组屏幕整理课件脚本。",
                "reasoning_basis": ["课件只作为教学过程的屏幕支撑。"],
                "impact_scope": ["大屏预览", "课堂流程"],
                "teacher_review_required": True,
                "formal_apply_performed": False,
            })
        ]
    if candidate_type == "classroom_display_candidate":
        return [
            _with_canonical_binding(candidate_type, "big_screen_short_text", {
                "field_patch_id": _field_patch_id(candidate_type, "display", "big_screen_short_text"),
                "target_section": "classroom_display_screen",
                "target_step_id": "",
                "target_field": "big_screen_short_text",
                "before_summary": "颜色慢慢变，层次就出现。",
                "after_candidate": content or "每屏只保留一个观察任务和一句短提示。",
                "reasoning_basis": ["大屏应该服务于课堂观察，不替代教案正文。"],
                "impact_scope": ["大屏草稿", "教学过程"],
                "teacher_review_required": True,
                "formal_apply_performed": False,
            })
        ]
    if candidate_type == "worksheet_candidate":
        return [
            _with_canonical_binding(candidate_type, "section_item", {
                "field_patch_id": _field_patch_id(candidate_type, "assessment", "section_item"),
                "target_section": "assessment",
                "target_step_id": "",
                "target_field": "section_item",
                "before_summary": "学习单记录色阶顺序、调色发现和一次修改理由。",
                "after_candidate": content or "学习单增加：色阶顺序、我发现的变化、我修改的一处。",
                "reasoning_basis": ["学习单承接学生过程证据。"],
                "impact_scope": ["学习单", "评价证据"],
                "teacher_review_required": True,
                "formal_apply_performed": False,
            })
        ]
    return []


def _normalize_field_patches(candidate_type: str, payload: dict[str, Any], content: str, before_text: str) -> list[dict[str, Any]]:
    raw = payload.get("field_patch_candidates")
    patches = raw if isinstance(raw, list) else []
    normalized: list[dict[str, Any]] = []
    allowed_sections = {"basis", "analysis", "goals", "keypoints", "preparation", "teaching_process", "assessment", "reflection", "courseware_script", "classroom_display_screen"}
    allowed_steps = {"", "intro", "sense", "explore", "make", "share", "courseware", "display"}
    for index, patch in enumerate(patches):
        if not isinstance(patch, dict):
            continue
        section = str(patch.get("target_section") or patch.get("section_id") or "teaching_process")
        step = str(patch.get("target_step_id") or patch.get("step_id") or "")
        target_field = str(patch.get("target_field") or "section_item")
        after = str(patch.get("after_candidate") or patch.get("candidate_text") or "").strip()
        if section not in allowed_sections or step not in allowed_steps or not after:
            continue
        if not _has_required_canonical_binding(patch):
            continue
        normalized.append(
            {
                "field_patch_id": str(patch.get("field_patch_id") or f"{candidate_type}_{index + 1}"),
                "target_section": section,
                "target_step_id": step,
                "target_field": target_field,
                "canonical_field_key": str(patch.get("canonical_field_key")),
                "target_field_key": str(patch.get("target_field_key")),
                "explicit_alias_of": str(patch.get("explicit_alias_of")),
                "current_alias": str(patch.get("current_alias") or ""),
                "before_summary": str(patch.get("before_summary") or patch.get("current_text") or before_text),
                "after_candidate": after,
                "reasoning_basis": _as_list(patch.get("reasoning_basis")),
                "impact_scope": _as_list(patch.get("impact_scope")),
                "teacher_review_required": True,
                "formal_apply_performed": False,
            }
        )
    return normalized or _fallback_field_patches(candidate_type, content, before_text)


def _normalize_impact_scope(payload: dict[str, Any], patches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw = payload.get("impact_scope")
    if isinstance(raw, list):
        impacts = []
        for item in raw:
            if isinstance(item, dict):
                impacts.append(
                    {
                        "affected_object": str(item.get("affected_object") or "teacher_action"),
                        "impact_summary": str(item.get("impact_summary") or item.get("summary") or ""),
                        "requires_teacher_confirmation": True,
                    }
                )
        if impacts:
            return impacts
    seen: set[str] = set()
    fallback = []
    for patch in patches:
        for text in patch.get("impact_scope") or []:
            if text in seen:
                continue
            seen.add(text)
            fallback.append({"affected_object": "field_patch", "impact_summary": str(text), "requires_teacher_confirmation": True})
    return fallback


def _work_object_patch(candidate_type: str, candidate_id: str, patches: list[dict[str, Any]], payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("work_object_patch") if isinstance(payload.get("work_object_patch"), dict) else {}
    changed_fields = [
        f"{patch.get('target_section')}.{patch.get('target_step_id')}.{patch.get('target_field')}".replace("..", ".")
        for patch in patches
    ]
    canonical_changed_fields = [
        str(patch.get("canonical_field_key"))
        for patch in patches
        if str(patch.get("canonical_field_key") or "").strip()
    ]
    return {
        "patch_id": str(raw.get("patch_id") or f"patch_{candidate_id}"),
        "target_work_object": str(raw.get("target_work_object") or "prep_room.current_lesson"),
        "patch_type": "candidate_update",
        "candidate_type": candidate_type,
        "changed_fields": changed_fields,
        "canonical_changed_fields": list(dict.fromkeys(canonical_changed_fields)),
        "review_status": "pending_teacher_review",
        "source_candidate_id": candidate_id,
        "applied": False,
        "rollback_available": True,
    }


def initial_state() -> tuple[dict[str, Any], int]:
    return {
        "success": True,
        "stage": STAGE_ID,
        "mode": "in_page_model_quality_loop",
        "context": deepcopy(DEFAULT_CONTEXT),
        "candidate_types": deepcopy(CANDIDATE_TYPES),
        "provider": _provider_status(),
        "message": "候选只用于预览和质量观察，不会保存到正式备课本。",
        "boundary": _boundary(),
    }, 200


def _normalize_candidate(candidate_type: str, parsed: dict[str, Any] | None, log: dict[str, Any], before_text: str) -> dict[str, Any]:
    if candidate_type == "assessment_rubric_candidate" and not isinstance(parsed, dict):
        fallback = r40_r44._fallback_candidate(candidate_type, "blocked", "missing_teacher_dimension")
    else:
        fallback = r40_r44._fallback_candidate(candidate_type, "fallback", log.get("reason_code") or "model_unavailable")
    payload = parsed if isinstance(parsed, dict) else fallback
    content = str(payload.get("candidate_content") or payload.get("after_text") or fallback.get("candidate_content") or "").strip()
    status = str(payload.get("status") or ("generated" if content else "blocked")).strip()
    if status == "blocked" and candidate_type != "assessment_rubric_candidate" and content:
        status = "generated"
    if candidate_type == "assessment_rubric_candidate" and "评价" not in content and not _as_list(payload.get("missing_requirements")):
        status = "blocked"
    field_patches = _normalize_field_patches(candidate_type, payload, content, before_text)
    candidate_id = str(payload.get("candidate_id") or fallback.get("candidate_id"))
    return {
        "candidate_id": candidate_id,
        "candidate_type": candidate_type,
        "candidate_label": _candidate_label(candidate_type),
        "target_slot": _target_slot(candidate_type),
        "source": "real_model" if log.get("status") == "success" else "fallback_quality_sandbox",
        "status": status,
        "provider_called": bool(log.get("provider_called")),
        "model_called": bool(log.get("model_called")),
        "sandbox_only": True,
        "formal_apply_allowed": False,
        "overwrite_original_allowed": False,
        "teacher_confirmation_required": True,
        "before_or_context": str(payload.get("before_or_context") or payload.get("before_text") or before_text or DEFAULT_CONTEXT["before_text"]),
        "candidate_content": content,
        "lesson_design_brief": payload.get("lesson_design_brief") if isinstance(payload.get("lesson_design_brief"), dict) else {},
        "target_resolution": payload.get("target_resolution") if isinstance(payload.get("target_resolution"), list) else [],
        "field_patch_candidates": field_patches,
        "impact_scope": _normalize_impact_scope(payload, field_patches),
        "work_object_patch": _work_object_patch(candidate_type, candidate_id, field_patches, payload),
        "xiaojiao_suggestion": str(payload.get("xiaojiao_suggestion") or fallback.get("xiaojiao_suggestion") or "请老师确认后再进入下一步。"),
        "missing_requirements": _as_list(payload.get("missing_requirements") or fallback.get("missing_requirements")),
        "risk_notes": _as_list(payload.get("risk_notes") or fallback.get("risk_notes") or ["需要教师确认", "不得覆盖原文"]),
    }


def _quality_panel(candidate: dict[str, Any]) -> dict[str, Any]:
    scored = r40_r44._score_candidate(
        {
            "candidate_id": candidate["candidate_id"],
            "candidate_type": candidate["candidate_type"],
            "candidate_content": candidate.get("candidate_content") or "",
            "status": "blocked" if candidate.get("status") == "blocked" else "generated",
            "missing_requirements": candidate.get("missing_requirements") or [],
            "risk_notes": candidate.get("risk_notes") or [],
        }
    )
    return {
        "candidate_id": candidate["candidate_id"],
        "candidate_type": candidate["candidate_type"],
        "status": scored.get("status"),
        "scores": scored.get("scores") or {},
        "total_score": scored.get("total_score"),
        "pass_line": scored.get("pass_line", 24),
        "basic_quality_pass": bool(scored.get("basic_quality_pass")),
        "requires_human_attention": bool(scored.get("requires_human_attention", True)),
        "blocked_reason": scored.get("blocked_reason"),
        "adjustment_points": scored.get("prompt_schema_adjustment_points") or [],
    }


def generate_candidate(payload: Any) -> tuple[dict[str, Any], int]:
    request_payload = payload if isinstance(payload, dict) else {}
    candidate_type = str(request_payload.get("candidate_type") or "teaching_process_cleanup").strip()
    if candidate_type not in {item["id"] for item in CANDIDATE_TYPES}:
        return {"success": False, "error": "unsupported_candidate_type", "candidate_type": candidate_type}, 400
    before_text = str(request_payload.get("before_text") or DEFAULT_CONTEXT["before_text"]).strip()
    adjustment_text = str(request_payload.get("adjustment_text") or "").strip()
    system, user = _prompt(candidate_type, before_text, adjustment_text)
    parsed, log = r40_r44._call_provider_json(
        f"R45_R47_in_page_{candidate_type}",
        STAGE_ID,
        candidate_type,
        system,
        user,
        max_tokens=2200,
    )
    candidate = _normalize_candidate(candidate_type, parsed, log, before_text)
    quality = _quality_panel(candidate)
    return {
        "success": True,
        "stage": STAGE_ID,
        "mode": "generate_in_page_candidate",
        "context": {**deepcopy(DEFAULT_CONTEXT), "before_text": before_text},
        "candidate": candidate,
        "quality_panel": quality,
        "model_call_log_redacted": log,
        "message": "候选已回填到当前工作台组件，未保存、未导出、未覆盖。",
        "boundary": _boundary(candidate["provider_called"], candidate["model_called"]),
    }, 200


def regenerate_candidate(payload: Any) -> tuple[dict[str, Any], int]:
    request_payload = payload if isinstance(payload, dict) else {}
    previous = request_payload.get("previous_candidate") if isinstance(request_payload.get("previous_candidate"), dict) else {}
    candidate_type = str(request_payload.get("candidate_type") or previous.get("candidate_type") or "teaching_process_cleanup").strip()
    before_text = str(request_payload.get("before_text") or previous.get("before_or_context") or DEFAULT_CONTEXT["before_text"]).strip()
    adjustment_text = str(request_payload.get("adjustment_text") or "").strip()
    previous_text = str(previous.get("candidate_content") or "").strip()
    if not adjustment_text:
        adjustment_text = "让候选更贴近小学美术课堂，步骤更清楚，减少空泛表达。"
    system, user = _prompt(candidate_type, before_text, adjustment_text, previous_text)
    parsed, log = r40_r44._call_provider_json(
        f"R47_in_page_regenerate_{candidate_type}",
        STAGE_ID,
        f"{candidate_type}_regenerate",
        system,
        user,
        max_tokens=2200,
    )
    v2 = _normalize_candidate(candidate_type, parsed, log, before_text)
    v1_quality = _quality_panel(previous) if previous else {}
    v2_quality = _quality_panel(v2)
    v1_score = int(v1_quality.get("total_score") or 0)
    v2_score = int(v2_quality.get("total_score") or 0)
    comparison = {
        "v1_score": v1_score,
        "v2_score": v2_score,
        "improvement_delta": v2_score - v1_score,
        "improved": v2_score > v1_score,
        "same_score": v2_score == v1_score,
        "v2_basic_quality_pass": bool(v2_quality.get("basic_quality_pass")),
    }
    return {
        "success": True,
        "stage": STAGE_ID,
        "mode": "regenerate_in_page_candidate",
        "context": {**deepcopy(DEFAULT_CONTEXT), "before_text": before_text},
        "v1_candidate": previous,
        "v2_candidate": v2,
        "candidate": v2,
        "quality_panel": v2_quality,
        "comparison": comparison,
        "model_call_log_redacted": log,
        "message": "再生成结果已回填到当前工作台组件，未保存、未导出、未覆盖。",
        "boundary": _boundary(v2["provider_called"], v2["model_called"]),
    }, 200
