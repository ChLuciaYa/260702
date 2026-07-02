"""
🧭 대한민국 인구 구조 탐험 대시보드
-----------------------------------------
행정안전부 '연령별 인구현황(월간)' CSV를 업로드하면
지역별 인구 피라미드, 연령 분포, 고령화 지표, 그리고
최근 출생율 반등 신호까지 인터랙티브하게 탐색할 수 있는
청소년 인구교육용 Streamlit 대시보드입니다.

배포: Streamlit Community Cloud
실행: streamlit run app.py
"""

import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

# =================================================================
# 0. 기본 설정
# =================================================================

st.set_page_config(
    page_title="대한민국 인구 구조 탐험 대시보드",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_DATA_PATH = "data/population.csv"
NATION_LABEL = "🇰🇷 전국 (17개 시도 합계)"

PRIMARY = "#2E5EAA"      # 남 계열 (블루)
SECONDARY = "#E0607E"    # 여 계열 (핑크)
ACCENT = "#F5A623"       # 강조 (오렌지)
GREEN = "#4CAF7D"        # 긍정 신호

# =================================================================
# 1. 데이터 로드 & 전처리
# =================================================================


@st.cache_data(show_spinner="📂 CSV 파일을 읽는 중이에요...")
def load_raw(file_or_path) -> pd.DataFrame:
    """행안부 CSV는 보통 EUC-KR/CP949 인코딩이라 순서대로 시도합니다."""
    encodings = ["cp949", "euc-kr", "utf-8-sig", "utf-8"]
    last_err = None
    for enc in encodings:
        try:
            if hasattr(file_or_path, "seek"):
                file_or_path.seek(0)
            return pd.read_csv(file_or_path, encoding=enc, low_memory=False)
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    raise ValueError(f"CSV를 읽을 수 없어요. 인코딩을 확인해주세요. ({last_err})")


def parse_region(raw: str):
    """'서울특별시 종로구 (1111000000)' -> (이름, 코드, 레벨)"""
    raw = str(raw).strip()
    m = re.search(r"\((\d+)\)\s*$", raw)
    code = m.group(1) if m else ""
    name = re.sub(r"\s*\(\d+\)\s*$", "", raw).strip()
    name = re.sub(r"\s+", " ", name)

    trailing_zeros = len(code) - len(code.rstrip("0")) if code else 0
    if trailing_zeros >= 8:
        level = "시도"
    elif trailing_zeros >= 5:
        level = "시군구"
    else:
        level = "읍면동"
    return name, code, level


MONTH_PATTERN = re.compile(r"^(\d{4}년\d{2}월)_(계|남|여)_(.+)$")


@st.cache_data(show_spinner="🧮 인구 데이터를 정리하는 중이에요...")
def preprocess(df: pd.DataFrame):
    df = df.copy()
    region_col = df.columns[0]

    parsed = df[region_col].apply(parse_region)
    df["__name"] = parsed.apply(lambda x: x[0])
    df["__code"] = parsed.apply(lambda x: x[1])
    df["__level"] = parsed.apply(lambda x: x[2])

    months = sorted({m.group(1) for c in df.columns for m in [MONTH_PATTERN.match(c)] if m})
    numeric_cols = [c for c in df.columns if MONTH_PATTERN.match(c)]

    for c in numeric_cols:
        cleaned = df[c].astype(str).str.replace(",", "", regex=False).str.replace("-", "0", regex=False)
        df[c] = pd.to_numeric(cleaned, errors="coerce").fillna(0).astype(np.int64)

    return df, months


def age_columns(month, gender):
    cols = [f"{month}_{gender}_{i}세" for i in range(0, 100)]
    cols.append(f"{month}_{gender}_100세 이상")
    return cols


@st.cache_data(show_spinner=False)
def build_summary(df: pd.DataFrame, months: list):
    """지역 x 월 단위 총인구 / 유소년 / 생산연령 / 고령 / 부양비 요약표"""
    records = []
    for month in months:
        cols_all = age_columns(month, "계")
        cols_all = [c for c in cols_all if c in df.columns]
        age_matrix = df[cols_all].to_numpy()

        young = age_matrix[:, 0:15].sum(axis=1)
        working = age_matrix[:, 15:65].sum(axis=1)
        old = age_matrix[:, 65:101].sum(axis=1)
        total = age_matrix.sum(axis=1)

        with np.errstate(divide="ignore", invalid="ignore"):
            aging_index = np.where(young > 0, old / young * 100, np.nan)
            old_dep = np.where(working > 0, old / working * 100, np.nan)
            young_dep = np.where(working > 0, young / working * 100, np.nan)

        chunk = pd.DataFrame({
            "월": month,
            "지역명": df["__name"].values,
            "코드": df["__code"].values,
            "레벨": df["__level"].values,
            "총인구": total,
            "유소년인구": young,
            "생산연령인구": working,
            "고령인구": old,
            "고령화지수": aging_index,
            "노년부양비": old_dep,
            "유소년부양비": young_dep,
        })
        records.append(chunk)
    return pd.concat(records, ignore_index=True)


def get_age_series(df: pd.DataFrame, region_name: str, month: str, gender: str) -> pd.Series:
    """0~100+ 세 인구를 index 0..100 Series로 반환. 전국은 시도 17개 합산."""
    cols = [c for c in age_columns(month, gender) if c in df.columns]
    if region_name == NATION_LABEL:
        sub = df[df["__level"] == "시도"]
        vals = sub[cols].sum(axis=0).values
    else:
        row = df[df["__name"] == region_name]
        if row.empty:
            return pd.Series([0] * 101, index=range(0, 101))
        vals = row[cols].iloc[0].values
    return pd.Series(vals, index=range(0, len(vals)))


def bin_ages_5y(series: pd.Series):
    labels, values = [], []
    for start in range(0, 100, 5):
        end = start + 4
        labels.append(f"{start}-{end}세")
        values.append(int(series.loc[start:end].sum()))
    labels.append("100세 이상")
    values.append(int(series.loc[100]))
    return labels, values


def fmt(n):
    if n is None or (isinstance(n, float) and np.isnan(n)):
        return "-"
    return f"{n:,.0f}"


def fmt1(n):
    if n is None or (isinstance(n, float) and np.isnan(n)):
        return "-"
    return f"{n:,.1f}"


# =================================================================
# 2. 사이드바 - 데이터 소스 & 지역 선택
# =================================================================

st.sidebar.title("🧭 컨트롤 패널")
st.sidebar.caption("행정안전부 «연령별 인구현황(월간)» CSV 기반")

uploaded = st.sidebar.file_uploader(
    "📁 다른 월(또는 다른 지역) CSV 업로드",
    type=["csv"],
    help="기본으로는 함께 배포된 202606월 데이터를 사용해요. "
         "다른 달 파일을 올리면 최신 데이터로 바로 갱신됩니다.",
)

try:
    raw_df = load_raw(uploaded) if uploaded is not None else load_raw(DEFAULT_DATA_PATH)
except Exception as e:  # noqa: BLE001
    st.error(f"데이터를 불러오지 못했어요 😢\n\n{e}")
    st.stop()

df, months = preprocess(raw_df)
summary_all = build_summary(df, months)

if not months:
    st.error("월별 인구 컬럼을 찾지 못했어요. 행정안전부 표준 양식 CSV인지 확인해주세요.")
    st.stop()

st.sidebar.markdown("---")
selected_month = st.sidebar.selectbox("📅 기준 월", months, index=len(months) - 1)

level_option = st.sidebar.radio("🗺️ 지역 단위", ["시도", "시군구", "읍면동"], horizontal=True)

region_pool = sorted(df.loc[df["__level"] == level_option, "__name"].unique().tolist())
region_choices = [NATION_LABEL] + region_pool if level_option == "시도" else region_pool

default_region = NATION_LABEL if level_option == "시도" else region_pool[0]
selected_region = st.sidebar.selectbox(
    "📍 분석할 지역 선택",
    region_choices,
    index=region_choices.index(default_region) if default_region in region_choices else 0,
)

compare_regions = st.sidebar.multiselect(
    "⚖️ 비교할 지역 (최대 6개, '지역 비교' 탭에서 사용)",
    region_choices,
    default=[selected_region],
    max_selections=6,
)

st.sidebar.markdown("---")
st.sidebar.info(
    "💡 **Tip.** 이 파일에는 "
    f"**{len(months)}개월치**({', '.join(months)}) 데이터가 들어있어요. "
    "여러 달을 한 번에 내려받은 CSV를 올리면 출생아 수 추세를 실제 시계열로도 볼 수 있어요!"
)

# =================================================================
# 3. 헤더
# =================================================================

st.title("🧭 대한민국 인구 구조 탐험 대시보드")
st.caption("숫자 속에 숨은 우리 동네 이야기를 함께 읽어봐요 🔎✨")

tabs = st.tabs([
    "🏠 개요",
    "🔺 인구 피라미드",
    "📈 연령별 분포",
    "👶 출생율 반등 인사이트",
    "⚖️ 지역 비교",
    "📚 용어 사전",
])

# -----------------------------------------------------------------
# TAB 1. 개요
# -----------------------------------------------------------------
with tabs[0]:
    row = summary_all[(summary_all["월"] == selected_month) & (summary_all["지역명"] == selected_region)]
    if selected_region == NATION_LABEL:
        nat = summary_all[(summary_all["월"] == selected_month) & (summary_all["레벨"] == "시도")]
        total = nat["총인구"].sum()
        young = nat["유소년인구"].sum()
        working = nat["생산연령인구"].sum()
        old = nat["고령인구"].sum()
        aging_index = old / young * 100 if young else np.nan
        old_dep = old / working * 100 if working else np.nan
        young_dep = young / working * 100 if working else np.nan
    elif not row.empty:
        r = row.iloc[0]
        total, young, working, old = r["총인구"], r["유소년인구"], r["생산연령인구"], r["고령인구"]
        aging_index, old_dep, young_dep = r["고령화지수"], r["노년부양비"], r["유소년부양비"]
    else:
        total = young = working = old = 0
        aging_index = old_dep = young_dep = np.nan

    st.subheader(f"📍 {selected_region} · {selected_month} 스냅샷")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 총인구", f"{fmt(total)}명")
    c2.metric("🧒 유소년 (0-14세)", f"{fmt(young)}명", f"{young/total*100:.1f}%" if total else None)
    c3.metric("💼 생산연령 (15-64세)", f"{fmt(working)}명", f"{working/total*100:.1f}%" if total else None)
    c4.metric("👴 고령 (65세+)", f"{fmt(old)}명", f"{old/total*100:.1f}%" if total else None)

    c5, c6, c7 = st.columns(3)
    c5.metric("📐 고령화지수", fmt1(aging_index), help="유소년 100명당 고령 인구 수. 100을 넘으면 고령 인구가 유소년보다 많다는 뜻이에요.")
    c6.metric("🧓 노년부양비", fmt1(old_dep), help="생산연령인구 100명이 부양해야 하는 고령인구 수")
    c7.metric("🍼 유소년부양비", fmt1(young_dep), help="생산연령인구 100명이 부양해야 하는 유소년 수")

    # 고령사회 단계 뱃지
    elderly_share = old / total * 100 if total else 0
    if elderly_share >= 20:
        stage, color = "초고령사회 (65세 이상 20% 이상)", "🔴"
    elif elderly_share >= 14:
        stage, color = "고령사회 (65세 이상 14~20%)", "🟠"
    elif elderly_share >= 7:
        stage, color = "고령화사회 (65세 이상 7~14%)", "🟡"
    else:
        stage, color = "고령화 이전 단계 (65세 이상 7% 미만)", "🟢"
    st.info(f"{color} **{selected_region}**은(는) 현재 UN 기준 **{stage}** 에 해당해요.")

    st.markdown(
        """
        > 🧑‍🏫 **잠깐! 이 숫자들은 어디서 왔을까요?**
        > 이 대시보드는 매달 행정안전부가 발표하는 **주민등록 인구통계**를 사용해요.
        > 즉, "이 순간 이 동네에 주민등록이 되어있는 사람 수"를 말해요 — 실제로 태어나거나 사망한 사람 수(통계청 '인구동향조사')와는
        > 집계 방식이 조금 달라요. 이 차이는 아래 **'출생율 반등 인사이트'** 탭에서 더 자세히 알아볼게요!
        """
    )

# -----------------------------------------------------------------
# TAB 2. 인구 피라미드
# -----------------------------------------------------------------
with tabs[1]:
    st.subheader(f"🔺 {selected_region}의 인구 피라미드 ({selected_month})")
    st.caption("왼쪽은 남성, 오른쪽은 여성 인구예요. 모양만 봐도 그 지역의 미래가 보여요!")

    male_s = get_age_series(df, selected_region, selected_month, "남")
    female_s = get_age_series(df, selected_region, selected_month, "여")
    labels, male_vals = bin_ages_5y(male_s)
    _, female_vals = bin_ages_5y(female_s)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=labels, x=[-v for v in male_vals], orientation="h",
        name="남성", marker_color=PRIMARY,
        customdata=male_vals, hovertemplate="%{y} 남성: %{customdata:,}명<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        y=labels, x=female_vals, orientation="h",
        name="여성", marker_color=SECONDARY,
        hovertemplate="%{y} 여성: %{x:,}명<extra></extra>",
    ))
    max_v = max(max(male_vals, default=1), max(female_vals, default=1), 1)
    fig.update_layout(
        barmode="relative",
        bargap=0.1,
        xaxis=dict(
            title="인구 수",
            tickvals=[-max_v, -max_v/2, 0, max_v/2, max_v],
            ticktext=[fmt(max_v), fmt(max_v/2), "0", fmt(max_v/2), fmt(max_v)],
        ),
        yaxis=dict(title="연령대", categoryorder="array", categoryarray=labels),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0.5, xanchor="center"),
        height=750,
        margin=dict(l=10, r=10, t=30, b=10),
        plot_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📖 피라미드 모양으로 사회를 읽는 법"):
        st.markdown(
            """
            - **피라미드형 (▲)** : 아래(어린이)가 넓고 위(노인)가 좁음 → 출생율이 높은 **성장형 사회**
            - **종형 (🔔)** : 중간 연령대가 두툼하고 위아래가 비슷 → 출생율이 인구를 유지하는 **정체형 사회**
            - **항아리형 / 방추형** : 아래가 좁고 중간이 넓음 → 저출산이 진행 중인 **감소형 사회**. 지금 대한민국 대부분 지역이 이 모양이에요.
            - **별형** : 생산연령(청장년층) 인구가 특별히 많이 몰려있는 모양 → 주로 대도시나 산업단지가 있는 지역에서 나타나요 (인구 유입형).
            - **표주박형** : 별형의 반대. 청장년층이 빠져나간 지역에서 보여요 (인구 유출형).
            """
        )

