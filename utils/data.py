# utils/data.py
import os
from decimal import Decimal
from typing import Dict, Any, List

import boto3
import pandas as pd
import streamlit as st

# -----------------------------
# Config (matches the rest of app)
# -----------------------------
AWS_ACCESS_KEY = st.secrets.get("AWS_ACCESS_KEY_ID", os.getenv("AWS_ACCESS_KEY_ID", ""))
AWS_SECRET_KEY = st.secrets.get("AWS_SECRET_ACCESS_KEY", os.getenv("AWS_SECRET_ACCESS_KEY", ""))
REGION         = st.secrets.get("REGION", os.getenv("AWS_REGION", "us-east-2"))

# ✅ Use the employee profile table (not PPEViolationTracker)
EMPLOYEE_TABLE = "employee_master"

# -----------------------------
# Dynamo helpers
# -----------------------------
def _ddb_resource():
    return boto3.resource(
        "dynamodb",
        region_name=REGION,
        aws_access_key_id=AWS_ACCESS_KEY or None,
        aws_secret_access_key=AWS_SECRET_KEY or None,
    )

def _table():
    return _ddb_resource().Table(EMPLOYEE_TABLE)

def _as_int(v) -> int:
    if isinstance(v, Decimal):
        return int(v)
    try:
        return int(v)
    except Exception:
        return 0

# -----------------------------
# Public API (used by pages)
# -----------------------------
def load_employees_from_dynamodb() -> pd.DataFrame:
    """
    Scan employee_master and return a DataFrame with:
      - EmployeeID (PK)
      - violations (default 0 if missing)
    Other profile fields are ignored here (the master list page only needs these).
    """
    tbl = _table()

    items: List[Dict[str, Any]] = []
    scan_kwargs: Dict[str, Any] = {}
    while True:
        resp = tbl.scan(**scan_kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" in resp:
            scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        else:
            break

    rows = []
    for it in items:
        emp_id = it.get("EmployeeID") or it.get("employee_id")
        if not emp_id:
            continue
        vio = _as_int(it.get("violations", 0))
        rows.append({"EmployeeID": str(emp_id), "violations": vio})

    if not rows:
        return pd.DataFrame(columns=["EmployeeID", "violations"])

    return (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["EmployeeID"], keep="last")
        .reset_index(drop=True)
    )


def update_employee_violations(employee_id: str, violations: int) -> None:
    """
    Update only the 'violations' attribute for the given EmployeeID in employee_master.
    (Keeps all other profile fields intact.)
    """
    tbl = _table()
    tbl.update_item(
        Key={"EmployeeID": employee_id},
        UpdateExpression="SET #v = :v",
        ExpressionAttributeNames={"#v": "violations"},
        ExpressionAttributeValues={":v": int(violations)},
    )


def upsert_employee(employee_id: str, violations: int = 0) -> None:
    """
    Create if missing, or update if exists, the 'violations' field for EmployeeID
    in employee_master. This does NOT overwrite other fields (name, department, etc.).
    """
    tbl = _table()
    # Using UpdateItem acts as an upsert without clobbering other attributes.
    tbl.update_item(
        Key={"EmployeeID": str(employee_id)},
        UpdateExpression="SET #v = :v",
        ExpressionAttributeNames={"#v": "violations"},
        ExpressionAttributeValues={":v": int(violations)},
    )
