---
name: module-done
description: Check a module's "Done when" list item by item with evidence (commands run, raw output, file references). Use before declaring any module of the lead-gen platform finished.
---

# module-done

1. Read the module's `docs/plans/module-NN-*.md`, sections "Done when" and "Terminal tests".
2. For each "Done when" item, gather evidence: run the command, or point to the file and line. Show the raw output.
3. Never tick an item without evidence. Mark items that can't be checked locally (staging, CI on GitHub) as "deferred" with the reason.
4. Report: item | done / not done / deferred | evidence.
