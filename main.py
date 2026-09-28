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
        st.error(f"학교 정보를 불러오는 중 오류가 발생했습니다: {e}")
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

    # -----------------------------------------------------
    # 한 달 전체 데이터를 가져오기 위해 페이지 반복
    # -----------------------------------------------------
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

    # -----------------------------------------------------
    # 날짜
    # -----------------------------------------------------
    df["날짜"] = pd.to_datetime(
        df["MLSV_YMD"],
        format="%Y%m%d",
        errors="coerce"
    )

    # -----------------------------------------------------
    # 급식 구분
    # -----------------------------------------------------
    df["급식구분"] = (
        df["MMEAL_SC_NM"]
        .fillna("")
        .astype(str)
    )

    # -----------------------------------------------------
    # 메뉴
    # -----------------------------------------------------
    df["메뉴"] = (
        df["DDISH_NM"]
        .fillna("")
        .astype(str)
    )

    # -----------------------------------------------------
    # 칼로리
    # 예:
    # "712.3 Kcal" → 712.3
    # -----------------------------------------------------
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

    # -----------------------------------------------------
    # 필요한 열만 남김
    # -----------------------------------------------------
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
    "학교 이름을 입력하세요.",
    placeholder="예: 송탄고등학교"
)


if keyword.strip():

    schools = search_schools(
        keyword.strip()
    )

    if schools.empty:

        st.warning(
            "검색된 학교가 없습니다. "
            "학교 이름을 다시 확인해주세요."
        )

    else:

        # -------------------------------------------------
        # 같은 학교명이 있을 수 있으므로
        # 지역까지 표시
        # -------------------------------------------------
        schools["표시명"] = (
            schools["SCHUL_NM"]
            + " · "
            + schools["LCTN_SC_NM"]
        )

        selected_name = st.selectbox(
            "학교를 선택하세요.",
            schools["표시명"].tolist()
        )

        selected_school = schools[
            schools["표시명"] == selected_name
        ].iloc[0]


        # -------------------------------------------------
        # 선택한 학교 정보를 session_state에 저장
        # -------------------------------------------------
        st.session_state["office_code"] = (
            selected_school["ATPT_OFCDC_SC_CODE"]
        )

        st.session_state["office_name"] = (
            selected_school["ATPT_OFCDC_SC_NM"]
        )

        st.session_state["school_code"] = (
            selected_school["SD_SCHUL_CODE"]
        )

        st.session_state["school_name"] = (
            selected_school["SCHUL_NM"]
        )

        st.session_state["school_location"] = (
            selected_school["LCTN_SC_NM"]
        )


        st.success(
            f"현재 선택한 학교: "
            f"**{selected_school['SCHUL_NM']}**"
        )


# =========================================================
# 학교가 선택된 경우 급식 보기
# =========================================================
if "school_code" in st.session_state:

    st.divider()

    st.header("🍚 급식 확인")

    st.write(
        f"**{st.session_state['school_name']}**의 "
        "원하는 월 급식을 확인할 수 있습니다."
    )


    # -----------------------------------------------------
    # 날짜 선택
    # -----------------------------------------------------
    now = datetime.now()

    col1, col2 = st.columns(2)

    with col1:

        selected_year = st.number_input(
            "연도",
            min_value=2020,
            max_value=2035,
            value=now.year,
            step=1
        )

    with col2:

        selected_month = st.selectbox(
            "월",
            list(range(1, 13)),
            index=now.month - 1
        )


    # -----------------------------------------------------
    # 급식 불러오기
    # -----------------------------------------------------
    if st.button(
        "📥 급식 불러오기",
        type="primary"
    ):

        with st.spinner(
            "급식 데이터를 불러오는 중입니다..."
        ):

            meal_df = get_meals(
                st.session_state["office_code"],
                st.session_state["school_code"],
                selected_year,
                selected_month
            )


        if meal_df.empty:

            st.warning(
                f"{selected_year}년 "
                f"{selected_month}월에는 "
                "급식 데이터가 없습니다."
            )

            # 이전 데이터 삭제
            st.session_state.pop(
                "meal_df",
                None
            )

        else:

            # ---------------------------------------------
            # 다른 페이지에서 사용할 수 있도록 저장
            # ---------------------------------------------
            st.session_state["meal_df"] = meal_df

            st.session_state["meal_year"] = (
                selected_year
            )

            st.session_state["meal_month"] = (
                selected_month
            )

            st.success(
                f"{selected_year}년 "
                f"{selected_month}월 급식 데이터를 "
                f"{len(meal_df)}건 불러왔습니다."
            )


# =========================================================
# 불러온 급식 표시
# =========================================================
if "meal_df" in st.session_state:

    st.divider()

    st.header("📋 급식표")

    meal_df = st.session_state["meal_df"].copy()

    display_df = meal_df.copy()

    display_df["날짜"] = (
        display_df["날짜"]
        .dt.strftime("%Y-%m-%d")
    )

    display_df["칼로리"] = display_df[
        "칼로리"
    ].apply(
        lambda x:
        f"{x:,.1f} kcal"
        if pd.notna(x)
        else "-"
    )

    display_df = display_df.rename(
        columns={
            "날짜": "날짜",
            "급식구분": "급식 구분",
            "메뉴": "메뉴",
            "칼로리": "칼로리"
        }
    )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )


    # -----------------------------------------------------
    # 데이터 요약
    # -----------------------------------------------------
    st.divider()

    st.header("📊 데이터 요약")

    col1, col2, col3 = st.columns(3)

    with col1:

        meal_days = meal_df[
            "날짜"
        ].nunique()

        st.metric(
            "급식이 제공된 날짜",
            f"{meal_days}일"
        )

    with col2:

        avg_calorie = meal_df[
            "칼로리"
        ].mean()

        if pd.notna(avg_calorie):

            st.metric(
                "평균 칼로리",
                f"{avg_calorie:,.1f} kcal"
            )

        else:

            st.metric(
                "평균 칼로리",
                "-"
            )

    with col3:

        st.metric(
            "급식 데이터",
            f"{len(meal_df)}건"
        )


else:

    st.info(
        "학교를 선택한 뒤 연도와 월을 정하고 "
        "'급식 불러오기'를 눌러주세요."
    )
