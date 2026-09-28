import streamlit as st
import requests
import pandas as pd
import re
import calendar
from datetime import datetime, timedelta, timezone

st.set_page_config(
    page_title="한 달 동안 같은 반찬이 얼마나 나올까?",
    page_icon="🥗",
    layout="wide"
)

st.title("🥗 한 달 동안 같은 반찬이 얼마나 나올까?")

st.write(
    "선택한 학교의 한 달 동안 중식 메뉴를 분석하여 "
    "같은 반찬이 몇 번 나오는지 알아봅니다."
)

MEAL_URL = (
    "https://open.neis.go.kr/hub/mealServiceDietInfo"
)


# ==================================================
# 한국 시간
# ==================================================
KST = timezone(
    timedelta(hours=9)
)

today = datetime.now(KST).date()


# ==================================================
# main.py에서 선택한 학교 확인
# ==================================================
if "selected_school" not in st.session_state:

    st.info(
        "먼저 첫 화면에서 학교를 검색하고 선택해 주세요."
    )

    st.stop()


school = st.session_state[
    "selected_school"
]

school_name = school.get(
    "SCHUL_NM",
    ""
)

region = school.get(
    "LCTN_SC_NM",
    ""
)


st.success(
    f"🏫 분석할 학교: **{school_name} ({region})**"
)


# ==================================================
# 연도와 월 선택
# ==================================================
st.subheader("📅 분석할 달")

col1, col2 = st.columns(2)


with col1:

    year = st.number_input(
        "연도",
        min_value=2020,
        max_value=today.year,
        value=today.year,
        step=1
    )


with col2:

    if year == today.year:

        month_range = range(
            1,
            today.month + 1
        )

    else:

        month_range = range(
            1,
            13
        )

    month = st.selectbox(
        "월",
        month_range,
        format_func=lambda x: f"{x}월"
    )


# ==================================================
# 해당 월 날짜 계산
# ==================================================
last_day = calendar.monthrange(
    int(year),
    int(month)
)[1]

start_date = datetime(
    int(year),
    int(month),
    1
).date()

end_date = datetime(
    int(year),
    int(month),
    last_day
).date()


# 미래 날짜 방지
if end_date > today:

    end_date = today


# ==================================================
# 급식 API 호출
#
# 인증키가 없으면 한 번에 5건만 올 수 있으므로
# 날짜를 5일씩 나누어 요청한다.
# ==================================================
@st.cache_data(ttl=3600)
def get_month_meals(
    atpt_code,
    school_code,
    start_date,
    end_date
):

    all_rows = []

    current_date = start_date

    while current_date <= end_date:

        # ------------------------------------------
        # 한 번에 최대 5일만 요청
        # ------------------------------------------
        chunk_end = min(
            current_date + timedelta(days=4),
            end_date
        )

        from_ymd = current_date.strftime(
            "%Y%m%d"
        )

        to_ymd = chunk_end.strftime(
            "%Y%m%d"
        )

        params = {
            "Type": "json",

            "ATPT_OFCDC_SC_CODE":
                atpt_code,

            "SD_SCHUL_CODE":
                school_code,

            "MMEAL_SC_CODE":
                "2",

            "MLSV_FROM_YMD":
                from_ymd,

            "MLSV_TO_YMD":
                to_ymd
        }

        try:

            response = requests.get(
                MEAL_URL,
                params=params,
                timeout=15
            )

            response.raise_for_status()

            data = response.json()

        except Exception:

            current_date = (
                chunk_end
                + timedelta(days=1)
            )

            continue


        # ------------------------------------------
        # 데이터가 있는 경우
        # ------------------------------------------
        if "mealServiceDietInfo" in data:

            if len(
                data["mealServiceDietInfo"]
            ) >= 2:

                rows = data[
                    "mealServiceDietInfo"
                ][1].get(
                    "row",
                    []
                )

                all_rows.extend(rows)


        # ------------------------------------------
        # 다음 날짜 구간
        # ------------------------------------------
        current_date = (
            chunk_end
            + timedelta(days=1)
        )


    return all_rows


# ==================================================
# 데이터 가져오기
# ==================================================
with st.spinner(
    "한 달 동안의 급식 데이터를 가져오는 중..."
):

    rows = get_month_meals(
        school[
            "ATPT_OFCDC_SC_CODE"
        ],
        school[
            "SD_SCHUL_CODE"
        ],
        start_date,
        end_date
    )


# ==================================================
# 데이터가 없는 경우
# ==================================================
if not rows:

    st.info(
        f"{year}년 {month}월에는 "
        "등록된 중식 정보가 없어요."
    )

    st.stop()


# ==================================================
# 데이터프레임
# ==================================================
df = pd.DataFrame(rows)


df["MLSV_YMD"] = pd.to_datetime(
    df["MLSV_YMD"],
    format="%Y%m%d"
)


df = df.sort_values(
    "MLSV_YMD"
)


# 같은 날짜가 중복으로 들어오는 경우 제거
df = df.drop_duplicates(
    subset=["MLSV_YMD"]
)


