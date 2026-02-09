# NSE OI-Volume App

FastAPI app that fetches NSE option chain data and renders a simple frontend dashboard.

## Run

```powershell
python -m venv venv
venv\Scripts\Activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/` in your browser.

## API Endpoints

- `GET /api/option-chain/expiries?symbol=NIFTY&instrument_type=Indices`
- `GET /api/option-chain/summary?symbol=NIFTY&expiry=10-Feb-2026&instrument_type=Indices`
