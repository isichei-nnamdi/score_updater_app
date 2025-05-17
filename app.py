import streamlit as st
import pandas as pd
import requests
import json
from io import StringIO
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==========================
# Load Google Sheet Public CSV
# ==========================

@st.cache_data
def load_google_sheet_with_auth(sheet_name: str) -> pd.DataFrame:
    try:
        """Load data from a Google Sheet using service account credentials."""
        # Load credentials from Streamlit secrets
        creds_dict = st.secrets["gcp_service_account"]

        # Define API scope and authorize client
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(credentials)

        # Open the spreadsheet and first worksheet
        sheet_url = "https://docs.google.com/spreadsheets/d/1LKPipvPUmM8bImUz6mGfMhFGKWljSroH42WNYCiMQss"
        worksheet = client.open_by_url(sheet_url).sheet1

        # Fetch all records and return as DataFrame
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    
    except Exception as e:
        st.error(f"❌ Failed to load Google Sheet: {e}")
        return pd.DataFrame()

# @st.cache_data
# def load_google_sheet_with_auth(sheet_name):
#     # try:
#     creds_dict = st.secrets["gcp_service_account"]
#     st.success("✅ Credentials loaded.")

#     scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
#     credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

#     client = gspread.authorize(credentials)
#     st.success("✅ Authorized gspread client.")

#     sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1LKPipvPUmM8bImUz6mGfMhFGKWljSroH42WNYCiMQss")
#     st.success("✅ Opened Google Sheet.")

#     worksheet = sheet.sheet1
#     st.success("✅ Accessed first worksheet.")

#     data = worksheet.get_all_records()
#     st.success("✅ Data fetched from Google Sheet.")

#     return pd.DataFrame(data)

#     # except Exception as e:
#     #     st.error(f"❌ Failed to load Google Sheet: {e}")
#         # return pd.DataFrame()



# ==========================
# Streamlit App UI
# ==========================

st.title("🔁 Student Score Updater")

# Google Sheet Info
# google_sheet_url = "https://docs.google.com/spreadsheets/d/1LKPipvPUmM8bImUz6mGfMhFGKWljSroH42WNYCiMQss/export?format=csv"

# Upload files
file_a = st.file_uploader("📤 Upload File A (Grade Book from LMS)", type=["csv"])
file_b = st.file_uploader("📤 Upload File B (Live Scores Sheet)", type=["csv"])

if file_a and file_b:
    # Load files
    df_a = pd.read_csv(file_a)
    df_b = pd.read_csv(file_b, header=1)  # Read second row as header

    # Load mapping sheet
    st.subheader("📥 Loading Mapping Sheet...")
    mapping_df = load_google_sheet_with_auth("enrolled")

    if not mapping_df.empty:
        try:
            # Normalize column names
            df_a.columns = df_a.columns.str.strip()
            df_b.columns = df_b.columns.str.strip()
            mapping_df.columns = mapping_df.columns.str.strip()

            # Rename for consistency
            email_col = "SIS Login ID"  # Actual column name in File A
            df_a[email_col] = df_a[email_col].astype(str).str.strip().str.lower()
            mapping_df["email"] = mapping_df["email"].astype(str).str.strip().str.lower()

            # Map Student ID to df_a
            email_to_id = dict(zip(mapping_df["email"], mapping_df["Student ID Number"]))
            df_a["Student ID Number"] = df_a[email_col].map(email_to_id)

            # Normalize Student IDs
            df_a["Student ID Number"] = df_a["Student ID Number"].astype(str).str.strip().str.replace(".0", "", regex=False)
            df_b["Student ID Number"] = df_b["Student ID Number"].astype(str).str.strip()

            # ✅ FIX: Clean and convert Total column to numeric
            df_b["Total"] = df_b["Total"].astype(str).str.replace(",", "").str.strip()
            df_b["Total"] = pd.to_numeric(df_b["Total"], errors="coerce").fillna(0)

            # ✅ Optional: Round scores to 2 decimal places
            df_b["Total"] = df_b["Total"].round(2)

            # Create score map
            score_map = dict(zip(df_b["Student ID Number"], df_b["Total"]))

            # Add new scores
            df_a["New Score"] = df_a["Student ID Number"].map(score_map)

            # Column to update
            # st.subheader("📑 Select Column to Update")
            update_col = st.selectbox("Choose the column in File A to update:", df_a.columns)

            st.subheader("Preview of Grade Book")
            st.write(df_a)

            st.subheader("Preview of Live Scores Sheet")
            st.write(df_b)

            if st.button("🔄 Update Scores"):
                df_original = df_a.copy()

                # ✅ Conditionally replace values in update_col
                df_a[update_col] = df_a.apply(
                    lambda row: f"{float(row['New Score']):.2f}" if pd.notnull(row["New Score"]) and str(row[update_col]).strip() == "0.00" else row[update_col],
                    axis=1
                )

                df_updated = df_a.drop(columns=["Student ID Number", "New Score"])

                # 🔍 Preview
                st.subheader("🔍 Preview of Updated Scores")
                st.write(df_updated)
                # st.write("**Before Update:**")
                # st.dataframe(df_original[[update_col]].head())

                # st.write("**After Update:**")
                # st.dataframe(df_updated[[update_col]].head())

                updated_count = df_a["New Score"].notna().sum()
                not_found_count = df_a["New Score"].isna().sum()

                st.subheader("📊 Summary")
                st.write(f"✅ Total records updated: **{updated_count}**")
                st.write(f"❌ Students without matching scores: **{not_found_count}**")

                
                # 📥 Download updated CSV
                csv = df_updated.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Download Updated CSV", csv, "updated_file.csv", "text/csv")

                # 🔎 Debug view
                with st.expander("🔎 Debug Info"):
                    st.dataframe(df_a[[email_col, "Student ID Number", "New Score"]].head(10))

        except Exception as e:
            st.error(f"❌ An error occurred during processing: {e}")
    else:
        st.warning("⚠️ Google Sheet mapping could not be loaded.")

st.markdown(
        """
        <style>
        .main-footer {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background-color: #f0f2f6;
            padding: 10px 0;
            font-size: 13px;
            text-align: center;
            color: #444;
            border-top: 1px solid #ddd;
            z-index: 9999;
        }
        .main-footer a {
            text-decoration: none;
            margin: 0 8px;
            color: #0366d6;
        }
        .main-footer a:hover {
            text-decoration: underline;
        }
        .footer-icons {
            margin-top: 5px;
        }
        .footer-icons a {
            text-decoration: none;
            color: #444;
            margin: 0 10px;
            font-size: 16px;
        }
        </style>
        <div class="main-footer">
            Design, Developed and Deployed by <strong>Nnamdi A. Isichei</strong> &copy; 2025 <br/>
            <div class="footer-icons">
                <a href="https://github.com/isichei-nnamdi" target="_blank">GitHub</a> |
                <a href="https://www.linkedin.com/in/nnamdi-isichei/" target="_blank">LinkedIn</a> |
                <a href="mailto:augustus@miva.university" target="_blank">Email</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
