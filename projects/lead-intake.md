# Lead Intake Pipeline

**Use case:** consolidate CSV contacts without creating repeated records.

```sh
python3 projects/automation.py leads examples/leads.csv --database /tmp/portfolio-leads.db
```

On a new database: 2 accepted, 1 rejected, 1 duplicate. Repeating the import accepts zero new contacts. SQLite enforces unique normalized emails across runs. Invalid rows are counted, not silently inserted. No CRM or messaging service is contacted.

Next steps: per-row rejection reports, stricter validation, authenticated CRM adapter, consent tracking, and integration retry policy. SQLite is intended for this local demo, not a high-volume concurrent service.
