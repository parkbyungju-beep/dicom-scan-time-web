import io
import tempfile
from pathlib import Path

import streamlit as st
from dicom_utils import collect_series_times, save_csv, extract_zip_to_temp

st.set_page_config(page_title="DICOM Scan Time", layout="wide")
st.title("🩻 DICOM Scan Time Summarizer (Multi‑Vendor)")
st.caption("GE / Philips / Canon(Toshiba) / Siemens 지원 — ZIP(폴더 압축) 업로드")

with st.expander("ℹ️ 사용 방법", expanded=True):
    st.markdown(
        """
        1) **DICOM 폴더를 ZIP으로 압축**하세요.  
        2) 아래에 **ZIP 파일을 드래그&드롭**(또는 선택)하세요.  
        3) 처리 후 **시리즈별 스캔타임 표**와 **CSV 다운로드** 버튼이 표시됩니다.

        **주의:** 브라우저 특성상 폴더 자체 업로드는 불가합니다. 반드시 ZIP으로 압축해서 올려주세요.
        """
    )

uploaded = st.file_uploader("DICOM ZIP 파일 업로드", type=["zip"], accept_multiple_files=False)

if uploaded is not None:
    with tempfile.TemporaryDirectory(prefix="dicom_zip_ui_") as td:
        temp_zip = Path(td) / uploaded.name
        with open(temp_zip, "wb") as f:
            f.write(uploaded.read())

        ph = st.empty()
        ph.info("[1/3] 압축 해제 중...")
        tmpdir = extract_zip_to_temp(temp_zip)

        try:
            ph.info("[2/3] DICOM 스캔 중… 파일 구조에 따라 수십 초 소요될 수 있습니다.")
            df, stats = collect_series_times(tmpdir)
        finally:
            pass

        ph.success("[3/3] 완료!")

        if df.empty:
            st.warning("시리즈를 찾지 못했습니다. ZIP 내부 구조 또는 DICOM 유효성을 확인해 주세요.")
        else:
            st.subheader("시리즈별 스캔타임 요약")
            st.dataframe(df, use_container_width=True)

            csv_buf = io.StringIO()
            df.to_csv(csv_buf, index=False)
            st.download_button(
                label="⬇️ CSV 다운로드",
                data=csv_buf.getvalue(),
                file_name=f"{uploaded.name.replace('.zip','')}_scan_times.csv",
                mime="text/csv",
            )

            st.markdown("---")
            st.subheader("처리 통계")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("파일 검사", f"{stats['files_checked']}")
            col2.metric("DICOM 판정", f"{stats['files_dicom']}")
            col3.metric("시리즈 수", f"{stats['series_count']}")
            col4.metric("시간 추출 성공 시리즈", f"{stats['series_with_time']}")