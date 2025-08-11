import os
import datetime as dt
import streamlit as st
from collections import Counter

from utils.data import (
    list_employees,
    query_violation_events,
    update_violation_event,
    presigned_url_for_s3,    # already provided in utils/data.py

)

st.set_page_config(page_title="Violations", page_icon="⚠️", layout="wide")
st.title("⚠️ Violations (Live from DynamoDB)")

# ---- filters ----
today = dt.date.today()
default_range = (today - dt.timedelta(days=7), today)

c1, c2, c3, c4 = st.columns([1.6, 1.3, 1, 1])
with c1:
    date_range = st.date_input("Date range", value=default_range, format="YYYY/MM/DD")
with c2:
    employees = ["(All)"] + list_employees()
    emp_pick = st.selectbox("Employee", employees, index=0)
with c3:
    only_unresolved = st.toggle("Only unresolved", value=False)
with c4:
    prefer_annot = st.toggle("Prefer annotated image", value=True)
st.button("🔄 Refresh")

# normalize date_range tuple
start_d, end_d = None, None
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_d, end_d = date_range

# ---- query ----
events = query_violation_events(
    start=start_d,
    end=end_d,
    employee_id=None if emp_pick == "(All)" else emp_pick,
    unresolved_only=only_unresolved
)

# ---- KPI ----
k1, k2, k3, k4 = st.columns(4)
total_events = len(events)
unknown = sum(1 for e in events if (e.get("EmployeeID") or "") == "Unknown")
unique_people = len({e.get("EmployeeID") for e in events if (e.get("EmployeeID") or "") != "Unknown"})

with k1: st.metric("Total events", total_events)
with k2: st.metric("Unknown", unknown)
with k3: st.metric("Unique employees", unique_people)

# top missing 全量显示（不再被 metric 截断）
flat = []
for e in events:
    for m in (e.get("Missing") or []):
        flat.append(m)
top3 = Counter(flat).most_common(3)
top_text = ", ".join(f"{k}({v})" for k, v in top3) if top3 else "-"
with k4: st.caption(f"Top missing: {top_text}")

st.write("---")

# ---- styles ----
st.markdown("""
<style>
.card{border:1px solid #e6e6e6;border-radius:12px;padding:12px;margin-bottom:18px}
.card img{max-height:520px;object-fit:contain}
.badge{display:inline-block;padding:2px 8px;margin-right:6px;background:#eef2ff;border-radius:6px;font-size:12px;color:#334155}
.caption{color:#64748b}
</style>
""", unsafe_allow_html=True)

def pick_img_url(item: dict, prefer_annotated: bool) -> str:
    def _safe_presign(val):
        return presigned_url_for_s3(val) if isinstance(val, str) and val else ""

    if prefer_annotated:
        for k in ("S3_Object_Annotated", "DerivedImage"):
            url = _safe_presign(item.get(k))
            if url:
                return url
    return _safe_presign(item.get("S3_Object"))


# ---- render ----
st.subheader("Events")
cols = st.columns(3)

for i, ev in enumerate(events):
    with cols[i % 3]:
        st.markdown('<div class="card">', unsafe_allow_html=True)

        ts = ev.get("Timestamp", "")
        emp = ev.get("EmployeeID", "")
        tags = " ".join([f'<span class="badge">{m}</span>' for m in (ev.get("Missing") or [])])
        st.markdown(f"{ts} — **{emp}** &nbsp; {tags}", unsafe_allow_html=True)

        url = pick_img_url(ev, prefer_annot)
        st.image(url, use_container_width=True, caption=url or "No image")

        c1, c2, c3 = st.columns([0.55, 1.25, 0.7])
        with c1:
            resolved = st.checkbox("Resolved", value=bool(ev.get("Resolved")), key=f"res_{ev['EventID']}")
        with c2:
            opts = ["(no change)"] + employees[1:]  # reuse list_employees()
            new_owner = st.selectbox("Assign", opts, index=0, key=f"asg_{ev['EventID']}")
        with c3:
            if st.button("Save", key=f"save_{ev['EventID']}"):
                payload = {"Resolved": resolved}
                if new_owner != "(no change)":
                    payload["EmployeeID"] = new_owner   # 直接重指派 owner
                update_violation_event(ev["EventID"], payload)
                st.toast("Saved", icon="✅")
                st.experimental_rerun()

        st.caption(f"EventID: {ev['EventID']}")
        st.markdown("</div>", unsafe_allow_html=True)
