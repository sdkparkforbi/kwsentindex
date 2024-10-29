import streamlit as st
import pandas as pd
import pymysql
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import os
import sqlalchemy
from matplotlib.gridspec import GridSpec

# GitHub 저장소에 업로드된 폰트 파일 경로 설정
font_path = os.path.join(os.path.dirname(__file__), 'NanumGothic.ttf')
# font_path = "C:/Windows/Fonts/NanumGothic.ttf"
fontprop = fm.FontProperties(fname=font_path, size=10)
plt.rcParams['font.family'] = fontprop.get_name()

# 데이터베이스 연결 정보
db_host = '59.9.20.28'
db_user = 'user1'
db_password = 'user1!!'
db_database = 'cuif'
charset = 'utf8'

# Streamlit 설정
st.title("키워드 기반 감성 지수 분석")
st.write("기사 데이터를 사용하여 감성 지수 및 이동 평균을 시각화합니다.")

# 사용자 입력 키워드 및 도시 선택
keyword = st.text_input("분석할 키워드를 입력하세요:", value="미군")
cities = ['가평', '구리', '고양', '남양주', '동두천', '양주', '연천', '의정부', '파주', '포천']
target_city = st.selectbox("분석할 도시를 선택하세요:", cities, index=cities.index('동두천'))

# SQLAlchemy 엔진 생성
engine = sqlalchemy.create_engine(f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_database}?charset={charset}")

# 필요한 열과 특정 조건을 쿼리문에 추가
query = """
SELECT date, sentiment, content, cname 
FROM cuif.country_news_sentiment_tot
WHERE sentiment != '0' 
  AND cname = %(city)s 
  AND date >= '2020-01-01'
"""
sent_data = pd.read_sql(query, engine, params={"city": target_city})

# 특정 단어가 포함된 기사 필터링
sent_data1 = sent_data.copy()

# 특정 단어가 포함된 기사 필터링 후 복사본 생성
filtered_data = sent_data1[sent_data1['content'].str.contains(keyword, na=False)].copy()

# 날짜 열을 datetime 형식으로 변환 후 년-월 기준으로 그룹화
filtered_data['date'] = pd.to_datetime(filtered_data['date'], errors='coerce')
filtered_data['year_month'] = filtered_data['date'].dt.to_period('M')

# 기간별, sentiment별 카운트 집계
sentiment_trend = filtered_data.groupby(['year_month', 'sentiment']).size().unstack(fill_value=0)

# 모든 가능한 year_month와 sentiment 조합을 만듭니다.
all_year_months = pd.period_range(sent_data['date'].min(), sent_data['date'].max(), freq='M')
all_sentiments = ['-1', '1']

# MultiIndex 생성 및 누락된 값을 NA로 유지
all_index = pd.MultiIndex.from_product([all_year_months, all_sentiments], names=['year_month', 'sentiment'])
sentiment_trend = sentiment_trend.stack().reindex(all_index).unstack(fill_value=0)

# 'index' 열 생성: 비율 계산
sentiment_trend['index'] = None
sentiment_trend.loc[(sentiment_trend['1'] > 0) & (sentiment_trend['-1'] == 0), 'index'] = 1
sentiment_trend.loc[(sentiment_trend['-1'] > 0) & (sentiment_trend['1'] == 0), 'index'] = 0
sentiment_trend.loc[(sentiment_trend['1'] > 0) & (sentiment_trend['-1'] > 0), 'index'] = (
    sentiment_trend['1'] / (sentiment_trend['1'] + sentiment_trend['-1'])
)

# 결측값 채우기
sentiment_trend['index'] = sentiment_trend['index'].fillna(method='ffill').fillna(method='bfill')

# 6개월 이동평균 계산
sentiment_trend1 = sentiment_trend.reset_index()
sentiment_trend1['year_month'] = sentiment_trend1['year_month'].dt.to_timestamp()
sentiment_trend1['6개월 이동평균'] = sentiment_trend1['index'].rolling(window=6).mean()

# 월별 빈도수 계산
monthly_counts = filtered_data['year_month'].value_counts().sort_index()

# 그래프 그리기 (GridSpec을 사용하여 서브플롯 배치)
fig = plt.figure(figsize=(12, 8))
gs = GridSpec(2, 1, height_ratios=[3, 1])  # 3:1 비율로 위쪽과 아래쪽 구분

# 감성 지수와 이동 평균을 상단 플롯에 그림
ax1 = fig.add_subplot(gs[0])
ax1.plot(sentiment_trend1['year_month'], sentiment_trend1['index'], marker='o', color='g', label='감성지수')
ax1.plot(sentiment_trend1['year_month'], sentiment_trend1['6개월 이동평균'], color='blue', linestyle='-', linewidth=2,
         label='6개월 이동평균')
plt.axhline(y=0.5, color='r', linestyle='--')
plt.xlabel('연월', fontproperties=fontprop)
plt.ylabel('감성지수', fontproperties=fontprop)
plt.title(f"감성지수: '{keyword}'", fontproperties=fontprop)
plt.legend(prop=fontprop)
plt.grid(True)

# 월별 빈도수를 하단 플롯에 막대그래프로 그림
ax2 = fig.add_subplot(gs[1], sharex=ax1)
ax2.bar(monthly_counts.index.to_timestamp(), monthly_counts.values, color='darkgray', alpha=0.8, width=20, align='center')
ax2.set_ylabel('기사수', fontproperties=fontprop)
ax2.set_xlabel('연월', fontproperties=fontprop)
ax2.set_ylim(0, max(monthly_counts.values) * 1.2)  # 여백 조정
ax2.grid(True)

# Streamlit에 그래프 표시
st.pyplot(fig)
