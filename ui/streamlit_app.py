"""
Streamlit Human Review UI
─────────────────────────
- Shows invoices pending review (paused by LangGraph interrupt)
- Passes thread_id back to approve endpoint so graph resumes via HITL
- Tab 2: All invoices table + CSV export
"""
import streamlit as st
import requests
from datetime import datetime

API = "http://localhost:8000"

st.set_page_config(page_title="Invoice Review", layout="wide")
st.title("📄 Invoice Automation — Review Queue")

tab1, tab2 = st.tabs(["⏳ Pending Review", "📋 All Invoices"])

# ── Tab 1: Pending ──────────────────────────────────────────────────────────
with tab1:
    try:
        invoices = requests.get(f"{API}/invoices/pending", timeout=5).json()
    except Exception as e:
        st.error(f"Cannot connect to API: {e}")
        invoices = []

    count = len(invoices)
    st.metric("Pending Review", count)

    if not invoices:
        st.success("✅ All caught up — no invoices pending review.")
    else:
        for inv in invoices:
            label = (
                f"🧾 {inv.get('invoice_number') or 'No Invoice#'} | "
                f"Vendor: {inv.get('vendor_name') or 'Unknown'} | "
                f"Confidence: {(inv.get('confidence') or 0):.0%} | "
                f"Method: {inv.get('extraction_method', 'direct')}"
            )
            with st.expander(label, expanded=False):
                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("Extracted Fields")
                    account_number = st.text_input(
                        "Account Number (BAN)",
                        inv.get("account_number") or "",
                        key=f"acc_{inv['id']}"
                    )
                    invoice_number = st.text_input(
                        "Invoice Number",
                        inv.get("invoice_number") or "",
                        key=f"inv_{inv['id']}"
                    )
                    bill_date = st.text_input(
                        "Bill Date (YYYY-MM-DD)",
                        inv.get("bill_date") or "",
                        key=f"bdate_{inv['id']}"
                    )
                    due_date = st.text_input(
                        "Due Date (YYYY-MM-DD)",
                        inv.get("due_date") or "",
                        key=f"ddate_{inv['id']}"
                    )
                    total_due = st.number_input(
                        "Total Due ($)",
                        value=float(inv.get("total_due") or 0.0),
                        key=f"due_{inv['id']}"
                    )

                with col2:
                    st.subheader("Addresses")
                    bill_to = st.text_area(
                        "Bill To Address",
                        inv.get("bill_to_address") or "",
                        key=f"bto_{inv['id']}"
                    )
                    bill_from = st.text_area(
                        "Bill From Address",
                        inv.get("bill_from_address") or "",
                        key=f"bfrom_{inv['id']}"
                    )
                    remittance = st.text_area(
                        "Remittance Address",
                        inv.get("remittance_address") or "",
                        key=f"rem_{inv['id']}"
                    )

                st.caption(
                    f"PDF: `{inv['pdf_filename']}` | "
                    f"Thread: `{inv.get('thread_id', 'N/A')}` | "
                    f"Created: {inv.get('created_at', '')}"
                )

                col_a, col_b, _ = st.columns([1, 1, 4])

                with col_a:
                    if st.button("✅ Approve", key=f"approve_{inv['id']}"):
                        payload = {
                            "account_number": account_number or None,
                            "invoice_number": invoice_number or None,
                            "bill_date": bill_date or None,
                            "due_date": due_date or None,
                            "total_due": total_due,
                            "bill_to_address": bill_to or None,
                            "bill_from_address": bill_from or None,
                            "remittance_address": remittance or None,
                            "thread_id": inv.get("thread_id"),  # HITL graph resume
                        }
                        resp = requests.put(
                            f"{API}/review/{inv['id']}/approve",
                            json=payload,
                            timeout=10
                        )
                        if resp.status_code == 200:
                            st.success("✅ Invoice approved! Graph resumed.")
                            st.rerun()
                        else:
                            st.error(f"Error: {resp.text}")

                with col_b:
                    if st.button("❌ Reject", key=f"reject_{inv['id']}"):
                        resp = requests.put(
                            f"{API}/review/{inv['id']}/reject",
                            timeout=5
                        )
                        if resp.status_code == 200:
                            st.warning("Invoice rejected.")
                            st.rerun()
                        else:
                            st.error(f"Error: {resp.text}")

# ── Tab 2: All Invoices ─────────────────────────────────────────────────────
with tab2:
    try:
        all_invoices = requests.get(f"{API}/invoices/", timeout=5).json()
    except Exception:
        all_invoices = []

    col1, col2, col3, col4 = st.columns(4)
    approved = [i for i in all_invoices if i.get("status") == "approved"]
    pending = [i for i in all_invoices if i.get("status") == "pending"]
    duplicates = [i for i in all_invoices if i.get("status") == "duplicate"]
    failed = [i for i in all_invoices if i.get("status") == "failed"]

    col1.metric("✅ Approved", len(approved))
    col2.metric("⏳ Pending", len(pending))
    col3.metric("🔁 Duplicate", len(duplicates))
    col4.metric("❌ Failed", len(failed))

    if all_invoices:
        import pandas as pd
        df = pd.DataFrame(all_invoices)
        display_cols = [
            "id", "pdf_filename", "vendor_name", "invoice_number",
            "account_number", "total_due", "confidence", "status", "created_at"
        ]
        st.dataframe(
            df[[c for c in display_cols if c in df.columns]],
            use_container_width=True
        )

    st.divider()
    st.subheader("📥 Export CSV")
    limit = st.number_input("Max invoices", value=1000, min_value=1)
    if st.button("Generate & Download CSV"):
        resp = requests.post(f"{API}/reports/export-csv?limit={int(limit)}", timeout=30)
        if resp.status_code == 200:
            st.download_button(
                "⬇️ Download CSV",
                data=resp.content,
                file_name=f"invoices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
            )
        else:
            st.error("CSV generation failed.")
