import streamlit as st
import pandas as pd
import json
import os
import sys
from datetime import datetime, timedelta
import altair as alt
import subprocess
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config_loader import load_config

# --- Configuration & Setup ---
st.set_page_config(
    page_title="YouTube Vibes Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for a more professional look
st.markdown("""
<style>
    .reportview-container {
        margin-top: -2em;
    }
    .stDeployButton {display:none;}
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

config = load_config()

# --- Data Loading ---
@st.cache_data
def get_clusters():
    with open(config.paths.cluster_config, 'r') as f:
        return json.load(f)

@st.cache_data
def load_main_data():
    if os.path.exists(config.paths.cluster_data):
        df = pd.read_csv(config.paths.cluster_data)
        df['publish_date'] = pd.to_datetime(df['publish_date'])
        return df
    return pd.DataFrame()

@st.cache_data
def load_analyzed_data():
    if os.path.exists(config.paths.analyzed_data):
        df = pd.read_csv(config.paths.analyzed_data)
        df['publish_date'] = pd.to_datetime(df['publish_date'])
        return df
    return pd.DataFrame()

clusters = get_clusters()
df_main = load_main_data()
df_analyzed = load_analyzed_data()

# --- Sidebar ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/e/ef/Youtube_logo.png", width=100)
st.sidebar.title("Vibes Tracker")
mode = st.sidebar.radio(
    "Navigation", 
    ["Dashboard", "Daily Reports", "Data Explorer", "Historical Collection"]
)

st.sidebar.markdown("---")
st.sidebar.caption(f"📅 Today: {datetime.now().strftime('%Y-%m-%d')}")
st.sidebar.caption(f"💾 Total Videos: {len(df_main):,}")

# --- Helper Functions ---
def run_command(command_list):
    """Run a shell command and stream output."""
    return subprocess.Popen(
        command_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

# ==========================================
# 🏠 DASHBOARD
# ==========================================
if mode == "Dashboard":
    st.title("📊 Narrative Ecosystem Dashboard")
    st.markdown("Overview of tracked channels and recent activity.")

    # Top Stats
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Videos Tracked", f"{len(df_main):,}")
    with c2:
        st.metric("Analyzed Transcripts", f"{len(df_analyzed):,}")
    with c3:
        st.metric("Active Clusters", len(clusters))
    with c4:
        recent_count = len(df_main[df_main['publish_date'] > (datetime.now() - timedelta(days=7))])
        st.metric("Videos (Last 7 Days)", f"{recent_count:,}")

    # Cluster Breakdown
    st.subheader("Cluster Composition")
    
    cluster_counts = {k: len(v) for k, v in clusters.items()}
    df_clusters = pd.DataFrame(list(cluster_counts.items()), columns=['Cluster', 'Channel Count'])
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        chart = alt.Chart(df_clusters).mark_bar().encode(
            x='Channel Count',
            y=alt.Y('Cluster', sort='-x'),
            color=alt.Color('Cluster', scale=alt.Scale(scheme='tableau10'))
        ).properties(height=300)
        st.altair_chart(chart, use_container_width=True)
    
    with col2:
        st.write("### Tracked Channels")
        selected_view_cluster = st.selectbox("View Channels in:", list(clusters.keys()))
        st.write(f"**{selected_view_cluster}** ({len(clusters[selected_view_cluster])} channels)")
        st.code("\n".join(clusters[selected_view_cluster]), language="text")

# ==========================================
# 📅 DAILY REPORTS
# ==========================================
elif mode == "Daily Reports":
    st.title("📅 Daily Vibes Report")
    
    tab1, tab2 = st.tabs(["Generate New Report", "View Past Reports"])
    
    with tab1:
        st.markdown("Run the daily ingestion and analysis pipeline for a specific date.")
        
        c1, c2 = st.columns([1, 3])
        with c1:
            target_date = st.date_input("Target Date", datetime.now().date())
            run_btn = st.button("🚀 Generate Report", type="primary")
        
        if run_btn:
            with st.status(f"Generating report for {target_date}...", expanded=True) as status:
                st.write("Initializing pipeline...")
                cmd = [sys.executable, "src/daily_report.py", "--date", str(target_date)]
                process = run_command(cmd)
                
                log_box = st.empty()
                full_log = ""
                
                for line in process.stdout:
                    full_log += line
                    # Update log every few lines to avoid UI lag
                    if len(full_log) % 500 < 100: 
                        log_box.code(full_log[-1500:], language="bash")
                
                process.wait()
                
                if process.returncode == 0:
                    status.update(label="✅ Report Complete!", state="complete", expanded=False)
                    st.success(f"Report generated for {target_date}")
                    st.balloons()
                else:
                    status.update(label="❌ Report Failed", state="error", expanded=True)
                    st.error(process.stderr.read())

    with tab2:
        st.markdown("Browse previously generated reports.")
        
        reports_root = Path("data/reports")
        if reports_root.exists():
            available_dates = sorted([d.name for d in reports_root.iterdir() if d.is_dir()], reverse=True)
            
            if available_dates:
                selected_report_date = st.selectbox("Select Report Date", available_dates)
                report_path = reports_root / selected_report_date
                
                # Load images
                images = list(report_path.glob("*.png"))
                
                if images:
                    st.subheader(f"Visualizations for {selected_report_date}")
                    
                    # Group images
                    wordclouds = [img for img in images if "cloud" in img.name or "sig" in img.name]
                    charts = [img for img in images if img not in wordclouds]
                    
                    st.markdown("### ☁️ Word Clouds")
                    cols = st.columns(2)
                    for i, img in enumerate(wordclouds):
                        with cols[i % 2]:
                            st.image(str(img), caption=img.name, use_column_width=True)
                            
                    if charts:
                        st.markdown("### 📈 Charts & Stats")
                        cols = st.columns(2)
                        for i, img in enumerate(charts):
                            with cols[i % 2]:
                                st.image(str(img), caption=img.name, use_column_width=True)
                else:
                    st.info("No images found in this report folder.")
            else:
                st.info("No reports found.")
        else:
            st.error("Reports directory not found.")

# ==========================================
# 🔍 DATA EXPLORER
# ==========================================
elif mode == "Data Explorer":
    st.title("🔍 Data Explorer")
    
    if not df_analyzed.empty:
        # Filters
        c1, c2, c3 = st.columns(3)
        with c1:
            selected_clusters = st.multiselect("Filter by Cluster", df_analyzed['cluster'].unique(), default=df_analyzed['cluster'].unique())
        with c2:
            search_term = st.text_input("Search Titles", "")
        with c3:
            sentiment_filter = st.multiselect("Filter Sentiment", df_analyzed['sentiment'].dropna().unique())

        # Apply Filters
        df_filtered = df_analyzed[df_analyzed['cluster'].isin(selected_clusters)]
        if search_term:
            df_filtered = df_filtered[df_filtered['title'].str.contains(search_term, case=False, na=False)]
        if sentiment_filter:
            df_filtered = df_filtered[df_filtered['sentiment'].isin(sentiment_filter)]

        st.markdown(f"**Showing {len(df_filtered):,} videos**")
        
        # Timeline Chart
        st.subheader("Upload Frequency Over Time")
        chart_data = df_filtered.groupby([pd.Grouper(key='publish_date', freq='D'), 'cluster']).size().reset_index(name='count')
        
        timeline = alt.Chart(chart_data).mark_line(point=True).encode(
            x='publish_date',
            y='count',
            color='cluster',
            tooltip=['publish_date', 'cluster', 'count']
        ).properties(height=300).interactive()
        
        st.altair_chart(timeline, use_container_width=True)

        # Data Table
        st.subheader("Video Data")
        st.dataframe(
            df_filtered[['publish_date', 'cluster', 'channel_name', 'title', 'sentiment', 'themes']] \
            .sort_values('publish_date', ascending=False),
            use_container_width=True,
            height=400
        )
    else:
        st.info("No analyzed data available. Run the analysis pipeline first.")

# ==========================================
# 🕰️ HISTORICAL COLLECTION
# ==========================================
elif mode == "Historical Collection":
    st.title("🕰️ Historical Data Collection")
    st.markdown("""
    Collect deep history for specific channels. This bypasses the daily limit by focusing on one channel at a time.
    **Note:** This process can take a long time due to rate limiting.
    """, unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    
    with c1:
        selected_cluster = st.selectbox("1. Select Cluster", list(clusters.keys()))
        selected_channel = st.selectbox("2. Select Channel", clusters[selected_cluster])
    
    with c2:
        start_year = st.number_input("Start Year", 2015, 2025, 2024)
        end_year = st.number_input("End Year", 2015, 2026, 2024)
        
    if st.button("Start Collection", type="primary"):
        st.info(f"Initiating collection for **{selected_channel}** ({start_year}-{end_year})...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        log_expander = st.expander("View Live Logs", expanded=True)
        
        cmd = [
            sys.executable, "scripts/collect_historical_data.py",
            "--channel", selected_channel,
            "--start-year", str(start_year),
            "--end-year", str(end_year)
        ]
        
        process = run_command(cmd)
        
        with log_expander:
            log_box = st.empty()
            full_log = ""
            
            for line in process.stdout:
                full_log += line
                if len(full_log) % 1000 < 200:
                    log_box.code(full_log[-2000:])
                
                # Simple progress heuristic
                if "Downloading" in line and "%" in line:
                    status_text.text(line.strip())

        process.wait()
        
        if process.returncode == 0:
            st.success("Collection Complete!")
            st.markdown(f"📂 Data saved to `data/historical/{selected_channel}/`")
        else:
            st.error("Collection Failed. Check logs above.")