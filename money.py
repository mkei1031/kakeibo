import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --- ページ設定 ---
st.set_page_config(page_title="家計簿ダッシュボード", layout="wide")
st.title("📊 家計簿マネージャー")

# --- 1. データ読み込み ---
@st.cache_data(ttl=30)
def load_data():
    base_url = "https://docs.google.com/spreadsheets/d/1nJ9cPEJT6fBLd2KRAxhGv-zGz6WdFCS1416_QtMw62Y/gviz/tq?tqx=out:csv"
    df_logs = pd.read_csv(f"{base_url}&gid=1775858850")
    df_budget = pd.read_csv(f"{base_url}&gid=1402210043")
    
    df_logs.columns = df_logs.columns.str.strip()
    df_budget.columns = df_budget.columns.str.strip()
    
    df_logs['日付'] = pd.to_datetime(df_logs['日付'])
    df_logs['年月'] = df_logs['日付'].dt.strftime('%Y-%m')
    df_budget['年月'] = pd.to_datetime(df_budget['年月']).dt.strftime('%Y-%m')
    
    for df in [df_logs, df_budget]:
        if '金額' in df.columns:
            df['金額'] = pd.to_numeric(df['金額'].astype(str).replace(r'[¥,]', '', regex=True), errors='coerce').fillna(0)
    return df_logs, df_budget

df_logs, df_budget = load_data()

# --- 2. フィルタリング ---
available_months = sorted(df_logs['年月'].unique(), reverse=True)
selected_month = st.sidebar.selectbox("表示月を選択", available_months)

month_logs = df_logs[(df_logs['年月'] == selected_month)]
month_budget = df_budget[df_budget['年月'] == selected_month]

total_income = month_logs[month_logs['収支'] == '収入']['金額'].sum()
total_spent = month_logs[month_logs['収支'] == '支出']['金額'].sum()
total_budget = month_budget['金額'].sum()
balance = total_budget - total_spent

# --- 3. 最上段：収支サマリー ---
st.subheader(f"💰 {selected_month} の収支状況")
col1, col2, col3, col4 = st.columns(4)
spent_pct = (total_spent / total_budget * 100) if total_budget > 0 else 0

with col1:
    st.metric("今月の総予算", f"¥{total_budget:,.0f}")
with col2:
    st.metric("現在の総支出", f"¥{total_spent:,.0f}", delta=f"{spent_pct:.1f}% 消化", delta_color="inverse")
with col3:
    st.metric("予算残金", f"¥{balance:,.0f}", delta=f"残り ¥{balance:,.0f}", delta_color="normal")
with col4:
    st.metric("収入", f"¥{total_income:,.0f}")

st.divider()

# --- 4. 項目別：予算消化状況（進捗バー形式） ---
st.subheader("⚠️ 項目別・予算との差額チェック")
summary = pd.merge(
    month_budget.groupby('項目')['金額'].sum().reset_index(),
    month_logs[month_logs['収支']=='支出'].groupby('項目')['金額'].sum().reset_index(),
    on='項目', how='outer', suffixes=('_予算', '_実績')
).fillna(0)

summary['差額'] = summary['金額_予算'] - summary['金額_実績']
summary = summary.sort_values('差額', ascending=True)

def make_label(row):
    spent, diff = int(row['金額_実績']), int(row['差額'])
    return f"¥{spent:,} (¥{abs(diff):,} オーバー!!)" if diff < 0 else f"¥{spent:,} (残り ¥{diff:,})"

summary['表示テキスト'] = summary.apply(make_label, axis=1)

fig_progress = go.Figure()
fig_progress.add_trace(go.Bar(
    y=summary['項目'], x=summary['金額_予算'], orientation='h',
    marker=dict(color='rgba(200, 200, 200, 0.3)', line=dict(color='lightgrey', width=1)),
    showlegend=False, hoverinfo='none'
))
bar_colors = summary['差額'].apply(lambda x: '#EF553B' if x < 0 else '#636EFA').tolist()
fig_progress.add_trace(go.Bar(
    y=summary['項目'], x=summary['金額_実績'], orientation='h',
    marker_color=bar_colors, text=summary['表示テキスト'], textposition='auto',
    insidetextanchor='end', textfont=dict(color='white', size=12)
))
fig_progress.update_layout(barmode='overlay', height=max(300, len(summary)*50), margin=dict(l=20, r=50, t=20, b=20), xaxis=dict(range=[0, max(summary['金額_予算'].max(), summary['金額_実績'].max()) * 1.3]))
st.plotly_chart(fig_progress, use_container_width=True)

st.write("各項目ごとの出費と予算",summary)
# --- 5. 【復活！】月次収支推移（棒グラフ） ---
st.divider()
st.subheader("📈 月次収支推移（収入 vs 支出）")

monthly_summary = df_logs.groupby(['年月', '収支'])['金額'].sum().unstack().fillna(0)

fig_trend = go.Figure()
if '収入' in monthly_summary.columns:
    fig_trend.add_trace(go.Bar(x=monthly_summary.index, y=monthly_summary['収入'], name='収入', marker_color='#00CC96'))
if '支出' in monthly_summary.columns:
    fig_trend.add_trace(go.Bar(x=monthly_summary.index, y=monthly_summary['支出'], name='支出', marker_color='#EF553B'))

fig_trend.update_layout(barmode='group', height=400, xaxis_title="年月", yaxis_title="金額（円）", hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
st.plotly_chart(fig_trend, use_container_width=True)

# --- 6. 今月の利用明細（日付の昇順） ---
st.divider()
st.subheader(f"📝 {selected_month} の利用明細")
display_logs = month_logs.copy().sort_values('日付', ascending=True)
display_logs['日付'] = display_logs['日付'].dt.strftime('%Y/%m/%d')
cols = ['日付', '項目', '内容', '金額', '収支']
actual_cols = [c for c in cols if c in display_logs.columns]
st.dataframe(display_logs[actual_cols], use_container_width=True, hide_index=True)