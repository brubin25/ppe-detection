import streamlit as st

st.set_page_config(page_title="Violations", page_icon="⚠️", layout="wide")
st.title("⚠️ Violations")

st.info(
    "Future: pull from DynamoDB (e.g., PPEViolationTracker) and show filters, counts, "
    "and critical alerts for >= 3 violations."
)

# Example placeholder data
st.subheader("Recent Violations (sample)")
st.dataframe(
    {
        "Timestamp": ["2025-07-14 10:10", "2025-07-14 09:55"],
        "EmployeeID": ["employee001", "Unknown"],
        "Missing": ["HEAD_COVER", "FACE_COVER"],
        "S3 Object": ["uploads/img_123.png", "uploads/img_456.png"],
    }
)