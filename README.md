# chaos

P2P mesh messenger with glass terminal UI

## Structure

- `app/` — Python backend (models, repositories)
- `css/` — styles
- `js/` — frontend logic
- `db/` — SQL schemas
- `tests/` — pytest suite
- `index.html` — main UI

## Quick start

```bash
# Python environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Database setup (PostgreSQL)
psql -U postgres -f db/genesis.sql

# Run
./run.sh
