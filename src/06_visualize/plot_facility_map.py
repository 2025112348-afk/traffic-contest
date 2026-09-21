# -*- coding: utf-8 -*-
"""전국 시설 위치를 점 지도로 시각화한다 (서울 제외).

Colab에서 그대로 실행 가능. 의료시설(HIRA 병원정보서비스)뿐 아니라
버스정류장 등 위경도가 있는 어떤 포인트 데이터에도 재사용할 수 있도록
컬럼명을 일부 자동으로 맞춰 읽는다.

사용법 (Colab):
    from google.colab import files
    uploaded = files.upload()   # 건강보험심사평가원 병원정보서비스에서 받은 csv 선택
    plot_facility_map('업로드한파일명.csv', title='의료시설은 어디에 있을까?')

로컬 실행:
    python plot_facility_map.py --csv data/raw/hira_hospitals.csv --out outputs/figures/medical_map.png
"""

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# 위경도로 흔히 쓰이는 컬럼명 후보들 (HIRA 병원정보서비스 / 공공데이터포털 표준 데이터 모두 커버)
LON_CANDIDATES = ["경도", "XPos", "xPos", "좌표X", "lon", "longitude", "X좌표"]
LAT_CANDIDATES = ["위도", "YPos", "yPos", "좌표Y", "lat", "latitude", "Y좌표"]
SIDO_CANDIDATES = ["시도명", "sidoCdNm", "시도", "sido"]

ACCENT = "#2f6fed"  # 단일 계열 포인트 색 (참고 이미지의 파란 점과 동일 계열)
LAND = "#f4ede1"    # 국토 배경 채움색 (참고 이미지의 베이지톤)
GRID = "#c9c9c9"


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str:
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(
        f"컬럼을 못 찾았습니다. 다음 중 하나가 있어야 합니다: {candidates}\n"
        f"실제 컬럼: {list(df.columns)}"
    )


def _setup_korean_font() -> str:
    """Colab이면 나눔고딕을 설치하고, 아니면 시스템에 있는 한글 폰트를 찾는다."""
    try:
        import google.colab  # noqa: F401
        subprocess.run(["apt-get", "-qq", "-y", "install", "fonts-nanum"], check=False)
        path = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
        if Path(path).exists():
            fm.fontManager.addfont(path)
            return fm.FontProperties(fname=path).get_name()
    except ImportError:
        pass

    for name in ["NanumGothic", "Malgun Gothic", "AppleGothic", "Noto Sans CJK KR"]:
        if any(name.lower() in f.name.lower() for f in fm.fontManager.ttflist):
            return name
    print("한글 폰트를 못 찾았습니다. 라벨이 깨질 수 있습니다 — 나눔고딕 설치를 권장합니다.", file=sys.stderr)
    return "DejaVu Sans"


def _load_korea_outline():
    """국가공간정보포털 등에서 받은 시도 경계 GeoJSON이 있으면 배경으로 깔아준다.
    없으면 조용히 건너뛰고 점만 찍는다 (geopandas 미설치 환경도 그대로 동작)."""
    candidates = [
        Path("data/raw/skorea_provinces_geo.json"),
        Path("data/raw/korea_sido.geojson"),
    ]
    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        return None
    try:
        import geopandas as gpd
        return gpd.read_file(path)
    except Exception as e:
        print(f"국토 경계 파일을 불러오지 못해 점만 표시합니다: {e}", file=sys.stderr)
        return None


