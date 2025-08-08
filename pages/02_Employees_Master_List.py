import streamlit as st

st.set_page_config(page_title="Employees (Master List)", page_icon="👥", layout="wide")
st.title("👥 Employees (Master List)")

st.info(
    "Future: show employees from DynamoDB and/or Rekognition collection, "
    "allow enroll/remove, and view metadata."
)

# Example table placeholder
st.subheader("Sample (static) table")
st.table(
    {
        "EmployeeID": ["employee001", "employee002"],
        "Name": ["Jane Doe", "John Smith"],
        "Registered": ["Yes", "Yes"],
        "Violations": [1, 0],
    }
)