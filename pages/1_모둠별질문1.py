import streamlit as st
import requests
import pandas as pd
import re

st.set_page_config(
    page_title="한 달 동안 같은 반찬이 얼마나 나올까?",
    page_icon="🥗",
    layout="wide"
)

API_URL = "https://open.neis.go.kr/hub"


# =========================================================
# 급식 데이터 가져오기
# =========================================================
@st.cache_data(ttl=3600)
def get_meals(office_code, school_code, year, month):

    start_date = f"{year}{month:02d}01"

    if month == 12:
        next_month = f"{year + 1}0101"
    else:
        next_month = f"{year}{month + 1:02d}01"

    end_date = (
        pd.to_datetime(next_month)
        - pd.Timedelta(days=1)
    ).strftime("%Y%m%d")

    url = f"{API_URL}/mealServiceDietInfo"

    all_rows = []
    page = 1

    # -----------------------------------------------------
    # 중요:
    # pSize를 크게 하고 여러 페이지를 확인한다.
    # -----------------------------------------------------
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

        rows = data["mealServiceDietInfo"][1].get(
            "row",
            []
        )

        if not rows:
            break

        all_rows.extend(rows)

        if len(rows) < 1000:
            break

        page += 1

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)

    df["날짜"] = pd.to_datetime(
        df["MLSV_YMD"],
        format="%Y%m%d",
        errors="coerce"
    )

    df["메뉴"] = (
        df["DDISH_NM"]
        .fillna("")
        .astype(str)
    )

    return df


# =========================================================
# 메뉴 이름 정리
# =========================================================
def clean_menu(menu):

    # <br/>, <br>, <br /> 등을 줄바꿈으로 변경
    menu = re.sub(
        r"<br\s*/?>",
        "\n",
        menu,
        flags=re.IGNORECASE
    )

    # 알레르기 번호 제거
    menu = re.sub(
        r"\(\s*\d+(?:\s*[.,]\s*\d+)*\s*\)",
        "",
        menu
    )

    # HTML 태그 제거
    menu = re.sub(
        r"<[^>]+>",
        "",
        menu
    )

    return menu


# =========================================================
# 메뉴를 하나씩 분리
# =========================================================
def make_menu_rows(df):

    rows = []

    for _, row in df.iterrows():

        menu_text = clean_menu(row["메뉴"])

        menus = menu_text.split("\n")

        for menu in menus:

            menu = menu.strip()

            if not menu:
                continue

            rows.append(
                {
                    "날짜": row["날짜"],
                    "반찬": menu
                }
            )

    return pd.DataFrame(rows)


# =========================================================
# 화면
# =========================================================
st.title("🥗 한 달 동안 같은 반찬이 얼마나 나올까?")

st.write(
    "선택한 학교의 한 달 급식을 분석하여 "
    "같은 메뉴가 몇 번 반복해서 등장했는지 확인합니다."
)

st.divider()


# =========================================================
# 학교 선택 확인
# =========================================================
if "school_code" not in st.session_state:

    st.warning(
        "먼저 첫 화면에서 학교를 선택해 주세요."
    )

    st.stop()


school_name = st.session_state["school_name"]
office_code = st.session_state["office_code"]
school_code = st.session_state["school_code"]


st.info(f"현재 선택된 학교: **{school_name}**")


# =========================================================
# 연도 / 월
# =========================================================
col1, col2 = st.columns(2)

with col1:

    year = st.number_input(
        "연도",
        min_value=2020,
        max_value=2035,
        value=2026,
        step=1
    )

with col2:

    month = st.selectbox(
        "분석할 월",
        range(1, 13),
        index=0
    )


# =========================================================
# 데이터 분석
# =========================================================
if st.button(
    "🔎 반찬 반복 횟수 분석하기",
    type="primary"
):

    with st.spinner(
        "한 달 전체 급식 데이터를 분석하고 있습니다..."
    ):

        df = get_meals(
            office_code,
            school_code,
            year,
            month
        )

    if df.empty:

        st.warning(
            "선택한 달의 급식 데이터가 없습니다."
        )

        st.stop()


    # -----------------------------------------------------
    # 모든 메뉴를 한 줄씩 분리
    # -----------------------------------------------------
    menu_df = make_menu_rows(df)

    if menu_df.empty:

        st.warning(
            "분석할 메뉴 데이터가 없습니다."
        )

        st.stop()


    # -----------------------------------------------------
    # 같은 메뉴를 실제로 합산
    # -----------------------------------------------------
    result = (
        menu_df
        .groupby("반찬")
        .agg(
            나온횟수=("반찬", "size"),
            나온날짜=("날짜", "nunique")
        )
        .reset_index()
    )


    # -----------------------------------------------------
    # 실제 날짜 목록 만들기
    # -----------------------------------------------------
    date_map = (
        menu_df
        .groupby("반찬")["날짜"]
        .apply(
            lambda x: ", ".join(
                sorted(
                    x.dt.day.astype(str).unique(),
                    key=lambda v: int(v)
                )
            )
        )
        .reset_index(name="나온날짜")


    result = (
        result.drop(columns=["나온날짜"])
        .merge(date_map, on="반찬")
    )


    # -----------------------------------------------------
    # 많이 나온 순서대로 정렬
    # -----------------------------------------------------
    result = result.sort_values(
        ["나온횟수", "반찬"],
        ascending=[False, True]
    ).reset_index(drop=True)


    result.insert(
        0,
        "순위",
        range(1, len(result) + 1)
    )


    # -----------------------------------------------------
    # 날짜에 '일' 붙이기
    # -----------------------------------------------------
    result["나온날짜"] = (
        result["나온날짜"]
        .apply(
            lambda x: ", ".join(
                f"{d}일"
                for d in x.split(", ")
            )
        )
    )


    # =====================================================
    # 결과
    # =====================================================
    st.divider()

    st.header("📋 반찬별 전체 등장 횟수")

    st.dataframe(
        result[
            [
                "순위",
                "반찬",
                "나온횟수",
                "나온날짜"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )


    # =====================================================
    # 그래프
    # =====================================================
    st.divider()

    st.header("📊 가장 자주 나온 반찬 TOP 10")

    chart_df = result.head(10).copy()

    chart_df = chart_df.sort_values(
        "나온횟수",
        ascending=True
    )

    st.bar_chart(
        chart_df.set_index("반찬")["나온횟수"]
    )


    # =====================================================
    # 해석
    # =====================================================
    st.divider()

    st.header("💡 이 그래프로 알 수 있는 것")

    top = result.iloc[0]

    st.write(
        f"**{year}년 {month}월 {school_name}**의 급식을 분석한 결과, "
        f"가장 많이 반복해서 나온 메뉴는 "
        f"**{top['반찬']}**으로 총 **{top['나온횟수']}회** "
        f"등장했습니다."
    )

    st.write(
        "표를 통해 한 달 동안 어떤 메뉴가 반복적으로 등장했는지 "
        "비교할 수 있습니다."
    )

    st.caption(
        "※ 메뉴에 표시된 알레르기 유발물질 번호는 메뉴 이름에서 제외했습니다."
    )
