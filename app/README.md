# Data Migration PoC

REST API + ETL pipeline to migrate CSV data from Azure Blob Storage to Snowflake.

## Stack
- **API**: FastAPI + Python
- **Database**: Snowflake
- **Storage**: Azure Blob Storage
- **Format**: AVRO for backups
- **Container**: Docker

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/load-historic | Load CSV files from Azure Blob |
| POST | /api/v1/insert | Batch insert (1-1000 rows) |
| POST | /api/v1/backup/{table} | Backup table to AVRO |
| POST | /api/v1/restore/{table}/{file} | Restore table from AVRO |

## Auth
All endpoints require header: `x-api-key: your_key`

## Run locally
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

## Run with Docker
```bash
docker build -t migration-poc .
docker run -p 8000:8000 --env-file .env migration-poc
```