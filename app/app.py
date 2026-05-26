import os, json, re, logging, math
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from db import get_conn

load_dotenv()
os.makedirs("logs", exist_ok=True)
os.makedirs("backups", exist_ok=True)

app = Flask(__name__)
API_KEY = os.getenv("API_KEY")

logging.basicConfig(
    filename="logs/rejected.log",
    level=logging.WARNING,
    format="%(asctime)s | %(message)s"
)

# ---------- API KEY authorization ----------
def check_key():
    if request.headers.get("x-api-key") != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

# ---------- validation ----------
def validate_row(table, row):
    errors = []
    if table == "departments":
        if not isinstance(int(row.get("id")) if row.get("id") is not None and not math.isnan(row.get("id")) else None, int) or row["id"] <= 0:
            errors.append("id must be a positive integer")
        if row.get("department", "") is None or row.get("department", "") is None or not row.get("department", "").strip():
            errors.append("department cannot be empty")

    elif table == "jobs":
        if not isinstance(int(row.get("id")) if row.get("id") is not None and not math.isnan(row.get("id")) else None, int) or row["id"] <= 0:
            errors.append("id must be a positive integer")
        if row.get("job", "") is None or not row.get("job", "").strip():
            errors.append("job cannot be empty")

    elif table == "hired_employees":
        for field in ("id", "department_id", "job_id"):
            if not isinstance(int(row.get(field)) if row.get(field) is not None and not math.isnan(row.get(field)) else None, int) or row[field] <= 0:
                errors.append(f"{field} cannot be empty and must be a positive integer")
        if row.get("name", "") is None or not row.get("name", "").strip():
            errors.append("name cannot be empty")
        if row.get("datetime", "") is None or not re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$', str(row.get("datetime", ""))):
            errors.append("datetime must be ISO format YYYY-MM-DDTHH:MM:SSZ")

    return errors

# ---------- insert statement ----------
INSERT_SQL = {
    "departments":     "INSERT INTO departments (id, department) VALUES (%s, %s)",
    "jobs":            "INSERT INTO jobs (id, job) VALUES (%s, %s)",
    "hired_employees": "INSERT INTO hired_employees (id, name, datetime, department_id, job_id) VALUES (%s, %s, %s, %s, %s)"
}

def to_tuple(table, row):
    if table == "departments":
        return (row["id"], row["department"])
    elif table == "jobs":
        return (row["id"], row["job"])
    elif table == "hired_employees":
        return (row["id"], row["name"], row["datetime"], int(row["department_id"]), int(row["job_id"]))

def process_batch(table, rows):
    valid, rejected = [], []
    for row in rows:
        errors = validate_row(table, row)
        if errors:
            reason = "; ".join(errors)
            logging.warning(f"REJECTED | table={table} | row={row} | reason={reason}")
            rejected.append({"row": row, "reason": reason})
            # log to snowflake
            try:
                conn = get_conn()
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO rejected_transactions (table_name, raw_data, reason) SELECT %s, PARSE_JSON(%s), %s",
                    (table, json.dumps(row), reason)
                )
                conn.commit()
                cur.close(); conn.close()
            except Exception:
                pass
        else:
            valid.append(to_tuple(table, row))

    inserted = 0
    if valid:
        conn = get_conn()
        cur = conn.cursor()
        cur.executemany(INSERT_SQL[table], valid)
        conn.commit()
        inserted = len(valid)
        cur.close(); conn.close()

    return {"inserted": inserted, "rejected": len(rejected), "details": rejected}

# ---------- endpoints ----------
@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/api/v1/insert", methods=["POST"])
def insert():
    err = check_key()
    if err: return err

    body = request.get_json()
    table = body.get("table", "")
    rows  = body.get("rows", [])

    if table not in ("departments", "jobs", "hired_employees"):
        return jsonify({"error": "Invalid table"}), 400
    if not (1 <= len(rows) <= 1000):
        return jsonify({"error": "rows must be between 1 and 1000"}), 400

    return jsonify(process_batch(table, rows))

@app.route("/api/v1/load-historic", methods=["POST"])
def load_historic():
    err = check_key()
    if err: return err

    from load_historic import run
    return jsonify(run())

@app.route("/api/v1/backup/<table>", methods=["POST"])
def backup(table):
    err = check_key()
    if err: return err

    if table not in ("departments", "jobs", "hired_employees"):
        return jsonify({"error": "Invalid table"}), 400

    from backup_restore import backup_table
    return jsonify(backup_table(table))

@app.route("/api/v1/restore/<table>/<backup_file>", methods=["POST"])
def restore(table, backup_file):
    err = check_key()
    if err: return err

    from backup_restore import restore_table
    try:
        return jsonify(restore_table(table, backup_file))
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404

if __name__ == "__main__":
    app.run(debug=True, port=8000)