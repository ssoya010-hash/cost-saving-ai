---
title: Zero side effects contract
summary: Rules every utility in this repo must follow so it never adds AI cost
---
# Zero side effects contract

A utility in `utils/` must:
- print nothing to the agent (hooks: empty stdout) unless the user opts in;
- never block, rewrite commands or edit files the agent uses;
- exit 0 on any internal error;
- add ≤ 0.2 s per hook, doing heavy work in a detached background process;
- keep data local; any network call must be opt-in and send summaries only;
- install idempotently with a backup, and uninstall back to the original state.

Each rule needs an automated test. Reference implementation: [utils/cost-coach](../utils/cost-coach/) (`DESIGN.md`, `tests/`).
