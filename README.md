# chaos

P2P mesh messenger with glass terminal UI
<img width="1188" height="936" alt="image" src="https://github.com/user-attachments/assets/468e7f5c-11a4-4a56-9d8f-b3d1c09ee31d" />

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

## API Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/users/` | Create user |
| GET | `/users/me` | Get current user |
| PATCH | `/users/me` | Update user |
| GET | `/users/search` | Search users |
| GET | `/users/{id}` | Get user by ID |
| GET | `/users/me/contacts` | List contacts |
| POST | `/users/me/contacts` | Add contact |
| DELETE | `/users/me/contacts/{id}` | Remove contact |
| POST | `/chains/` | Create chain |
| GET | `/chains/` | List chains |
| GET | `/chains/{id}` | Get chain |
| GET | `/messages/chains/{id}` | Get chain messages |
| POST | `/messages/chains/{id}` | Create message |
| POST | `/messages/chains/{id}/with-attachments` | Create message with files |
| GET | `/messages/chains/{id}/messages/{mid}` | Get message |
| DELETE | `/messages/{id}` | Delete message |
| GET | `/validation/chains/{id}` | Validate chain |
| GET | `/validation/chains/{id}/invalid` | Get invalid messages |
| GET | `/validation/chains/{id}/valid` | Quick validity check |
| GET | `/attachments/{id}` | Download attachment |

> hopefully I will do it. or die young and beautiful
