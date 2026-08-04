import io
import re
import streamlit as st
import pandas as pd

abort_email = st.secrets["abort_email"]

st.title("Deliveroo & Uber Eats Order Number Checks")

st.write("Upload a Deliveroo export and an Uber Eats export.")

st.markdown("""
The tool will:

- Filter irrelevant audits
- Validate order numbers
- Combine the results
- Generate **Order Number Checks.csv**
- Generate copyable email text
""")

d_file = st.file_uploader("Upload Deliveroo export", type="csv")
u_file = st.file_uploader("Upload Uber Eats export", type="csv")

KEEP = [
    "order_internal_id","internal_id","site_internal_id","site_name",
    "site_address_1","site_address_2","site_address_3","site_post_code",
    "submitted_date","approval_date","item_to_order","date_of_visit",
    "time_of_visit","tokens","auditor_name","auditor_internal_id",
    "auditor_gender","auditor_date_of_birth","visit_info","Order Number"
]

def prepare(df, order_col):
    # Remove existing columns before renaming to avoid duplicate .1 columns
    for c in ("date_of_visit","time_of_visit","Order Number"):
        if c in df.columns:
            df = df.drop(columns=c)
    rename = {
        "date_of_visit_local":"date_of_visit",
        "time_of_visit_local":"time_of_visit",
        order_col:"Order Number"
    }
    df = df.rename(columns=rename)

    # Preserve everything as text
    for c in ["Order Number","date_of_visit","time_of_visit"]:
        if c in df.columns:
            df[c] = df[c].fillna("").astype(str).str.strip()

    missing=[c for c in KEEP if c not in df.columns]
    if missing:
        raise ValueError("Missing columns: " + ", ".join(missing))

    return df.loc[:, KEEP].copy()

def deliveroo_validate(v):
    x=str(v).strip()
    y=x[1:] if x.startswith("#") else x
    errs=[]
    if x=="": errs.append("Blank")
    if x.startswith("#"): errs.append("Must not start with #")
    if x and len(y)!=11: errs.append("Must be exactly 11 digits")
    if x and not y.isdigit(): errs.append("Must contain digits only")
    return "Valid" if not errs else ", ".join(errs)

def uber_validate(v):
    x=str(v).strip()
    y=x[1:] if x.startswith("#") else x
    errs=[]
    if x=="": errs.append("Blank")
    if not x.startswith("#"): errs.append("Must start with #")
    if x and len(y)!=5: errs.append("Must be exactly 5 characters long")
    if x and re.search(r"[^0-9A-F]", y):
        errs.append("Must only contain the numbers 0-9 and capital letters A-F")
    return "Valid" if not errs else ", ".join(errs)

if d_file and u_file:
    d=pd.read_csv(d_file,dtype=str,keep_default_na=False)
    u=pd.read_csv(u_file,dtype=str,keep_default_na=False)

    d=d[d["primary_result"].str.lower()!="abort"]
    d=d[~d["item_to_order"].isin(["Alcohol","Click & Collect"])]

    u=u[u["primary_result"].str.lower()!="abort"]
    u=u[~u["tokens"].str.contains("Tesco Whoosh",case=False,na=False)]

    d=prepare(d,"Please enter the  11-digit order number:")
    u=prepare(u,"Please enter your order number:")

    d["Platform"]="Deliveroo"
    u["Platform"]="Uber Eats"

    d["Fail Criteria"]=d["Order Number"].map(deliveroo_validate)
    u["Fail Criteria"]=u["Order Number"].map(uber_validate)

    d=d[d["Fail Criteria"]!="Valid"]
    u=u[u["Fail Criteria"]!="Valid"]

    final=pd.concat([d,u],ignore_index=True)
    final=final.drop(columns=["Platform"])

    upload_df = (
        pd.DataFrame({
            "internal_id": final["internal_id"],
            "status": "approving_query",
            "report_ABORT_mini": abort_email
        })
        .drop_duplicates(subset=["internal_id"])
    )

	# Preserve leading zeros when opening the CSV in Excel
    final["Order Number"] = final["Order Number"].apply(
        lambda x: f'="{x}"'
        if isinstance(x, str) and x.startswith("0")
        else x
    )

    csv=io.StringIO()
    final.to_csv(csv,index=False,encoding='utf-8-sig')

    upload_csv=io.StringIO()
    upload_df.to_csv(upload_csv,index=False)

    d_contact=d.loc[d["Fail Criteria"].str.contains("Must be exactly 11 digits",na=False),"internal_id"].tolist()
    u_contact=u.loc[u["Fail Criteria"].str.contains("Must be exactly 5 characters long",na=False),"internal_id"].tolist()

    email=f"""Hi all,

Please see attached for a list of Deliveroo and Uber Eats audits which failed order number validations, along with the reasons in column U. To me it looks like there's {len(d_contact)} Deliveroo ({", ".join(d_contact)}) and {len(u_contact)} Uber Eats ({", ".join(u_contact)}) which would require contacting the auditor to get the correct order number, while the rest should be able to be updated in place on the audit. I've moved these audits to approving query and removed the emails so that they can be edited and re-approved as and when they're ready. Please let me know if there's anything else you need."""

    st.success(f"{len(final)} invalid audits found.")
    st.download_button("Download Order Number Checks.csv",csv.getvalue(),"Order Number Checks.csv","text/csv")
    st.download_button("Download audits_upload_template.csv",upload_csv.getvalue(),"audits_upload_template.csv","text/csv")
    st.markdown("#### Email Text")
    st.code(email,language="text")
