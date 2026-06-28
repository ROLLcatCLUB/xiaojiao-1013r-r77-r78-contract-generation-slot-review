from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "outputs" / "PREP_ROOM_RENDER_CANVAS_DEEPEN_V1" / "1013R_R21_page_copy_binds_unified_package" / "prep_room_page_copy_binds_unified_package_1013R_R21.html"
OUT_DIR = ROOT / "outputs" / "PREP_ROOM_RENDER_CANVAS_DEEPEN_V1" / "1013R_R77_CONTRACT_ID_STATIC_SAMPLE_PAGE"
OUT_HTML = OUT_DIR / "prep_room_contract_id_static_sample_1013R_R77.html"
OUT_JSON = OUT_DIR / "prep_room_contract_id_static_sample_1013R_R77_contracts.json"
MODEL_OUTPUTS_JSON = OUT_DIR / "r77_generation_slot_model_outputs.json"


CONTRACTS = [
    {
        "contract_id": "R77-COVER-UNIT-BASIC-INFO",
        "label": "单元卡",
        "field": "unit_basic_info",
        "selectors": [".nb-cover", ".nb-cover-title", ".nb-cover-sub"],
    },
    {
        "contract_id": "R77-LEFT-LESSON-CATALOG",
        "label": "左侧目录",
        "field": "lesson_task_chain",
        "selectors": [".nb-tree", ".nb-tree-group", ".nb-tree-button"],
    },
    {
        "contract_id": "R77-STATUS-ROW",
        "label": "状态行",
        "field": "lesson_task_chain",
        "selectors": [".nb-state-bar", ".nb-status-row", ".chip-row"],
    },
    {
        "contract_id": "R77-MATERIAL-PROMPT",
        "label": "资料提示",
        "field": "material_requests",
        "selectors": [".nb-material-front-prompt", "[data-r49-material-requests-prompt='true']"],
    },
    {
        "contract_id": "R77-DOC-SECTION-BASIS",
        "label": "本课依据",
        "field": "curriculum_basis",
        "selectors": ["#chunk-render_chunk_basis_1013K_R3", "[data-r21-field-anchor='lesson_basis']"],
    },
    {
        "contract_id": "R77-DOC-SECTION-ANALYSIS",
        "label": "学情分析",
        "field": "student_starting_point",
        "selectors": ["#chunk-render_chunk_analysis_1013K_R3"],
    },
    {
        "contract_id": "R77-DOC-SECTION-GOALS",
        "label": "教学目标",
        "field": "core_literacy_goals",
        "selectors": ["#chunk-render_chunk_goals_1013K_R3"],
    },
    {
        "contract_id": "R77-DOC-SECTION-PREPARATION",
        "label": "教学准备",
        "field": "skills_materials_scaffolds",
        "selectors": ["#chunk-render_chunk_preparation_1013K_R3"],
    },
    {
        "contract_id": "R77-DOC-TEACHING-PROCESS",
        "label": "教学过程",
        "field": "lesson_task_chain",
        "selectors": ["#chunk-render_chunk_process_1013K_R3", ".nb-process-list", ".nb-process-step"],
    },
    {
        "contract_id": "R77-PROCESS-INTRO",
        "label": "导入行",
        "field": "lesson_task_chain",
        "line_contract_id": "line_intro",
        "text_contains": ["看见渐变", "出示自然图片", "展示差异"],
    },
    {
        "contract_id": "R77-PROCESS-COMPARE",
        "label": "比较行",
        "field": "lesson_task_chain",
        "line_contract_id": "line_compare",
        "text_contains": ["比较明度", "同一种颜色加入白色", "比较明度与纯度"],
    },
    {
        "contract_id": "R77-PROCESS-DEMO",
        "label": "示范行",
        "field": "skills_materials_scaffolds",
        "line_contract_id": "line_demo",
        "text_contains": ["做渐变实验", "示范少量多次加色", "示范方法"],
    },
    {
        "contract_id": "R77-PROCESS-EVIDENCE",
        "label": "证据行",
        "field": "assessment_evidence",
        "line_contract_id": "line_evidence",
        "text_contains": ["留下注据", "说明自己怎么调出来", "评价证据"],
    },
    {
        "contract_id": "R77-EDIT-MODAL-BEFORE-AFTER",
        "label": "编辑卡",
        "field": "curriculum_basis",
        "selectors": [".r6p-modal", ".r6p-modal-body", ".r6p-modal-compare"],
    },
    {
        "contract_id": "R77-RIGHT-TOOL-RAIL",
        "label": "右侧工具",
        "field": "skills_materials_scaffolds",
        "selectors": [".nb-right-rail", ".r6p-resource-rail", ".r6p-tool-strip"],
    },
    {
        "contract_id": "R77-MODEL-CANDIDATE-SANDBOX",
        "label": "模型候选",
        "field": "lesson_task_chain",
        "selectors": [".r50-field-strip", "[data-r50-field-aware-edit-card='true']", ".r50-line-contracts"],
    },
    {
        "contract_id": "R77-BOTTOM-XIAOJIAO-JUDGEMENT",
        "label": "底部判断",
        "field": "lesson_task_chain",
        "selectors": [".xiaobei-chat-entry", ".r50-route-toast", ".r6s-static-review-overlay"],
    },
]


