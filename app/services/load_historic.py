import os, io, pandas as pd
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()

FILES   = {"departments": "departments.csv", "jobs": "jobs.csv", "hired_employees": "hired_employees.csv"}
COLUMNS = {
    "departments":     ["id", "department"],
    "jobs":            ["id", "job"],
    "hired_employees": ["id", "name", "datetime", "department_id", "job_id"]
}

def run():
    from app import process_batch
    client    = BlobServiceClient.from_connection_string(os.getenv("AZURE_STORAGE_CONNECTION_STRING"))
    container = client.get_container_client(os.getenv("AZURE_CONTAINER_NAME"))
    results   = {}

    for table, filename in FILES.items():
        data = container.get_blob_client(filename).download_blob().readall()
        df   = pd.read_csv(io.BytesIO(data), header=None, names=COLUMNS[table])
        rows = df.where(pd.notnull(df), None).to_dict(orient="records")

        total_inserted = total_rejected = 0
        for i in range(0, len(rows), 1000):
            r = process_batch(table, rows[i:i+1000])
            total_inserted += r["inserted"]
            total_rejected += r["rejected"]

        results[table] = {"inserted": total_inserted, "rejected": total_rejected}

    return results