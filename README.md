# SAP Fiori-Style Expandable Table with Inline Editing

This project implements the final requested architecture:
- SAP Fiori–style expandable table
- Inline spreadsheet-like editing
- Manual Save (batch update)
- Flask + SQLAlchemy backend

## Key Features
- Expandable master/detail rows
- Click-to-edit cells
- Pending changes tracking
- Batch save via API

## Setup
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```
