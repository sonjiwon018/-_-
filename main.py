import streamlit as st
import requests
import pandas as pd
from datetime import datetime


# =========================================================
# 기본 설정
# =========================================================
st.set_page_config(
    page_title="학교 급식 데이터 분석",
    page_icon="🍱",
    layout="wide"
)

API_URL = "https://open.neis.go.kr/hub"


# =========================================================
# NEIS 인증키
# =========================================================
try:
    NEIS_KEY = st.secrets["NEIS_KEY"]
except Exception:
    st.error(
        "NEIS_KEY가 설정되어 있지 않습니다. "
        "Streamlit Cloud의 Secrets에 NEIS_KEY를 등록해주세요."
    )
    st.stop()


# =========================================================
# 학교 검색 함수
# =========================================================
@st.cache_data(ttl=3600)
def search_schools(keyword):

    url = f"{API_URL}/schoolInfo"

    params = {
        "KEY": NEIS_KEY,
        "Type": "json",
        "pIndex": 1,
        "pSize": 100,
        "SCHUL_NM": keyword
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

    except Exception as e:
        st.error(
            f"학교 정보를 불러오는 중 오류가 발생했습니다: {e}"
        )
        return pd.DataFrame()

    if "schoolInfo" not in data:
        return pd.DataFrame()

    try:
        rows = data["schoolInfo"][1]["row"]
    except (KeyError, IndexError):
        return pd.DataFrame()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    needed_columns = [
        "ATPT_OFCDC_SC_CODE",
        "ATPT_OFCDC_SC_NM",
        "SD_SCHUL_CODE",
        "SCHUL_NM",
        "LCTN_SC_NM"
    ]

    existing_columns = [
        col for col in needed_columns
        if col in df.columns
    ]

    return df[existing_columns]


# =========================================================
# 급식 데이터 가져오기
# =========================================================
@st.cache_data(ttl=3600)
def get_meals(
    office_code,
    school_code,
    year,
    month
):

    start_date = f"{year}{month:02d}01"

    # 다음 달 1일 계산
    if month == 12:
        next_month = pd.Timestamp(
            year + 1,
            1,
            1
        )
    else:
        next_month = pd.Timestamp(
            year,
            month + 1,
            1
        )

    end_date = (
        next_month - pd.Timedelta(days=1)
    ).strftime("%Y%m%d")

    url = f"{API_URL}/mealServiceDietInfo"

    all_rows = []
    page = 1

    # =====================================================
    # 한 달 전체 데이터를 가져오기 위해 페이지 반복
    # =====================================================
    while True:

        params = {
            "KEY": NEIS_KEY,
            "Type": "json",
            "pIndex": page,
            "pSize": 1000,
            "ATPT_OFCDC_SC_CODE": office_code,
            "SD_SCHUL_CODE": school_code,
            "MLSV_FROM_YMD": start_date,
            "MLSV_TO_YMD": end_date
        }

        try:
            response = requests.get(
                url,
                params=params,
                timeout=10
            )

            response.raise_for_status()

            data = response.json()

        except Exception as e:
            st.error(
                f"급식 데이터를 불러오는 중 오류가 발생했습니다: {e}"
            )
            return pd.DataFrame()

        if "mealServiceDietInfo" not in data:
            break

        try:
            rows = data["mealServiceDietInfo"][1].get(
                "row",
                []
            )
        except (KeyError, IndexError):
            break

        if not rows:
            break

        all_rows.extend(rows)

        # 1000개보다 적으면 마지막 페이지
        if len(rows) < 1000:
            break

        page += 1

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)

    # =====================================================
    # 날짜
    # =====================================================
    df["날짜"] = pd.to_datetime(
        df["MLSV_YMD"],
        format="%Y%m%d",
        errors="coerce"
    )

    # =====================================================
    # 급식 구분
    # =====================================================
    df["급식구분"] = (
        df["MMEAL_SC_NM"]
        .fillna("")
        .astype(str)
    )

    # =====================================================
    # 메뉴
    # =====================================================
    df["메뉴"] = (
        df["DDISH_NM"]
        .fillna("")
        .astype(str)
    )

    # =====================================================
    # 칼로리
    # 예:
    # "712.3 Kcal" → 712.3
    # =====================================================
    df["칼로리"] = (
        df["CAL_INFO"]
        .fillna("")
        .astype(str)
        .str.extract(
            r"([\d,]+(?:\.\d+)?)"
        )[0]
        .str.replace(
            ",",
            "",
            regex=False
        )
    )

    df["칼로리"] = pd.to_numeric(
        df["칼로리"],
        errors="coerce"
    )

    # =====================================================
    # 필요한 열만 남김
    # =====================================================
    df = df[
        [
            "날짜",
            "급식구분",
            "메뉴",
            "칼로리"
        ]
    ]

    # 날짜순 정렬
    df = df.sort_values(
        ["날짜", "급식구분"]
    ).reset_index(drop=True)

    return df


# =========================================================
# 제목
# =========================================================
st.title("🍱 학교 급식 데이터 분석")

st.write(
    "학교를 선택하면 해당 학교의 급식을 확인하고 "
    "여러 가지 질문을 데이터로 분석할 수 있습니다."
)


st.divider()


# =========================================================
# 학교 검색
# =========================================================
st.header("🏫 학교 선택")

keyword = st.text_input(
