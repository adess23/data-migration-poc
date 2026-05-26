import os, fastavro
from datetime import datetime
from db import get_conn
from app import process_batch

BACKUP_DIR = "backups"

AVRO_SCHEMAS = {
    "departments": {
        "type": "record", "name": "Department",
        "fields": [{"name": "id", "type": "int"}, {"name": "department", "type": "string"}]
    },
    "jobs": {
        "type": "record", "name": "Job",
        "fields": [{"name": "id", "type": "int"}, {"name": "job", "type": "string"}]
    },
    "hired_employees": {
        "type": "record", "name": "HiredEmployee",
        "fields": [
            {"name": "id", "type": "int"}, {"name": "name", "type": "string"},
            {"name": "datetime", "type": "string"},
            {"name": "department_id", "type": "int"}, {"name": "job_id", "type": "int"}
        ]
    }
}

def backup_table(table):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(f"SELECT * FROM {table}")
    rows = [dict(zip([d[0].lower() for d in cur.description], row)) for row in cur.fetchall()]
    cur.close(); conn.close()

    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"{BACKUP_DIR}/{table}_{ts}.avro"
    schema = fastavro.parse_schema(AVRO_SCHEMAS[table])

    with open(path, "wb") as f:
        fastavro.writer(f, schema, rows)

    return {"table": table, "file": path, "rows": len(rows)}

def restore_table(table, backup_file):
    path = f"{BACKUP_DIR}/{backup_file}"
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    with open(path, "rb") as f:
        records = list(fastavro.reader(f))

    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(f"TRUNCATE TABLE {table}")
    conn.commit(); cur.close(); conn.close()

    result = process_batch(table, records)
    return {"table": table, "restored": result["inserted"], "rejected": result["rejected"]}