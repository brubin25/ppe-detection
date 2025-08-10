# --- Compatibility shims so pages can import the expected names ---
# These wrappers call your existing functions if they exist; otherwise
# they use a safe DynamoDB fallback that expects a PPEViolationTracker table.

from typing import Any, Dict, List
import os
import boto3
import pandas as pd

try:
    import streamlit as st
    _SECRETS = getattr(st, "secrets", {})
except Exception:
    _SECRETS = {}

_AWS_REGION  = os.getenv("AWS_REGION", _SECRETS.get("REGION", "us-east-2"))
_AWS_KEY     = os.getenv("AWS_ACCESS_KEY_ID", _SECRETS.get("AWS_ACCESS_KEY_ID", ""))
_AWS_SECRET  = os.getenv("AWS_SECRET_ACCESS_KEY", _SECRETS.get("AWS_SECRET_ACCESS_KEY", ""))
_VIOL_TBL    = os.getenv("EMPLOYEE_TABLE_VIOLATIONS", "PPEViolationTracker")

def _ddb():
    return boto3.resource(
        "dynamodb",
        region_name=_AWS_REGION,
        aws_access_key_id=_AWS_KEY or None,
        aws_secret_access_key=_AWS_SECRET or None,
    )

def _scan_violations_table() -> pd.DataFrame:
    tbl = _ddb().Table(_VIOL_TBL)
    items: List[Dict[str, Any]] = []
    last = None
    while True:
        resp = tbl.scan(**({"ExclusiveStartKey": last} if last else {}))
        items += resp.get("Items", [])
        last = resp.get("LastEvaluatedKey")
        if not last:
            break
    if not items:
        return pd.DataFrame(columns=["EmployeeID", "violations"])
    rows = []
    for it in items:
        emp = str(it.get("EmployeeID", "")).strip()
        vio = it.get("violations", 0)
        try:
            vio = int(vio)
        except Exception:
            vio = 0
        if emp:
            rows.append({"EmployeeID": emp, "violations": vio})
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.groupby("EmployeeID", as_index=False)["violations"].sum()
    return df

def _update_violations_in_ddb(emp_id: str, value: int) -> None:
    tbl = _ddb().Table(_VIOL_TBL)
    tbl.update_item(
        Key={"EmployeeID": emp_id},
        UpdateExpression="SET #v = :v",
        ExpressionAttributeNames={"#v": "violations"},
        ExpressionAttributeValues={":v": int(value)},
    )

def _put_violations_in_ddb(emp_id: str, value: int) -> None:
    tbl = _ddb().Table(_VIOL_TBL)
    tbl.put_item(Item={"EmployeeID": emp_id, "violations": int(value)})

# ---- Wrappers expected by pages ----

def load_employees_from_dynamodb() -> pd.DataFrame:
    # Try your function names first:
    for name in ("load_employees", "get_employees"):
        fn = globals().get(name)
        if callable(fn):
            return fn()
    # Fallback
    return _scan_violations_table()

def update_employee_violations(employee_id: str, new_value: int) -> None:
    for name in ("update_employee", "set_employee_violations"):
        fn = globals().get(name)
        if callable(fn):
            return fn(employee_id, new_value)
    # Fallback
    return _update_violations_in_ddb(employee_id, new_value)

def upsert_employee(employee_id: str, violations: int = 0) -> None:
    for name in ("put_employee", "create_or_update_employee"):
        fn = globals().get(name)
        if callable(fn):
            return fn(employee_id, violations)
    # Fallback
    return _put_violations_in_ddb(employee_id, violations)
