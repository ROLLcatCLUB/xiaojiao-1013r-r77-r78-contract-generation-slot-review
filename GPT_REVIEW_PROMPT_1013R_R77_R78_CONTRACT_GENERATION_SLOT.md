# GPT Review Prompt: 1013R R77-R78 Contract Generation Slot

Please review this lightweight package as a contract-visualization and model-smoke checkpoint.

## Task

Check whether R77/R78 correctly demonstrate the intended direction:

- A copied static sample page carries contract IDs.
- Each generated object has a visible contract ID.
- Generated model output is mounted into a blue generation slot after the original body/field content.
- The original page content is not overwritten.
- R78 proves a small real model call can produce slot-bound content.

## Must Pass

```text
R77 static sample page exists.
Orange chips show concrete contract IDs, not generic "contract" labels.
Blue generation slots are separate from original field text.
R78 model smoke result is PASS.
provider_called=true.
model_called=true.
formal_apply_performed=false.
main_r21_modified=false.
database_written=false.
feishu_written=false.
memory_written=false.
```

## Important Boundary

Do not judge this as final runtime integration. It is not the production R21 page and not a full model runtime. It is a controlled static sample for teacher-side review of contract placement and generation-slot placement.

## Suggested Verdict Labels

- `PASS_R77_R78_CONTRACT_SLOT_DIRECTION`
- `PASS_WITH_NOTES_LAYOUT_TUNING_NEEDED`
- `FAIL_SLOT_PLACEMENT_OR_BOUNDARY`