def read_generation_outputs() -> list[dict]:
    if not MODEL_OUTPUTS_JSON.exists():
        return []
    try:
        payload = json.loads(MODEL_OUTPUTS_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    items = payload.get("generated_slots") if isinstance(payload, dict) else payload
    return items if isinstance(items, list) else []


def injection() -> str:
    generated_outputs = read_generation_outputs()
    return f"""
  <style id="r77-contract-id-label-style">
    html[data-r77-contract-id-sample="true"] .r77-contract-host {{
      position: relative;
      outline: 1px dashed rgba(219, 134, 33, 0.32);
      outline-offset: 2px;
    }}
    html[data-r77-contract-id-sample="true"] .r77-contract-chip {{
      display: inline-flex;
      align-items: center;
      max-width: 150px;
      margin-left: 6px;
      margin-top: 2px;
      padding: 2px 5px;
      border: 1px solid rgba(219, 134, 33, 0.55);
      border-radius: 6px;
      background: rgba(255, 245, 225, 0.96);
      color: #8a4b00;
      font-size: 8px;
      font-weight: 800;
      line-height: 1.2;
      vertical-align: middle;
      box-shadow: 0 3px 10px rgba(116, 77, 16, 0.08);
      pointer-events: auto;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    html[data-r77-contract-id-sample="true"] .r77-contract-chip strong {{
      color: #9c5708;
      font-size: 10px;
      margin-right: 4px;
    }}
    html[data-r77-contract-id-sample="true"] .r77-contract-chip[data-r77-field="material_requests"] {{
      border-color: rgba(197, 80, 52, 0.5);
      background: rgba(255, 239, 232, 0.96);
      color: #8b3124;
    }}
    html[data-r77-contract-id-sample="true"] .r77-generation-slot {{
      display: flex;
      align-items: center;
      width: fit-content;
      max-width: min(420px, 96%);
      min-height: 20px;
      margin: 4px 0 6px 0;
      padding: 3px 7px;
      border: 1px solid rgba(47, 111, 191, 0.4);
      border-radius: 6px;
      background: rgba(235, 245, 255, 0.96);
      color: #24558d;
      font-size: 8px;
      font-weight: 700;
      line-height: 1.25;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      clear: both;
    }}
    html[data-r77-contract-id-sample="true"] .r77-generation-slot::before {{
      content: "GEN";
      margin-right: 4px;
      color: #2f6fbf;
      font-size: 7px;
      font-weight: 900;
    }}
    html[data-r77-contract-id-sample="true"] .r77-generation-slot[data-r77-generated="true"] {{
      max-width: min(560px, 98%);
      white-space: normal;
      overflow: visible;
      text-overflow: clip;
      align-items: flex-start;
      background: rgba(226, 241, 255, 0.98);
      border-color: rgba(47, 111, 191, 0.62);
      color: #163f70;
    }}
    html[data-r77-contract-id-sample="true"] .r77-contract-legend {{
      position: fixed;
      left: 22px;
      top: 154px;
      z-index: 120;
      width: 245px;
      padding: 8px 10px;
      border: 1px solid rgba(219, 134, 33, 0.42);
      border-radius: 8px;
      background: rgba(255, 252, 244, 0.96);
      color: #70430d;
      font-size: 11px;
      line-height: 1.45;
      box-shadow: 0 10px 28px rgba(69, 55, 22, 0.12);
    }}
    html[data-r77-contract-id-sample="true"] .r77-contract-legend strong {{
      display: block;
      color: #9c5708;
      font-size: 12px;
      margin-bottom: 3px;
    }}
    @media (max-width: 1100px) {{
      html[data-r77-contract-id-sample="true"] .r77-contract-legend {{
        position: static;
        width: auto;
        margin: 8px 12px;
      }}
    }}
  </style>
  <script id="r77-contract-id-label-data" type="application/json">{json.dumps(CONTRACTS, ensure_ascii=False)}</script>
  <script id="r77-generation-slot-model-output-data" type="application/json">{json.dumps(generated_outputs, ensure_ascii=False)}</script>
  <script id="r77-contract-id-label-script">
    (function () {{
      const contracts = {json.dumps(CONTRACTS, ensure_ascii=False)};
      const generatedOutputs = {json.dumps(generated_outputs, ensure_ascii=False)};
      const generatedByContractId = new Map(
        generatedOutputs
          .filter((item) => item && item.contract_id)
          .map((item) => [item.contract_id, item])
      );
      const seen = new WeakSet();
      function chip(item) {{
        const node = document.createElement("span");
        node.className = "r77-contract-chip";
        node.dataset.r77ContractId = item.contract_id;
        node.dataset.r77Field = item.field || "";
        node.title = [
          "contract_id=" + item.contract_id,
          "canonical_field_key=" + (item.field || "unknown"),
          item.line_contract_id ? "line_contract_id=" + item.line_contract_id : "",
          "preview_only=true",
          "formal_apply_allowed=false"
        ].filter(Boolean).join("\\n");
        node.textContent = item.contract_id;
        return node;
      }}
      function generationSlot(item) {{
        const node = document.createElement("span");
        node.className = "r77-generation-slot";
        node.dataset.r77GenerationSlot = "true";
        node.dataset.r77ContractId = item.contract_id;
        node.dataset.canonicalFieldKey = item.field || "";
        node.dataset.previewOnly = "true";
        node.dataset.formalApplyAllowed = "false";
        if (item.line_contract_id) node.dataset.lineContractId = item.line_contract_id;
        const generated = generatedByContractId.get(item.contract_id);
        node.title = [
          "generation_slot_for=" + item.contract_id,
          "canonical_field_key=" + (item.field || "unknown"),
          item.line_contract_id ? "line_contract_id=" + item.line_contract_id : "",
          "model_output_mount_here=true",
          generated ? "model_output_present=true" : "model_output_present=false",
          "preview_only=true",
          "formal_apply_allowed=false"
        ].filter(Boolean).join("\\n");
        if (generated && generated.generated_text) {{
          node.dataset.r77Generated = "true";
          node.dataset.r77ModelStage = generated.stage || "";
          node.textContent = generated.generated_text;
        }} else {{
          node.textContent = "待生成";
        }}
        return node;
      }}
      function hasOwnChip(target) {{
        return !!target?.querySelector?.(":scope > .r77-contract-chip");
      }}
      function safeAppend(target, item) {{
        if (!target || seen.has(target) || hasOwnChip(target)) return false;
        if (target.closest && target.closest(".r77-contract-chip")) return false;
        target.classList.add("r77-contract-host");
        target.dataset.r77ContractId = item.contract_id;
        target.dataset.canonicalFieldKey = item.field || "";
        target.dataset.previewOnly = "true";
        target.dataset.formalApplyAllowed = "false";
        if (item.line_contract_id) target.dataset.lineContractId = item.line_contract_id;
        const marker = chip(item);
        const titleLike = target.querySelector?.(".nb-doc-title,.nb-section-title,.nb-tree-title,.r6p-resource-item strong,.r50-field-strip-title,.r6p-modal-title,strong,h1,h2,h3");
        if (titleLike && !titleLike.querySelector(".r77-contract-chip")) {{
          titleLike.appendChild(marker);
        }} else {{
          target.insertAdjacentElement("afterbegin", marker);
        }}
        appendGenerationSlotAfterContent(target, item);
        seen.add(target);
        return true;
      }}
      function appendGenerationSlotAfterContent(target, item) {{
        if (!target || target.dataset.r77GenerationSlotAttached === "true") return;
        const slot = generationSlot(item);
        target.dataset.r77GenerationSlotAttached = "true";
        const tag = (target.tagName || "").toLowerCase();
        const inlineTags = new Set(["span", "strong", "em", "b", "i", "button", "a"]);
        if (inlineTags.has(tag)) {{
          target.insertAdjacentElement("afterend", slot);
          return;
        }}
        target.insertAdjacentElement("beforeend", slot);
      }}
      function byText(item) {{
        const needles = item.text_contains || [];
        if (!needles.length) return [];
        const candidates = Array.from(document.querySelectorAll(".nb-doc-section li,.nb-doc-section p,.nb-process-step,.nb-step-card,.nb-doc-section"));
        return candidates.filter((node) => needles.some((needle) => (node.textContent || "").includes(needle))).slice(0, 2);
      }}
      function apply() {{
        document.documentElement.setAttribute("data-r77-contract-id-sample", "true");
        if (!document.querySelector(".r77-contract-legend")) {{
          const legend = document.createElement("div");
          legend.className = "r77-contract-legend";
          legend.innerHTML = "<strong>R77 契约ID静态样板</strong>橙色小卡只标注生成物/候选物的契约归属。当前页不接模型、不采纳、不写正式备课本。";
          document.body.appendChild(legend);
        }}
        contracts.forEach((item) => {{
          let targets = [];
          (item.selectors || []).forEach((selector) => {{
            try {{ targets = targets.concat(Array.from(document.querySelectorAll(selector))); }} catch (_) {{}}
          }});
          targets = targets.concat(byText(item));
          targets.slice(0, item.contract_id.includes("LEFT-LESSON") ? 8 : 3).forEach((target) => safeAppend(target, item));
        }});
        autoFillLeftRailContracts();
        autoFillBodyContracts();
      }}
      function slugText(text, fallback) {{
        const value = String(text || "").trim();
        if (!value) return fallback;
        const known = [
          ["三年级美术", "GRADE-SUBJECT"],
          ["2025学年第二学期", "TERM"],
          ["来源", "SOURCE"],
          ["正式课表", "SCHEDULE-SOURCE"],
          ["教学工作计划", "PLAN-SOURCE"],
          ["8节", "OFFICIAL-LESSON-COUNT"],
          ["4项", "PENDING-COUNT"],
          ["1-2", "CURRENT-LESSON-RANGE"],
          ["0次", "REHEARSAL-COUNT"],
          ["学期工作", "TERM-WORK"],
          ["计划", "TERM-PLAN"],
          ["排课", "SCHEDULE"],
          ["周历", "WEEK-CALENDAR"],
          ["大单元", "BIG-UNIT"],
          ["第一单元", "UNIT-01"],
          ["第二单元", "UNIT-02"],
          ["第三单元", "UNIT-03"],
          ["第四单元", "UNIT-04"],
          ["第五单元", "UNIT-05"],
          ["第六单元", "UNIT-06"],
          ["专题", "TOPIC"],
          ["1-1", "LESSON-1-1"],
          ["1-2", "LESSON-1-2"],
          ["2-1", "LESSON-2-1"],
          ["2-2", "LESSON-2-2"],
          ["2-3", "LESSON-2-3"],
          ["3-1", "LESSON-3-1"],
          ["3-2", "LESSON-3-2"],
          ["3-3", "LESSON-3-3"],
          ["4-1", "LESSON-4-1"],
          ["4-2", "LESSON-4-2"],
          ["5-1", "LESSON-5-1"],
          ["5-2", "LESSON-5-2"],
          ["5-3", "LESSON-5-3"]
        ];
        const hit = known.find(([needle]) => value.includes(needle));
        return hit ? hit[1] : `${{fallback}}-${{String(value.length).padStart(2, "0")}}`;
      }}
      function autoFillLeftRailContracts() {{
        Array.from(document.querySelectorAll(".nb-cover-title,.nb-cover-sub,.nb-cover .nb-stat,.nb-cover li,.nb-cover span")).forEach((node, index) => {{
          if ((node.textContent || "").trim().length < 1) return;
          const id = `R77-COVER-${{slugText(node.textContent, `ITEM-${{index + 1}}`)}}`;
          safeAppend(node, {{ contract_id: id, field: "unit_basic_info" }});
        }});
        Array.from(document.querySelectorAll(".nb-tree-title,.nb-tree-button,.nb-tree-group > strong,.nb-tree-group > div,.nb-tree-items > *")).forEach((node, index) => {{
          if ((node.textContent || "").trim().length < 1) return;
          const text = node.textContent || "";
          const field = text.includes("计划") || text.includes("排课") || text.includes("周课表") || text.includes("周历") ? "schedule_context" : "lesson_task_chain";
          const id = `R77-LEFT-${{slugText(text, `ITEM-${{index + 1}}`)}}`;
          safeAppend(node, {{ contract_id: id, field }});
        }});
      }}
      function sectionField(section) {{
        const text = section.textContent || "";
        if (text.includes("本课依据")) return ["BASIS", "curriculum_basis"];
        if (text.includes("学情分析")) return ["ANALYSIS", "student_starting_point"];
        if (text.includes("教学目标")) return ["GOALS", "core_literacy_goals"];
        if (text.includes("教学重难点")) return ["KEYPOINTS", "knowledge_and_skills"];
        if (text.includes("教学准备")) return ["PREP", "skills_materials_scaffolds"];
        if (text.includes("教学过程")) return ["PROCESS", "lesson_task_chain"];
        if (text.includes("学习单") || text.includes("评价")) return ["ASSESS", "assessment_evidence"];
        if (text.includes("课堂后记")) return ["REFLECTION", "assessment_evidence"];
        if (text.includes("材料") || text.includes("支架")) return ["MATERIALS", "skills_materials_scaffolds"];
        return ["DOC", "lesson_task_chain"];
      }}
      function autoId(prefix, index) {{
        return `R77-${{prefix}}-${{String(index + 1).padStart(2, "0")}}`;
      }}
      function autoFillBodyContracts() {{
        const sections = Array.from(document.querySelectorAll(".nb-doc-section"));
        sections.forEach((section, sectionIndex) => {{
          const [prefix, field] = sectionField(section);
          safeAppend(section, {{ contract_id: `R77-${{prefix}}-SECTION`, field, label: prefix }});
          Array.from(section.querySelectorAll(".nb-doc-title,h2,h3,h4")).forEach((node, index) => {{
            safeAppend(node, {{ contract_id: autoId(`${{prefix}}-TITLE`, index), field }});
          }});
          Array.from(section.querySelectorAll(":scope > p, :scope > ul > li, :scope li, :scope .nb-section-candidate, :scope .nb-doc-subnote")).forEach((node, index) => {{
            safeAppend(node, {{ contract_id: autoId(`${{prefix}}-TEXT`, index), field }});
          }});
          Array.from(section.querySelectorAll("button,.node-action,.nb-soft-button,.courseware-inline-chip,.quiet-tag")).forEach((node, index) => {{
            safeAppend(node, {{ contract_id: autoId(`${{prefix}}-ACTION`, index), field }});
          }});
        }});
        Array.from(document.querySelectorAll(".nb-process-step,.nb-step-card,[data-step-id],.courseware-placeholder,.courseware-screen-mini")).forEach((node, index) => {{
          safeAppend(node, {{ contract_id: autoId("PROCESS-LINE", index), field: "lesson_task_chain", line_contract_id: autoId("LINE", index) }});
        }});
        Array.from(document.querySelectorAll(".r6p-resource-item,.r6p-tool,.r50-line-contract,.r50-modal-card,.r6p-modal-block,.r6p-modal-compare-box")).forEach((node, index) => {{
          safeAppend(node, {{ contract_id: autoId("SIDE-CANDIDATE", index), field: index % 2 ? "skills_materials_scaffolds" : "assessment_evidence" }});
        }});
      }}
      if (document.readyState === "loading") {{
        document.addEventListener("DOMContentLoaded", apply);
      }} else {{
        apply();
      }}
      setTimeout(apply, 500);
      window.__R77_CONTRACT_ID_STATIC_SAMPLE__ = {{ contracts, apply }};
    }})();
  </script>
"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC, OUT_HTML)
    html = OUT_HTML.read_text(encoding="utf-8")
    if "r77-contract-id-label-script" not in html:
        html = html.replace("</body>", injection() + "\n</body>")
    OUT_HTML.write_text(html, encoding="utf-8")
    OUT_JSON.write_text(json.dumps({"stage": "1013R_R77_CONTRACT_ID_STATIC_SAMPLE_PAGE", "source": str(SRC), "html": str(OUT_HTML), "contracts": CONTRACTS}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PASS", "html": str(OUT_HTML), "contracts": len(CONTRACTS)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
