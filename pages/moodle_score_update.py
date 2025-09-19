import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
import os
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(
    page_title="Miva Score Updater",
    page_icon="favicon_io/favicon-16x16.png",
    layout="wide"
)

def should_update(old_value):
    try:
        return float(str(old_value).strip()) == 0.0
    except:
        return False
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
        st.text(traceback.format_exc())
        return pd.DataFrame()

def get_greeting():
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "Good morning"
    elif 12 <= hour < 17:
        return "Good afternoon"
    elif 17 <= hour < 21:
        return "Good evening"
    else:
        return "Hello"


# ==========================
# Streamlit App UI
# ==========================

col1, col2, col3 = st.columns([2, 5, 2])
with col2:
    st.markdown(
             """
        <div style="display: flex; align-items: center;">
            <img src="favicon_io/android-chrome-512x512.png" width="40" style="margin-right: 10px; display: block;">
            <h1 style="margin: 0;">Exam Score Updater</h1>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Display the greeting message
    st.markdown(f"""
        <div style="background-color:#e74c3c; padding:15px; border-radius:10px; color:white; font-weight:bold; font-size:18px;">
        👋 {get_greeting()} and welcome to the Exam Score Updater App, designed by the School of Computing for Miva Open University. 🤗
        </div>

        This app is designed to help you seamlessly update student scores by merging the Grade Book downloaded from the Miva LMS with the Live Score Sheet.

        **How to use the app:**
        1. 📥 Upload the Grade Book file you downloaded from the Miva LMS for the specific course.
        2. 📊 Upload the Live Score Sheet that contains the latest exam scores for the students.
        3. 🛠️ Select the column in the Grade Book that you want to update (e.g., Exam, CA, etc.).
        4. 👀 Preview the updated Grade Book with the new scores.
        5. ✅ Click the Update Scores button to apply the changes.
        6. ⬇️ Download the updated sheet and upload it back to the Miva LMS.

        Feel free to refresh or re-run the app if needed. Happy scoring! 🎯
        """, unsafe_allow_html=True)

    st.write("")
    st.write("")

    # Upload files
    # file_a = st.file_uploader("📤 Upload File A (Grade Book from LMS)", type=["csv"])
    # file_b = st.file_uploader("📤 Upload File B (Live Scores Sheet)", type=["csv"])

    # if file_a and file_b:
    #     # Load files
    #     df_a = pd.read_csv(file_a)
    #     df_b = pd.read_csv(file_b, header=1)  # Read second row as header
    file_a = st.file_uploader("📤 Upload File A (Grade Book from LMS)", type=["csv", "xlsx", "xls"])
    file_b = st.file_uploader("📤 Upload File B (Live Scores Sheet)", type=["csv", "xlsx", "xls"])

    # Get base name of File A (without extension)
    if file_a is not None:
        # Get base name of File A (without extension)
        base_name = os.path.splitext(file_a.name)[0]
    else:
        base_name = "Updated_GradeBook"  # fallback default name

    def load_file(uploaded_file, header=None):
        """Load CSV or Excel depending on extension"""
        if uploaded_file is None:
            return None
        file_type = uploaded_file.name.split(".")[-1].lower()
        if file_type == "csv":
            return pd.read_csv(uploaded_file, header=header)
        elif file_type in ["xlsx", "xls"]:
            return pd.read_excel(uploaded_file, header=header)
        else:
            st.error("❌ Unsupported file format. Please upload CSV or Excel.")
            return None

    if file_a and file_b:
        # Load files dynamically
        df_a = load_file(file_a, header=0)       # Grade Book → use first row as header
        df_b = load_file(file_b, header=1)       # Live Scores → use second row as header


        # Load mapping sheet
        mapping_df = load_google_sheet_with_auth("enrolled")
        st.success("✅ Google Sheet loaded successfully.")


        if not mapping_df.empty:
            try:
                # Normalize column names
                df_a.columns = df_a.columns.str.strip()
                df_b.columns = df_b.columns.str.strip()
                mapping_df.columns = mapping_df.columns.str.strip()

                # Rename for consistency
                email_col = "Email address"  # Actual column name in File A
                df_a[email_col] = df_a[email_col].apply(lambda x: str(x).strip().lower() if pd.notnull(x) else "")
                mapping_df["email"] = mapping_df["email"].astype(str).str.strip().str.lower()

               
                # Map Student ID to df_a
                email_to_id = dict(zip(mapping_df["email"], mapping_df["Student ID Number"]))
                
                df_a["Student ID Number"] = df_a[email_col].map(email_to_id)

                # Normalize Student IDs
                df_a["Student ID Number"] = df_a["Student ID Number"].astype(str).str.strip().str.replace(".0", "", regex=False)
                df_b["Student ID Number"] = df_b["Student ID Number"].astype(str).str.strip().str.replace(".0", "", regex=False)

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

                    # ✅ Update values in the chosen column (overwrite if new score exists)
                    df_a[update_col] = df_a.apply(
                        lambda row: f"{float(row['New Score']):.2f}" if pd.notnull(row["New Score"]) else row[update_col],
                        axis=1
                    )

                    # ✅ Keep track of updated rows only
                    updated_rows = df_a[df_a["New Score"].notna()].copy()

                    # Drop helper columns for final export
                    df_updated = df_a.drop(columns=["Student ID Number", "New Score"])
                    df_updated_only = updated_rows.drop(columns=["Student ID Number", "New Score"])

                    # 🔍 Preview only updated students
                    st.subheader("🔍 Preview of Updated Students")
                    df_updated_only[email_col] = df_updated_only[email_col].fillna("").astype(str).replace("nan", "")
                    st.write(df_updated_only)

                    updated_count = updated_rows.shape[0]
                    not_found_count = df_a["New Score"].isna().sum()

                    st.subheader("📊 Summary")
                    st.write(f"✅ Total records updated: **{updated_count}**")
                    st.write(f"❌ Students without matching scores: **{not_found_count}**")

                    # # 📥 Download options
                    # st.download_button(
                    #     "📥 Download FULL Updated CSV",
                    #     df_updated.to_csv(index=False).encode("utf-8"),
                    #     "updated_file.csv",
                    #     "text/csv"
                    # )
                    # st.download_button(
                    #     "📥 Download ONLY Updated Students",
                    #     df_updated_only.to_csv(index=False).encode("utf-8"),
                    #     "updated_students.csv",
                    #     "text/csv"
                    # )

                    # Construct new filenames
                    full_updated_filename = f"{base_name}_Live Score Updated.csv"
                    updated_only_filename = f"{base_name}_Live Score Updated_Only.csv"

                    # Download buttons with dynamic names
                    st.download_button(
                        "📥 Download FULL Updated CSV",
                        df_updated.to_csv(index=False).encode("utf-8"),
                        full_updated_filename,
                        "text/csv"
                    )
                    st.download_button(
                        "📥 Download ONLY Updated Students",
                        df_updated_only.to_csv(index=False).encode("utf-8"),
                        updated_only_filename,
                        "text/csv"
                    )


                    # 🔎 Debug info
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
            padding: 6px 0;
            font-size: 12px;
            text-align: center;
            color: #444;
            border-top: 1px solid #ddd;
            z-index: 9999;
        }
        .main-footer a {
            text-decoration: none;
            margin: 0 6px;
            color: #0366d6;
        }
        .main-footer a:hover {
            text-decoration: underline;
        }
        .footer-icons {
            margin-top: 4px;
        }
        .footer-icons a {
            text-decoration: none;
            color: #444;
            margin: 0 8px;
            font-size: 13px;
        }
        </style>
        <div class="main-footer">
            Design, Developed and Deployed by the <strong>School of Computing</strong> for Miva Open University &copy; 2025 <br/>
        </div>
        """,
        unsafe_allow_html=True
    )