def plot_facility_map(
    csv_path: str,
    title: str = "시설은 어디에 있을까?",
    source_note: str = "",
    exclude_seoul: bool = True,
    out_path: str | None = None,
    encoding_candidates=("utf-8-sig", "cp949", "euc-kr"),
):
    df = None
    for enc in encoding_candidates:
        try:
            df = pd.read_csv(csv_path, encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    if df is None:
        raise ValueError(f"인코딩 실패: {csv_path}")

    lon_col = _find_col(df, LON_CANDIDATES)
    lat_col = _find_col(df, LAT_CANDIDATES)
    df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")
    df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
    df = df.dropna(subset=[lon_col, lat_col])
    # 잘못 찍힌 좌표(0,0 등) 제거 — 대한민국 영역 밖 점은 버림
    df = df[df[lon_col].between(124, 132) & df[lat_col].between(33, 39)]

    if exclude_seoul:
        try:
            sido_col = _find_col(df, SIDO_CANDIDATES)
            df = df[~df[sido_col].astype(str).str.contains("서울", na=False)]
        except KeyError:
            print("시도명 컬럼을 못 찾아 서울 제외를 건너뜁니다 — 직접 필터링이 필요할 수 있습니다.", file=sys.stderr)

    font_name = _setup_korean_font()
    plt.rcParams["font.family"] = font_name
    plt.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(9, 9))

    outline = _load_korea_outline()
    if outline is not None:
        outline.plot(ax=ax, color=LAND, edgecolor="white", linewidth=0.6, zorder=1)

    ax.scatter(
        df[lon_col], df[lat_col],
        s=6, color=ACCENT, alpha=0.35, linewidths=0, zorder=2,
    )

    ax.set_xlim(124, 132)
    ax.set_ylim(33, 39)
    ax.set_xlabel("경도 (°)")
    ax.set_ylabel("위도 (°)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(True, color=GRID, linewidth=0.4, alpha=0.6, zorder=0)
    ax.set_facecolor("white")

    n = len(df)
    subtitle = f"{n:,}개 지점"
    if source_note:
        subtitle += f" · {source_note}"
    if exclude_seoul:
        subtitle += " · 서울 제외"

    fig.suptitle(title, fontsize=16, fontweight="bold", x=0.12, ha="left", y=0.97)
    ax.set_title(subtitle, fontsize=10, color="#666666", loc="left", pad=10)

    fig.tight_layout()
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        print(f"저장 완료: {out_path}")
    plt.show()
    return fig, ax


def _make_demo_csv(path: Path, n: int = 500):
    """실제 CSV가 아직 없을 때 스크립트가 바로 돌아가는지 확인용 샘플 데이터.
    ⚠️ 실제 병원 데이터가 아닙니다 — 대한민국 영역 안 무작위 좌표일 뿐입니다."""
    import numpy as np
    rng = np.random.default_rng(0)
    df = pd.DataFrame({
        "요양기관명": [f"샘플의료기관{i}" for i in range(n)],
        "시도명": rng.choice(
            ["경기도", "강원특별자치도", "충청북도", "전라남도", "경상북도", "서울특별시"],
            size=n,
        ),
        "경도": rng.uniform(126.0, 129.5, n),
        "위도": rng.uniform(34.5, 38.3, n),
    })
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default=None, help="위경도가 있는 시설 위치 CSV 경로")
    parser.add_argument("--title", default="의료시설은 어디에 있을까?")
    parser.add_argument("--source", default="", help="부제에 넣을 출처/날짜 메모")
    parser.add_argument("--out", default="outputs/figures/facility_map.png")
    parser.add_argument("--include-seoul", action="store_true")
    parser.add_argument("--demo", action="store_true", help="실제 데이터 없이 샘플로 실행")
    args = parser.parse_args()

    csv_path = args.csv
    if args.demo or csv_path is None:
        demo_path = Path("data/raw/_demo_facility_sample.csv")
        demo_path.parent.mkdir(parents=True, exist_ok=True)
        _make_demo_csv(demo_path)
        csv_path = str(demo_path)
        print(f"[데모 모드] 실제 데이터가 아닌 샘플 좌표로 실행합니다: {csv_path}")
        if not args.source:
            args.source = "샘플 데이터 (실제 아님)"

    plot_facility_map(
        csv_path,
        title=args.title,
        source_note=args.source,
        exclude_seoul=not args.include_seoul,
        out_path=args.out,
    )