# -----------------------------------------------------------------
# TAB 3. 연령별 분포
# -----------------------------------------------------------------
with tabs[2]:
    st.subheader(f"📈 {selected_region}의 한 살 단위 연령별 인구 ({selected_month})")
    show_gender = st.radio("성별 보기", ["계", "남", "여", "남녀 비교"], horizontal=True, key="dist_gender")

    fig2 = go.Figure()
    if show_gender in ("계", "남", "여"):
        s = get_age_series(df, selected_region, selected_month, show_gender)
        color = {"계": ACCENT, "남": PRIMARY, "여": SECONDARY}[show_gender]
        fig2.add_trace(go.Scatter(
            x=list(s.index), y=s.values, mode="lines", fill="tozeroy",
            line=dict(color=color, width=2), name=show_gender,
        ))
    else:
        m = get_age_series(df, selected_region, selected_month, "남")
        f = get_age_series(df, selected_region, selected_month, "여")
        fig2.add_trace(go.Scatter(x=list(m.index), y=m.values, mode="lines", name="남성", line=dict(color=PRIMARY, width=2)))
        fig2.add_trace(go.Scatter(x=list(f.index), y=f.values, mode="lines", name="여성", line=dict(color=SECONDARY, width=2)))

    fig2.update_layout(
        xaxis_title="만 나이", yaxis_title="인구 수",
        height=500, plot_bgcolor="white",
        margin=dict(l=10, r=10, t=30, b=10),
        hovermode="x unified",
    )
    st.plotly_chart(fig2, use_container_width=True)

    total_series = get_age_series(df, selected_region, selected_month, "계")
    peak_age = int(total_series.idxmax())
    st.success(
        f"🔍 **{selected_region}**에서 인구가 가장 많은 단일 연령은 **만 {peak_age}세**"
        f" (약 {fmt(total_series.max())}명)예요. 이 나이대가 태어난 해를 계산해보면 "
        f"어떤 시대의 '베이비붐'이었는지 추리해볼 수 있어요! 🕵️"
    )

