# Emirald

A bot that wakes up every minute, asks the Emirald LLM (via Nous Portal) what to
do on Blofin USDT perpetual futures, then acts on the highest-confidence setups.

## Quick start

```powershell
cd C:\Users\mknig\hermes-trader\Emirald
python -m emirald.scripts.first_run_check
python -m emirald
```

On Windows, you can also use:

```powershell
C:\Users\mknig\hermes-trader\Emirald\.venv\Scripts\pythonw.exe -m emirald
```

working directory `C:\Users\mknig\hermes-trader\Emirald`. Triggers = "At system startup".

## Dashboard

```powershell
python -m emirald.scripts.dump_journal
```

## Risk

This runs live by default. To add guardrails: implement `emirald/src/emirald/risk.py` with a real
risk gate, then in `emirald/src/emirald/loop.py` change the import from `risk_none` to `risk`.
