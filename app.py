import io
import tempfile
from pathlib import Path

import streamlit as st
from dicom_utils import collect_series_times, save_csv, extract_zip_to_temp

st.set_page_config(page_title="DICOM Scan Time", layout="wide")
st.title("🩻 DICOM Scan Time Summarizer (Multi-Vendor)")
st.caption("Supports GE / Philips / Canon (Toshiba) / Siemens — Upload a ZIP (compressed folder)")

with st.expander("ℹ️ How to Use", expanded=True):
    st.markdown(
        """
        1) **Compress your DICOM folder into a ZIP file.**  
        2) **Drag & drop** (or select) the ZIP file below.  
        3) After processing, you'll see a **series-wise scan time table** and a **CSV download** button.

        **Note:** Due to browser limitations, you cannot upload folders directly. Please compress your DICOM folder into a ZIP file before uploading.
        """
    )

uploaded = st.file_uploader("Upload DICOM ZIP file", type=["zip"], accept_multiple_files=False)

if uploaded is not None:
    with tempfile.TemporaryDirectory(prefix="dicom_zip_ui_") as td:
        temp_zip = Path(td) / uploaded.name
        with open(temp_zip, "wb") as f:
            f.write(uploaded.read())

        ph = st.empty()
        ph.info("[1/3] Extracting ZIP file...")
        tmpdir = extract_zip_to_temp(temp_zip)

        try:
            ph.info("[2/3] Scanning DICOM files… This may take several seconds depending on folder structure.")
            df, stats = collect_series_times(tmpdir)
        finally:
            pass

        ph.success("[3/3] Done!")

        if df.empty:
            st.warning("No series found. Please check the ZIP structure or DICOM file validity.")
        else:
            # --- UI preference: hide SeriesInstanceUID + show Number of Instances as 2nd column ---
            display_df = df.drop(columns=["SeriesInstanceUID"], errors="ignore")
            preferred = ["Series", "Number of Instances", "Manufacturer", "TagUsed", "RawValue", "Unit", "ScanTime", "Seconds"]
            final_cols = [c for c in preferred if c in display_df.columns] + [c for c in display_df.columns if c not in preferred]
            display_df = display_df[final_cols]

            st.subheader("Series-wise Scan Time Summary")
            st.dataframe(display_df, use_container_width=True)

            csv_buf = io.StringIO()
            df.to_csv(csv_buf, index=False)
            st.download_button(
                label="⬇️ Download CSV",
                data=csv_buf.getvalue(),
                file_name=f"{uploaded.name.replace('.zip','')}_scan_times.csv",
                mime="text/csv",
            )

            st.markdown("---")
            st.subheader("Processing Statistics")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Files Checked", f"{stats['files_checked']}")
            col2.metric("Valid DICOM Files", f"{stats['files_dicom']}")
            col3.metric("Series Count", f"{stats['series_count']}")
            col4.metric("Series with Extracted Time", f"{stats['series_with_time']}")

st.caption("Made by AIRS Medical 2025 CCS Team")