# -----------------------------------------------------------------
# TAB 4. 출생율 반등 인사이트 (핵심)
# -----------------------------------------------------------------
with tabs[3]:
    st.subheader("👶 최근 '출생율 반등', 데이터로 직접 확인해볼까요?")

    st.markdown(
        """
        #### 1️⃣ 먼저, 헷갈리기 쉬운 두 개념부터 구분해요

        | 구분 | 이 대시보드의 데이터 (주민등록인구) | 뉴스에 나오는 '합계출산율' |
        |---|---|---|
        | 성격 | **저량(Stock)** — 특정 시점의 '재고' | **유량(Flow)** — 1년 동안의 '흐름' |
        | 의미 | 오늘 이 순간 주민등록상 살아있는 사람 수 | 여성 1명이 평생 낳을 것으로 기대되는 자녀 수 |
        | 발표 기관 | 행정안전부 (매달) | 통계청 (매년) |
        | 이 자료로 알 수 있는 것 | 특정 나이대가 **지금** 몇 명 살아있는지 | 알 수 없음 (직접 발표된 값을 봐야 해요) |

        즉, 이 대시보드의 **'0세 인구'**는 정확한 연간 출생아 수는 아니지만,
        "최근 1년 사이 태어나 지금까지 주민등록이 유지되고 있는 아이의 수"이기 때문에
        **최근 출산 트렌드를 가늠하는 훌륭한 대리 지표(proxy)**가 될 수 있어요. 아래에서 직접 비교해봐요!
        """
    )

    st.markdown("#### 2️⃣ 최근 태어난 코호트(연령 집단) 비교하기")
    cohort_region = st.selectbox(
        "코호트를 확인할 지역", region_choices,
        index=region_choices.index(selected_region) if selected_region in region_choices else 0,
        key="cohort_region",
    )
    s_total = get_age_series(df, cohort_region, selected_month, "계")
    cohort_ages = list(range(0, 10))
    cohort_vals = [int(s_total.loc[a]) for a in cohort_ages]

    colors = [ACCENT if a == 0 else PRIMARY for a in cohort_ages]
    fig3 = go.Figure(go.Bar(
        x=[f"{a}세" for a in cohort_ages], y=cohort_vals,
        marker_color=colors,
        text=[fmt(v) for v in cohort_vals], textposition="outside",
    ))
    fig3.update_layout(
        title=f"{cohort_region}의 0~9세 인구 ({selected_month} 기준)",
        yaxis_title="인구 수", height=450, plot_bgcolor="white",
        margin=dict(l=10, r=10, t=50, b=10),
    )
    st.plotly_chart(fig3, use_container_width=True)

    avg_1_3 = np.mean(cohort_vals[1:4]) if len(cohort_vals) > 3 else np.nan
    zero_val = cohort_vals[0]
    if avg_1_3 and not np.isnan(avg_1_3) and avg_1_3 > 0:
        diff_pct = (zero_val - avg_1_3) / avg_1_3 * 100
        if diff_pct > 0:
            st.success(
                f"📈 **{cohort_region}**의 0세 인구({fmt(zero_val)}명)는 "
                f"1~3세 평균({fmt(avg_1_3)}명)보다 **{diff_pct:.1f}% 많아요.** "
                "이는 최근 출생아 수가 직전 몇 년보다 늘었을 가능성을 보여주는 신호예요! 🎉"
            )
        else:
            st.warning(
                f"📉 **{cohort_region}**의 0세 인구({fmt(zero_val)}명)는 "
                f"1~3세 평균({fmt(avg_1_3)}명)보다 **{abs(diff_pct):.1f}% 적어요.** "
                "지역 특성(전출입 등)에 따라 전국 흐름과 다르게 나타날 수 있어요."
            )

    st.markdown("#### 3️⃣ 실제 전국 통계로 확인하는 '9년 만의 반등'")
    tfr_years = ["2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025(잠정)"]
    tfr_vals = [0.98, 0.92, 0.84, 0.81, 0.78, 0.72, 0.75, 0.80]
    births_vals = [326.9, 302.7, 272.3, 260.6, 249.0, 230.0, 238.3, 254.0]  # 천명 단위(근사)

    fig4 = go.Figure()
    fig4.add_trace(go.Bar(x=tfr_years, y=births_vals, name="출생아 수(천 명, 근사)", marker_color="#B9D2F0", yaxis="y2", opacity=0.7))
    fig4.add_trace(go.Scatter(x=tfr_years, y=tfr_vals, name="합계출산율(명)", mode="lines+markers", line=dict(color=ACCENT, width=3), marker=dict(size=9)))
    fig4.update_layout(
        yaxis=dict(title="합계출산율 (명)"),
        yaxis2=dict(title="출생아 수 (천 명)", overlaying="y", side="right", showgrid=False),
        height=450, plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0.5, xanchor="center"),
        margin=dict(l=10, r=10, t=30, b=10),
    )
    st.plotly_chart(fig4, use_container_width=True)
    st.caption("자료: 통계청 「인구동향조사」(2023년 확정치, 2024·2025년 잠정치). 참고용 근사 수치입니다.")

    st.markdown(
        """
        2023년 합계출산율은 **0.72명**으로 역대 최저를 찍었지만, 2024년 **0.75명**으로
        **9년 만에 반등**했고, 2025년 잠정치는 **0.80명**으로 2년 연속 상승했어요.
        전문가들은 이 반등의 원인으로 ①코로나19로 미뤄졌던 결혼이 다시 늘어난 점,
        ②1990년대 초반(에코붐 세대)에 태어난 인구가 결혼·출산 적령기에 접어든 점을 꼽아요.
        다만 이 반등이 **일시적인 '반짝 효과'**일지, **장기적인 추세 전환**일지는 아직 지켜봐야 해요 — 그래서 통계를
        꾸준히, 비판적으로 살펴보는 태도가 중요합니다. 🧐
        """
    )

    if len(months) > 1:
        st.markdown("#### 4️⃣ 이 파일에 담긴 여러 달의 0세 인구 추세")
        trend = []
        for month in months:
            s = get_age_series(df, cohort_region, month, "계")
            trend.append({"월": month, "0세 인구": int(s.loc[0])})
        trend_df = pd.DataFrame(trend)
        fig5 = px.line(trend_df, x="월", y="0세 인구", markers=True)
        fig5.update_traces(line_color=GREEN)
        fig5.update_layout(height=400, plot_bgcolor="white", margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig5, use_container_width=True)
    else:
        st.info(
            "ℹ️ 지금 불러온 파일에는 **1개월치** 데이터만 있어서 실제 시계열 추세는 볼 수 없어요. "
            "행안부 사이트에서 **여러 달을 한 번에** 내려받아 업로드하면, 0세 인구의 월별 변화를 실제 그래프로 볼 수 있어요!"
        )

