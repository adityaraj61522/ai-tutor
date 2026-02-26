# Flask server for b-ai-tutor

This folder contains a minimal Flask server that listens on port 7700 by default.

Quick start:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Or to run on a different port:

```bash
PORT=7700 python app.py
```

Endpoints:
- `GET /` — returns JSON {"status":"ok","port":<port>}
- `POST /echo` — echoes received JSON body