# ==================================================
# 기본 정보
# ==================================================
st.divider()

st.subheader(
    f"📊 {year}년 {month}월 급식 데이터"
)

col1, col2 = st.columns(2)


with col1:

    st.metric(
        "급식이 제공된 날",
        f"{len(df)}일"
    )


with col2:

    st.metric(
        "분석 기간",
        f"{start_date} ~ {end_date}"
    )


# ==================================================
# 메뉴 분리
# ==================================================
menu_list = []


for _, row in df.iterrows():

    date = row["MLSV_YMD"]

    menu_text = str(
        row.get(
            "DDISH_NM",
            ""
        )
    )

    # <br/>, <br>, <br /> 모두 처리
    items = re.split(
        r"<br\s*/?>",
        menu_text,
        flags=re.IGNORECASE
    )


    for item in items:

        item = item.strip()

        # 공백 정리
        item = re.sub(
            r"\s+",
            " ",
            item
        )

        if item:

            menu_list.append({
                "날짜": date,
                "원래메뉴": item
            })


menu_df = pd.DataFrame(
    menu_list
)


if menu_df.empty:

    st.info(
        "분석할 메뉴가 없어요."
    )

    st.stop()


# ==================================================
# 메뉴 이름 정리
# ==================================================
def clean_menu(menu):

    menu = str(menu)

    # ----------------------------------------------
    # 알레르기 번호 제거
    #
    # 김치(5,6,9)
    # → 김치
    # ----------------------------------------------
    menu = re.sub(
        r"\([^)]*\)",
        "",
        menu
    )

    # ----------------------------------------------
    # 앞뒤 기호 제거
    # ----------------------------------------------
    menu = menu.strip(
        " -•·"
    )

    # ----------------------------------------------
    # 공백 정리
    # ----------------------------------------------
    menu = re.sub(
        r"\s+",
        " ",
        menu
    )

    return menu.strip()


menu_df["반찬"] = menu_df[
    "원래메뉴"
].apply(
    clean_menu
)


# ==================================================
# 의미 없는 항목 제거
# ==================================================
menu_df = menu_df[
    menu_df["반찬"].str.len() >= 2
]


menu_df = menu_df[
    ~menu_df["반찬"].str.fullmatch(
        r"\d+"
    )
]


# ==================================================
# 같은 반찬 횟수 계산
# ==================================================
count_df = (
    menu_df
    .groupby("반찬")
    .agg(
        나온횟수=(
            "반찬",
            "count"
        ),

        나온날짜=(
            "날짜",
            "nunique"
        )
    )
    .reset_index()
)


count_df = count_df.sort_values(
    ["나온횟수", "반찬"],
    ascending=[
        False,
        True
    ]
).reset_index(
    drop=True
)


# ==================================================
# 가장 많이 나온 반찬
# ==================================================
most_common = count_df.iloc[0]

most_common_name = most_common[
    "반찬"
]

most_common_count = int(
    most_common["나온횟수"]
)


# ==================================================
# 핵심 결과
# ==================================================
st.divider()

st.subheader(
    "🔎 분석 결과"
)


col1, col2, col3 = st.columns(3)


with col1:

    st.metric(
        "분석한 급식일",
        f"{len(df)}일"
    )


with col2:

    st.metric(
        "종류가 가장 많이 반복된 반찬",
        most_common_name
    )


with col3:

    st.metric(
        "가장 많이 나온 횟수",
        f"{most_common_count}회"
    )


# ==================================================
# 그래프
# ==================================================
st.divider()

st.subheader(
    "📈 반찬별 등장 횟수"
)

st.write(
    "위에 있을수록 한 달 동안 자주 나온 메뉴입니다."
)


# 상위 15개
graph_df = count_df.head(
    15
).copy()


# Streamlit bar chart에서
# 위쪽에 가장 많이 나온 항목이 보이도록 역순
graph_df = graph_df.sort_values(
    "나온횟수",
    ascending=True
)


st.bar_chart(
    graph_df.set_index(
        "반찬"
    )["나온횟수"]
)


# ==================================================
# 전체 결과 표
# ==================================================
st.divider()

st.subheader(
    "📋 반찬별 전체 등장 횟수"
)


display_df = count_df.copy()

display_df.insert(
    0,
    "순위",
    range(
        1,
        len(display_df) + 1
    )
)


st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)


# ==================================================
# 질문에 대한 해석
# ==================================================
st.divider()

st.subheader(
    "💡 이 그래프로 알 수 있는 것"
)


st.write(
    f"""
**{year}년 {month}월 {school_name}의 중식**을 분석한 결과,
가장 많이 반복해서 나온 메뉴는 **{most_common_name}**으로
총 **{most_common_count}회** 등장했습니다.

이 그래프를 통해 한 달 동안 어떤 반찬이 자주 반복되고,
어떤 반찬은 상대적으로 적게 나오는지 비교할 수 있습니다.
"""
)


st.caption(
    "※ 메뉴에 표시된 알레르기 번호는 반복 횟수 계산에서 제외했습니다."
)
