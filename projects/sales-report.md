# Sales Report Automation

**Use case:** generate a repeatable daily summary from a single-currency transaction export.

```sh
python3 projects/automation.py sales examples/sales.csv --output /tmp/portfolio-sales.md
```

Expected output: 4 transactions, net sales **480.00**, October 1 total **200.00**, October 2 total **280.00**. Negative amounts represent refunds. Decimal arithmetic avoids binary floating-point rounding. Invalid dates and non-finite amounts fail the run before an output report is written.

Next steps: currency column validation, timezone policy, scheduled execution, charts, and delivery to an authorized destination. This demo does not provide accounting or tax calculations.
