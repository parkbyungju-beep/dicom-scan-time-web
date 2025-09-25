# DICOM Scan Time Web App (Streamlit)

ZIP으로 압축한 DICOM 폴더를 업로드하면, 시리즈별 스캔 시간(초, 분:초)과 총합을 표로 보여주고 CSV로 다운로드할 수 있는 웹앱입니다. 

## 로컬 실행
```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## 배포 (Streamlit Community Cloud)
1. 이 폴더를 GitHub 저장소로 푸시
2. https://share.streamlit.io 접속 → New app → GitHub repo 선택 → main 브랜치, `app.py` 지정
3. Deploy 클릭 후 제공된 URL을 공유하면 누구나 사용 가능

### 업로드 제한/주의
- 무료 호스팅 환경은 **메모리/파일 크기 제한**이 있습니다. 대용량 ZIP은 Render/VM 등으로 배포하거나 Docker로 자체 호스팅을 권장합니다.
