
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, re, csv, zipfile, tempfile
from pathlib import Path
from typing import Any, Dict, Tuple, Optional

import pandas as pd
from pydicom import dcmread
from pydicom.tag import Tag

def extract_zip_to_temp(zip_path: Path) -> Path:
    tmpdir = Path(tempfile.mkdtemp(prefix="dicom_zip_"))
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(tmpdir)
    return tmpdir

def is_dicom_file(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            header = f.read(132)
            if len(header) >= 132 and header[128:132] == b"DICM":
                return True
    except Exception:
        pass
    try:
        dcmread(str(path), stop_before_pixels=True, force=True)
        return True
    except Exception:
        return False

def _normalize_value(val: Any) -> Optional[Any]:
    if val is None:
        return None
    if isinstance(val, (list, tuple)):
        return _normalize_value(val[0]) if val else None
    if isinstance(val, bytes):
        try:
            s = val.decode(errors="ignore").strip()
            return s if s else None
        except Exception:
            return None
    return val

def seconds_to_min_sec_str(total_seconds: Optional[float]) -> Optional[str]:
    if total_seconds is None:
        return None
    try:
        sec = int(round(float(total_seconds)))
    except Exception:
        return None
    mm, ss = divmod(sec, 60)
    return f"{mm} min {ss} sec"

def microseconds_to_seconds(value_us: Any) -> Optional[float]:
    try:
        v = float(str(value_us).strip())
    except Exception:
        return None
    return v / 1_000_000.0

TA_PATTERN = re.compile(r"\bTA\s*[:]??\s*(\d{1,2}):(\d{2})(?:\s*\*\s*(\d+))?\b", re.IGNORECASE)

# NEW: 'TA 50.12*2' 같은 "초[.소수]*배수" 패턴도 지원 (콤마 소수점도 허용)
TA_PATTERN_SEC = re.compile(
    r"\bTA\s*[:]?\s*(\d+(?:[.,]\d+)?)(?:\s*\*\s*(\d+))?\b",
    re.IGNORECASE
)

def parse_ta_string(text: Optional[str]) -> Optional[float]:
    """'TA 01:08*2' 또는 'TA 50.12*2' → seconds.
    - 'mm:ss[*mult]'을 우선 해석
    - 없으면 'ss[.fraction][*mult]' 해석 (소수점은 버림)
    """
    if not text:
        return None

    # 1) mm:ss[*mult]
    m = TA_PATTERN.search(text)
    if m:
        mm = int(m.group(1))
        ss = int(m.group(2))
        mult = int(m.group(3)) if m.group(3) else 1
        return float((mm * 60 + ss) * mult)

    # 2) ss[.fraction][*mult] → 소수점은 버리고 정수 초로 계산
    m2 = TA_PATTERN_SEC.search(text)
    if m2:
        sec_str = m2.group(1).replace(",", ".")  # '50,12'도 허용
        try:
            base_sec = int(float(sec_str))       # 50.12 → 50
        except Exception:
            return None
        mult = int(m2.group(2)) if m2.group(2) else 1
        return float(base_sec * mult)

    return None


VENDOR_GE = "GE"
VENDOR_PHILIPS = "Philips"
VENDOR_CANON = "Canon"
VENDOR_TOSHIBA = "Toshiba"
VENDOR_SIEMENS = "Siemens"

TAG_GE_TIME = Tag(0x0019, 0x105A)
TAG_ACQ_DURATION = Tag(0x0018, 0x9073)
TAG_SIEMENS_TA = Tag(0x0051, 0x100A)
TAG_SERIES_DESC = Tag(0x0008, 0x103E)
TAG_PROTOCOL_NAME = Tag(0x0018, 0x1030)

def detect_vendor(ds) -> str:
    vendor_raw = str(getattr(ds, "Manufacturer", "")).strip()
    vlow = vendor_raw.lower()
    if "siemens" in vlow:
        return VENDOR_SIEMENS
    if "philips" in vlow:
        return VENDOR_PHILIPS
    if "canon" in vlow:
        return VENDOR_CANON
    if "toshiba" in vlow:
        return VENDOR_CANON
    if "ge" in vlow:
        return VENDOR_GE
    return vendor_raw or "Unknown"

def extract_scan_seconds_for_series(ds) -> Tuple[Optional[float], str, Optional[str]]:
    vendor = detect_vendor(ds)
    if vendor == VENDOR_GE and TAG_GE_TIME in ds:
        raw = _normalize_value(ds.get(TAG_GE_TIME).value)
        sec = microseconds_to_seconds(raw)
        return sec, "(0019,105A)", str(raw) if raw is not None else None
    if TAG_ACQ_DURATION in ds:
        raw = _normalize_value(ds.get(TAG_ACQ_DURATION).value)
        try:
            sec = float(str(raw).strip()) if raw is not None else None
        except Exception:
            sec = None
        return sec, "(0018,9073)", str(raw) if raw is not None else None
    if vendor == VENDOR_SIEMENS and TAG_SIEMENS_TA in ds:
        raw = _normalize_value(ds.get(TAG_SIEMENS_TA).value)
        sec = parse_ta_string(str(raw)) if raw is not None else None
        if sec is not None:
            return sec, "(0051,100A)", str(raw)
    if vendor == VENDOR_SIEMENS:
        for tag, label in ((TAG_SERIES_DESC, "SeriesDescription"), (TAG_PROTOCOL_NAME, "ProtocolName")):
            if tag in ds:
                raw = _normalize_value(ds.get(tag).value)
                sec = parse_ta_string(str(raw)) if raw is not None else None
                if sec is not None:
                    return sec, f"TA in {label}", str(raw)
    return None, "", None

def collect_series_times(root: Path):
    series_map: Dict[str, Dict[str, Any]] = {}
    files_checked = 0
    files_dicom = 0
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            p = Path(dirpath) / fn
            if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".txt", ".json", ".xml", ".csv", ".zip"}:
                continue
            if not is_dicom_file(p):
                continue
            files_checked += 1
            try:
                ds = dcmread(str(p), stop_before_pixels=True, force=True)
            except Exception:
                continue
            files_dicom += 1
            series_uid = getattr(ds, "SeriesInstanceUID", None) or getattr(ds, "StudyInstanceUID", None) or "unknown"
            series_desc = getattr(ds, "SeriesDescription", None)
            if not series_desc:
                series_num = getattr(ds, "SeriesNumber", None)
                series_desc = f"Series {series_num}" if series_num is not None else "Unknown Series"
            entry = series_map.setdefault(series_uid, {
                "Series": series_desc,
                "SeriesInstanceUID": series_uid,
                "Manufacturer": str(getattr(ds, "Manufacturer", "")),
                "TagUsed": None,
                "RawValue": None,
                "Unit": None,
                "Number of Instances": 0,
                "Seconds": None,
            })
            entry["Number of Instances"] += 1
            if entry["Seconds"] is None:
                sec, tag_used, raw = extract_scan_seconds_for_series(ds)
                if sec is not None:
                    entry["Seconds"] = float(sec)
                    entry["TagUsed"] = tag_used
                    entry["RawValue"] = raw
                    if tag_used == "(0019,105A)":
                        entry["Unit"] = "microseconds"
                    elif tag_used == "(0018,9073)":
                        entry["Unit"] = "seconds"
                    elif tag_used == "(0051,100A)" or tag_used.startswith("TA in"):
                        entry["Unit"] = "mm:ss or sec[*mult]"
    rows = list(series_map.values())
    df = pd.DataFrame(rows).sort_values(["Series"]).reset_index(drop=True)
    df["ScanTime"] = df["Seconds"].apply(seconds_to_min_sec_str)
    total_seconds = pd.to_numeric(df["Seconds"], errors="coerce").sum()
    total_row = {
        "Series": "TotalScanTime",
        "SeriesInstanceUID": None,
        "Manufacturer": None,
        "TagUsed": None,
        "RawValue": None,
        "Unit": None,
        "Number of Instances": None,
        "Seconds": float(total_seconds) if pd.notnull(total_seconds) else None,
        "ScanTime": seconds_to_min_sec_str(total_seconds),
    }
    df.loc[len(df)] = total_row
    stats = {
        "files_checked": files_checked,
        "files_dicom": files_dicom,
        "series_count": len(series_map),
        "series_with_time": int(df["Seconds"].notna().sum() - 1),
    }
    return df, stats

def save_csv(df, out_csv: Path) -> None:
    df.to_csv(out_csv, index=False, quoting=csv.QUOTE_MINIMAL)
