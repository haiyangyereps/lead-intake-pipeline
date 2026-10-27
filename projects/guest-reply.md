# Guest Reply Assistant

**Use case:** reduce repetitive drafting while keeping the host in control.

Input: guest question plus a small property knowledge JSON. Output: a draft awaiting approval, or escalation with no draft. Sensitive terms take priority over FAQ matches. There is no send action.

```sh
python3 projects/automation.py guest 'Is parking available?' --knowledge examples/property.json
```

Expected status: `needs_approval`, `sent: false`, with the driveway information.

```sh
python3 projects/automation.py guest 'I need a refund' --knowledge examples/property.json
```

Expected status: `escalate`, `draft: null`.

This is a deterministic prototype, not an AI agent or Airbnb API integration. Next steps: authorized inbox integration, multilingual intent testing, approval UI, audit logging, and evaluation before any LLM integration.
