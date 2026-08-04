import io
import re
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Deliveroo & Uber Eats Order Number Checks", layout="wide")
st.title("Deliveroo & Uber Eats Order Number Checks")

st.write("""
Upload a Deliveroo export and an Uber Eats export.

The tool will:
- Filter irrelevant audits
- Validate order numbers
- Combine the results
- Generate Order Number Checks.csv
- Generate copyable email text
""")

d_file = st.file_uploader("Upload Deliveroo.csv", type=["csv"])
u_file = st.file_uploader("Upload Uber Eats.csv", type=["csv"])

KEEP = [
    "order_internal_id","internal_id","site_internal_id","site_name",
    "site_address_1","site_address_2","site_address_3","site_post_code",
    "submitted_date","approval_date","item_to_order",
    "date_of_visit","time_of_visit","tokens","auditor_name",
    "auditor_internal_id","auditor_gender","auditor_date_of_birth",
    "visit_info","Order Number"
]

def deliveroo_validate(v):
    x = "" if pd.isna(v) else str(v).strip()
    y = x[1:] if x.startswith("#") else x
    errs=[]
    if x=="": errs.append("Blank")
    if x.startswith("#"): errs.append("Must not start with #")
    if x!="" and len(y)!=11: errs.append("Must be exactly 11 digits")
    if x!="" and (not y.isdigit()): errs.append("Must contain digits only")
    return "Valid" if not errs else ", ".join(errs)

def uber_validate(v):
    x = "" if pd.isna(v) else str(v).strip()
    y = x[1:] if x.startswith("#") else x
    errs=[]
    if x=="": errs.append("Blank")
    if not x.startswith("#"): errs.append("Must start with #")
    if x!="" and len(y)!=5: errs.append("Must be exactly 5 characters long")
    if x!="" and re.search(r"[^0-9A-F]", y): errs.append("Must only contain the numbers 0-9 and capital letters A-F")
    return "Valid" if not errs else ", ".join(errs)

if d_file and u_file:
    d = pd.read_csv(d_file, dtype=str).fillna("")
    u = pd.read_csv(u_file, dtype=str).fillna("")

    d = d[d["primary_result"].str.lower()!="abort"]
    d = d[~d["item_to_order"].isin(["Alcohol","Click & Collect"])]

    u = u[u["primary_result"].str.lower()!="abort"]
    u = u[~u["tokens"].str.contains("Tesco Whoosh", case=False, na=False)]

    d = d.rename(columns={
        "date_of_visit_local":"date_of_visit",
        "time_of_visit_local":"time_of_visit",
        "Please enter the  11-digit order number:":"Order Number"
    })
    u = u.rename(columns={
        "date_of_visit_local":"date_of_visit",
        "time_of_visit_local":"time_of_visit",
        "Please enter your order number:":"Order Number"
    })

    d = d[KEEP].copy()
    u = u[KEEP].copy()

    d["Fail Criteria"] = d["Order Number"].apply(deliveroo_validate)
    u["Fail Criteria"] = u["Order Number"].apply(uber_validate)

    d = d[d["Fail Criteria"]!="Valid"]
    u = u[u["Fail Criteria"]!="Valid"]

    final = pd.concat([d,u], ignore_index=True)

    buf = io.StringIO()
    final.to_csv(buf,index=False)

    d_contact = d[d["Fail Criteria"].str.contains("Must be exactly 11 digits", na=False)]["internal_id"].tolist()
    u_contact = u[u["Fail Criteria"].str.contains("Must be exactly 5 characters long", na=False)]["internal_id"].tolist()

    email = f"""Hi all,

Please see attached for a list of Deliveroo and Uber Eats audits which failed my order number validations, along with the reasons in column U. To me it looks like there's {len(d_contact)} Deliveroo ({", ".join(d_contact)}) and {len(u_contact)} Uber Eats ({", ".join(u_contact)}) which would require contacting the auditor to get the correct order number, while the rest should be able to be updated in place on the audit. I've moved these audits to approving query and removed the emails so that they can be edited and re-approved as and when they're ready. Please let me know if there's anything else you need.
"""

    st.success(f"{len(final)} invalid audits found.")
    st.download_button("Download Order Number Checks.csv", buf.getvalue(), file_name="Order Number Checks.csv", mime="text/csv")
    st.markdown("#### Email Text")
    st.code(email, language="text")
