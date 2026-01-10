import streamlit as st
import pandas as pd
import json
import os
import sys
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import subprocess

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config_loader import load_config

# --- Configuration & Setup ---
st.set_page_config(page_title="YouTube Vibes Tracker", layout="wide")
config = load_config()

# Load Clusters
@st.cache_data
def get_clusters():
    with open(config.paths.cluster_config, 'r') as f:
        return json.load(f)

clusters = get_clusters()

# --- Sidebar ---
st.sidebar.title("YouTube Vibes Tracker")
mode = st.sidebar.radio("Select Mode", ["Daily Report", "Long-Term Analysis", "Data Explorer"])

# --- Helper Functions ---
def run_command(command_list):
    """Run a shell command and stream output."""
    process = subprocess.Popen(
        command_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return process

# --- Daily Report Page ---
if mode == "Daily Report":
    st.header("📅 Daily Vibes Report")
    
    col1, col2 = st.columns(2)
    with col1:
        target_date = st.date_input("Select Date", datetime.now().date())
    
    if st.button("Generate Daily Report"):
        with st.spinner(f"Generating report for {target_date}..."):
            # Run the daily_report.py script
            cmd = [sys.executable, "src/daily_report.py", "--date", str(target_date)]
            process = run_command(cmd)
            
            # Show logs
            log_container = st.empty()
            full_log = ""
            for line in process.stdout:
                full_log += line
                log_container.code(full_log[-2000:]) # Show last 2000 chars
            
            process.wait()
            
            if process.returncode == 0:
                st.success("Report Generated Successfully!")
                
                # Display Results
                report_dir = f"data/reports/{target_date}"
                if os.path.exists(report_dir):
                    st.subheader("Word Clouds")
                    
                    # Display images in a grid
                    img_cols = st.columns(2)
                    images = [f for f in os.listdir(report_dir) if f.endswith(".png")]
                    
                    for i, img_file in enumerate(images):
                        with img_cols[i % 2]:
                            st.image(f"{report_dir}/{img_file}", caption=img_file)
                else:
                    st.error("Report directory not found. Check logs.")
            else:
                st.error("Report generation failed.")
                st.error(process.stderr.read())

# --- Long-Term Analysis Page ---
elif mode == "Long-Term Analysis":
    st.header("📈 Long-Term Trend Analysis")
    
    analysis_type = st.selectbox("Analysis Type", ["Single Channel History", "Cluster Comparison"])
    
    if analysis_type == "Single Channel History":
        selected_cluster = st.selectbox("Select Cluster", list(clusters.keys()))
        selected_channel = st.selectbox("Select Channel", clusters[selected_cluster])
        
        col1, col2 = st.columns(2)
        with col1:
            start_year = st.number_input("Start Year", min_value=2015, max_value=2030, value=2024)
        with col2:
            end_year = st.number_input("End Year", min_value=2015, max_value=2030, value=2024)
            
        if st.button("Collect Historical Transcripts"):
            st.info(f"Starting collection for {selected_channel} ({start_year}-{end_year})...")
            
            cmd = [
                sys.executable, "scripts/collect_historical_data.py",
                "--channel", selected_channel,
                "--start-year", str(start_year),
                "--end-year", str(end_year)
            ]
            
            process = run_command(cmd)
            
            # Show logs
            log_container = st.empty()
            full_log = ""
            for line in process.stdout:
                full_log += line
                log_container.code(full_log[-2000:])
                
            process.wait()
            if process.returncode == 0:
                st.success("Collection Complete!")
                st.write(f"Data saved to `data/historical/{selected_channel}/`")
            else:
                st.error("Collection Failed")

# --- Data Explorer Page ---
elif mode == "Data Explorer":
    st.header("🔍 Data Explorer")
    
    # Load main dataset
    if os.path.exists(config.paths.analyzed_data):
        df = pd.read_csv(config.paths.analyzed_data)
        
        # Filters
        selected_clusters = st.multiselect("Filter by Cluster", df['cluster'].unique(), default=df['cluster'].unique())
        df_filtered = df[df['cluster'].isin(selected_clusters)]
        
        st.metric("Total Videos", len(df_filtered))
        
        st.dataframe(df_filtered[['publish_date', 'cluster', 'channel_name', 'title', 'sentiment', 'themes']].sort_values('publish_date', ascending=False))
        
        # Simple visualization
        st.subheader("Sentiment Distribution")
        sentiment_counts = df_filtered['sentiment'].value_counts()
        st.bar_chart(sentiment_counts)
        
    else:
        st.warning("No analyzed data found. Run the pipeline first.")
