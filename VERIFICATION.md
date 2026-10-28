# Version 0.4 verification

- 27 automated tests passed (`python3 -m unittest discover -s tests -v`).
- Live inference tested through an operator-configured OpenAI-compatible service.
- `live-result.json`: original model output, actual tool calls, and local pending proposals.
- `agent-live.png`: screenshot of the run viewer generated from that record.
- `fixture-result.json`: explicitly scripted offline fixture, separate from live evidence.

No customer records, production integrations, or measured customer ROI are claimed. Approval records a local decision; external execution is not implemented.
