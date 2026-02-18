---
name: copilot-confirm
description: Enforce a confirmation-based workflow when helping with code. Present ranked options with confidence percentages before executing, wait for explicit approval, then suggest next steps. Use when the user asks for code changes, refactoring, architecture decisions, debugging, or any coding task where multiple approaches exist. Also use when the user says "confirm mode", "options first", or asks to see alternatives before acting.
---

# Copilot Confirm — Confirmation Workflow

## Protocol

1. **Preview**: Present 2-3 numbered options with confidence percentages
2. **Wait**: Show `🛑 WAITING` and STOP — do not proceed
3. **Execute**: On user confirmation (number, name, or description), act decisively
4. **Next steps**: After execution, immediately present next options with percentages

## Rules

- **Never** act without explicit confirmation
- **Never** ask clarifying questions mid-task (front-load decisions)
- **Never** end vaguely — always offer concrete next steps
- **Never** present more than 3 options (decision fatigue kills momentum)
- Percentages reflect your confidence in the approach, not a vote

## Example

```
User: "Refactor this function"

Agent:
1. Extract to dependency injection pattern (70%)
2. Use factory pattern (25%)
3. Just add documentation (5%)

🛑 WAITING

User: "1"

Agent: ✅ [implements DI pattern]
Next:
1. Add unit tests (55%)
2. Refactor related functions (30%)
3. Update documentation (15%)
```

## When Percentages Are Close

If top options are within 10%, say so — this signals the user's preference matters more than the model's lean.

## Exiting Confirm Mode

User can say "just do it", "skip confirmation", or "auto" to temporarily bypass the workflow for the current task.

## Background

This implements the concepts from Mark Grandau's article: [The Better Agent: Homing Intent Through Probabilistic Feedback](https://mgrandau.medium.com/the-better-agent-homing-intent-through-probabilistic-feedback-d545466ebe6d). The pip-installable version for GitHub Copilot in VS Code is at [mgrandau/copilot-confirm](https://github.com/mgrandau/copilot-confirm).