# -----------------------------------------------------------------
# TAB 5. 지역 비교
# -----------------------------------------------------------------
with tabs[4]:
    st.subheader("⚖️ 여러 지역, 한눈에 비교하기")
    if len(compare_regions) < 2:
        st.warning("사이드바에서 비교할 지역을 2개 이상 선택해주세요. 👈")
    else:
        metric = st.selectbox(
            "비교할 지표",
            ["총인구", "고령화지수", "노년부양비", "유소년부양비"],
            key="compare_metric",
        )
        rows = []
        for reg in compare_regions:
            if reg == NATION_LABEL:
                nat = summary_all[(summary_all["월"] == selected_month) & (summary_all["레벨"] == "시도")]
                total = nat["총인구"].sum(); young = nat["유소년인구"].sum()
                working = nat["생산연령인구"].sum(); old = nat["고령인구"].sum()
                rows.append({
                    "지역": reg, "총인구": total,
                    "고령화지수": old/young*100 if young else np.nan,
                    "노년부양비": old/working*100 if working else np.nan,
                    "유소년부양비": young/working*100 if working else np.nan,
                })
            else:
                r = summary_all[(summary_all["월"] == selected_month) & (summary_all["지역명"] == reg)]
                if not r.empty:
                    r = r.iloc[0]
                    rows.append({
                        "지역": reg, "총인구": r["총인구"], "고령화지수": r["고령화지수"],
                        "노년부양비": r["노년부양비"], "유소년부양비": r["유소년부양비"],
                    })
        comp_df = pd.DataFrame(rows).sort_values(metric, ascending=False)

        fig6 = px.bar(
            comp_df, x="지역", y=metric, color="지역",
            text=comp_df[metric].map(lambda v: fmt1(v) if metric != "총인구" else fmt(v)),
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig6.update_traces(textposition="outside")
        fig6.update_layout(showlegend=False, height=480, plot_bgcolor="white", margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig6, use_container_width=True)

        st.dataframe(
            comp_df.set_index("지역").style.format({
                "총인구": "{:,.0f}", "고령화지수": "{:,.1f}",
                "노년부양비": "{:,.1f}", "유소년부양비": "{:,.1f}",
            }),
            use_container_width=True,
        )

        st.markdown("##### 🔺 지역별 인구 피라미드 겹쳐보기 (연령대별 총인구 비중 %)")
        fig7 = go.Figure()
        palette = px.colors.qualitative.Set2
        for i, reg in enumerate(compare_regions):
            s = get_age_series(df, reg, selected_month, "계")
            labels, vals = bin_ages_5y(s)
            total = sum(vals) or 1
            pct = [v/total*100 for v in vals]
            fig7.add_trace(go.Scatter(x=labels, y=pct, mode="lines+markers", name=reg, line=dict(color=palette[i % len(palette)])))
        fig7.update_layout(
            xaxis_title="연령대", yaxis_title="해당 지역 내 비중 (%)",
            height=480, plot_bgcolor="white", margin=dict(l=10, r=10, t=30, b=10),
            hovermode="x unified",
        )
        st.plotly_chart(fig7, use_container_width=True)

# -----------------------------------------------------------------
# TAB 6. 용어 사전
# -----------------------------------------------------------------
with tabs[5]:
    st.subheader("📚 인구 데이터 용어 사전")
    with st.expander("👶 합계출산율 (TFR) vs 출생아 수", expanded=True):
        st.markdown(
            """
            - **합계출산율**: 여성 한 명이 가임기간(15~49세) 동안 낳을 것으로 기대되는 평균 자녀 수. '비율' 지표라 인구 규모와 무관하게 비교 가능해요.
            - **출생아 수**: 실제로 한 해 동안 태어난 아기의 총 숫자. 인구 규모가 큰 지역일수록 커지는 '절대값' 지표예요.
            - 두 지표는 같이 움직일 때도, 다르게 움직일 때도 있어요. 가임기 여성 인구 자체가 줄면 출산율이 같아도 출생아 수는 줄 수 있거든요!
            """
        )
    with st.expander("📐 고령화지수 / 부양비"):
        st.markdown(
            """
            - **고령화지수** = 고령인구(65세+) ÷ 유소년인구(0~14세) × 100. 100을 넘으면 노인이 어린이보다 많다는 뜻이에요.
            - **노년부양비** = 고령인구 ÷ 생산연령인구(15~64세) × 100. 일하는 사람 100명이 부양해야 하는 고령자 수예요.
            - **유소년부양비** = 유소년인구 ÷ 생산연령인구 × 100.
            - **총부양비** = 노년부양비 + 유소년부양비. 숫자가 클수록 생산연령인구의 부담이 크다는 뜻이에요.
            """
        )
    with st.expander("🔺 인구 피라미드 읽는 법"):
        st.markdown(
            """
            인구 피라미드는 가로축에 인구 수(왼쪽 남성, 오른쪽 여성), 세로축에 연령을 나타낸 그래프예요.
            모양이 삼각형에 가까울수록 젊은 사회, 항아리·표주박 모양일수록 고령화가 진행된 사회예요.
            가운데가 볼록 튀어나온 부분이 있다면, 그 나이대가 태어났을 때 '베이비붐'이 있었다는 뜻이랍니다.
            """
        )
    with st.expander("🗂️ 이 데이터는 어떻게 만들어졌나요? (Stock vs Flow)"):
        st.markdown(
            """
            행정안전부의 '주민등록 연앙(월간)인구'는 매달 말일 기준으로 등록된 주민 수를 센 **저량(Stock)** 데이터예요.
            반면 통계청이 발표하는 출생·사망 통계는 특정 기간 동안 발생한 사건 수를 세는 **유량(Flow)** 데이터죠.
            두 통계를 함께 볼 줄 알면, 뉴스에서 나오는 인구 관련 숫자를 훨씬 더 정확하게 이해할 수 있어요! 💪
            """
        )

st.markdown("---")
st.caption(
    "📊 데이터 출처: 행정안전부 «연령별 인구현황(월간)» · 합계출산율 참고: 통계청 인구동향조사 (근사치) · "
    "본 대시보드는 교육 목적으로 제작되었습니다."
)
