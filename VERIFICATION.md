# Local verification

Fictional sample data; commands executed successfully. Temporary database paths shown below are ephemeral.

```text
python3 pipeline.py --db /var/folders/zg/sd0lgkgn0q71mm5sgl66mkkc0000gn/T/tmpy88ixv7h/leads.db import examples/leads.csv
[
  {
    "row": 2,
    "status": "accepted",
    "lead_id": 1
  },
  {
    "row": 3,
    "status": "duplicate",
    "lead_id": 1
  },
  {
    "row": 4,
    "status": "rejected",
    "reason": "invalid email format"
  },
  {
    "row": 5,
    "status": "accepted",
    "lead_id": 2
  }
]
```

```text
python3 pipeline.py --db /var/folders/zg/sd0lgkgn0q71mm5sgl66mkkc0000gn/T/tmpy88ixv7h/leads.db drain --crm /var/folders/zg/sd0lgkgn0q71mm5sgl66mkkc0000gn/T/tmpy88ixv7h/crm.db
[
  {
    "id": 1,
    "status": "delivered"
  },
  {
    "id": 2,
    "status": "delivered"
  }
]
```

```text
python3 pipeline.py --db /var/folders/zg/sd0lgkgn0q71mm5sgl66mkkc0000gn/T/tmpy88ixv7h/leads.db status
{
  "leads": 2,
  "events": 4,
  "rejections": 1,
  "outbox": [
    {
      "state": "delivered",
      "count": 2
    }
  ]
}
```
