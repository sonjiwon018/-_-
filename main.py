import streamlit as st
import requests
import pandas as pd
import re
from datetime import datetime

st.set_page_config(
    page_title="학교 급식 데이터 분석",
    page_icon="🍱",
    layout="wide"
)

API_URL = "https://open.neis.go.kr/hub"


# =========================================================
# 학교 검색
# =========================================================
@st.cache_data(ttl=3600)
def search_schools(keyword):
    url = f"{API_URL}/schoolInfo"

    params = {
        "Type": "json",
        "pIndex": 1,
        "pSize": 1000,
        "SCHUL_NM": keyword
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "schoolInfo" not in data:
            return pd.DataFrame()

        rows = data["schoolInfo"][1]["row"]

        result = pd.DataFrame(rows)

        return result[
            [
                "ATPT_OFCDC_SC_CODE",
                "ATPT_OFCDC_SC_NM",
                "SD_SCHUL_CODE",
                "SCHUL_NM",
                "LCTN_SC_NM"
            ]
        ]

    except Exception:
        return pd.DataFrame()


# =========================================================
# 급식 데이터 가져오기
# =========================================================
@st.cache_data(ttl=3600)
def get_meals(office_code, school_code, year, month):

    start_date = f"{year}{month:02d}01"

    if month == 12:
        end_date = f"{year + 1}0101"
    else:
        end_date = f"{year}{month + 1:02d}01"

    end_date = (
        pd.to_datetime(end_date) -
        pd.Timedelta(days=1)
    ).strftime("%Y%m%d")

    url = f"{API_URL}/mealServiceDietInfo"

    all_rows = []
    page = 1

    while True:

        params = {
            "Type": "json",
            "pIndex": page,
            "pSize": 1000,
            "ATPT_OFCDC_SC_CODE": office_code,
            "SD_SCHUL_CODE": school_code,
            "MLSV_FROM_YMD": start_date,
            "MLSV_TO_YMD": end_date
        }

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        if "mealServiceDietInfo" not in data:
            break

        rows = data["mealServiceDietInfo"][1].get("row", [])

        if not rows:
            break

        all_rows.extend(rows)

        if len(rows) < 1000:
            break

        page += 1

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)

    columns = [
        "MLSV_YMD",
        "MMEAL_SC_NM",
        "DDISH_NM",
        "CAL_INFO"
    ]

    df = df[[c for c in columns if c in df.columns]]

    df["날짜"] = pd.to_datetime(
        df["MLSV_YMD"],
        format="%Y%m%d",
        errors="coerce"
    )

    df["급식구분"] = df["MMEAL_SC_NM"]

    df["메뉴"] = df["DDISH_NM"].fillna("")

    # 칼로리 숫자만 추출
    df["칼로리"] = (
        df["CAL_INFO"]
        .fillna("")
        .astype(str)
        .str.extract(r"([\d,]+(?:\.\d+)?)")[0]
        .str.replace(",", "", regex=False)
    )

    df["칼로리"] = pd.to_numeric(
        df["칼로리"],
        errors="coerce"
    )

    return df


# =========================================================
# 화면
# =========================================================
st.title("🍱 학교 급식 데이터 분석")

st.write(
    "학교를 선택하면 해당 학교의 급식을 확인하고 "
    "급식 데이터를 다양한 질문으로 분석할 수 있습니다."
)

st.divider()

# ---------------------------------------------------------
# 학교 검색
# ---------------------------------------------------------
st.subheader("🏫 학교 선택")

keyword = st.text_input(
    "학교 이름을 입력하세요",
    placeholder="예: 송탄고등학교"
)

if keyword:

    schools = search_schools(keyword)

    if schools.empty:
        st.warning("검색된 학교가 없습니다.")

    else:

        schools["표시명"] = (
            schools["SCHUL_NM"]
            + " ("
            + schools["LCTN_SC_NM"]
            + ")"
        )

        selected_name = st.selectbox(
            "학교를 선택하세요",
            schools["표시명"].tolist()
        )

        selected = schools[
            schools["표시명"] == selected_name
        ].iloc[0]

        st.session_state["office_code"] = (
            selected["ATPT_OFCDC_SC_CODE"]
        )

        st.session_state["office_name"] = (
            selected["ATPT_OFCDC_SC_NM"]
        )

        st.session_state["school_code"] = (
            selected["SD_SCHUL_CODE"]
        )

        st.session_state["school_name"] = (
            selected["SCHUL_NM"]
        )

        st.session_state["school_location"] = (
            selected["LCTN_SC_NM"]
        )

        st.success(
            f"선택된 학교: {selected['SCHUL_NM']}"
        )


# =========================================================
# 급식 확인
# =========================================================
if "school_code" in st.session_state:

    st.divider()

    st.subheader(
        f"🍚 {st.session_state['school_name']} 급식 보기"
    )

    today = datetime.now()

    col1, col2 = st.columns(2)

    with col1:
        year = st.number_input(
            "연도",
            min_value=2020,
            max_value=2035,
            value=today.year,
            step=1
        )

    with col2:
        month = st.selectbox(
            "월",
            range(1, 13),
            index=today.month - 1
        )

    if st.button("급식 불러오기", type="primary"):

        with st.spinner("급식 데이터를 불러오는 중입니다..."):

            df = get_meals(
                st.session_state["office_code"],
                st.session_state["school_code"],
                year,
                month
            )

        if df.empty:

            st.warning(
                "선택한 기간에는 급식 데이터가 없습니다."
            )

        else:

            st.session_state["meal_df"] = df
            st.session_state["meal_year"] = year
            st.session_state["meal_month"] = month

    # -----------------------------------------------------
    # 이미 불러온 데이터 표시
    # -----------------------------------------------------
    if "meal_df" in st.session_state:

        df = st.session_state["meal_df"]

        st.success(
            f"{st.session_state['meal_year']}년 "
            f"{st.session_state['meal_month']}월 급식 "
            f"{len(df)}건을 불러왔습니다."
        )

        display_df = df[
            ["날짜", "급식구분", "메뉴", "칼로리"]
        ].copy()

        display_df["날짜"] = (
            display_df["날짜"]
            .dt.strftime("%Y-%m-%d")
        )

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )

else:

    st.info(
        "먼저 위에서 학교를 검색하고 선택해 주세요."
    )
