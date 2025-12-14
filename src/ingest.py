import os
import json
import pandas as pd
from googleapiclient.discovery import build
from dotenv import load_dotenv

# --- Helper Functions ---

def get_channel_id(youtube, handle):
    """Converts a YouTube handle (e.g., '@MrBeast') to a Channel ID using the Search API."""
    try:
        request = youtube.search().list(
            part="snippet",
            type="channel",
            q=handle,
            maxResults=1
        )
        response = request.execute()
        if response.get('items'):
            return response['items'][0]['snippet']['channelId']
        return None
    except Exception as e:
        print(f"     ⚠️ Error resolving handle {handle}: {e}")
        return None

def get_recent_videos(youtube, channel_id, channel_name, limit=10):
    """Fetches the most recent X videos from a specific channel ID."""
    videos = []
    
    try:
        # 1. Get the 'Uploads' Playlist ID for the channel
        res = youtube.channels().list(id=channel_id, part='contentDetails').execute()
        playlist_id = res['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        
        # 2. Get videos from that playlist
        res = youtube.playlistItems().list(
            playlistId=playlist_id,
            part='snippet',
            maxResults=limit
        ).execute()
        
        for item in res['items']:
            # Skip if video title is "Private" or "Deleted"
            if item['snippet']['title'] in ["Private video", "Deleted video"]:
                continue

            videos.append({
                "video_id": item['snippet']['resourceId']['videoId'],
                "title": item['snippet']['title'],
                "publish_date": item['snippet']['publishedAt'],
                "channel_name": channel_name,
                "url": f"https://www.youtube.com/watch?v={item['snippet']['resourceId']['videoId']}"
            })
        return videos
    
    except Exception as e:
        print(f"     ❌ Error fetching videos for {channel_name} (ID: {channel_id}): {e}")
        return []

# --- Main Ingestion Logic ---

def ingest_clusters(clusters_config, api_key):
    """
    Processes a dictionary of clusters, fetches video metadata for each channel,
    and returns a combined DataFrame.
    """
    if not api_key:
        print("Error: YOUTUBE_API_KEY not found. Please check your .env file.")
        return pd.DataFrame()

    # Initialize the YouTube API client
    youtube = build('youtube', 'v3', developerKey=api_key)
    all_videos = []

    print(f"🚀 Starting Ingestion for {len(clusters_config)} clusters...")

    for cluster_name, handles in clusters_config.items():
        print(f"\n📂 Processing Cluster: {cluster_name}")
        
        for handle in handles:
            print(f"  -> Fetching data for: {handle}")
            
            # 1. Resolve Handle to ID
            cid = get_channel_id(youtube, handle)
            if not cid:
                continue
            
            # 2. Fetch Videos (limit set to 15 per channel for a good initial sample)
            videos = get_recent_videos(youtube, cid, handle, limit=15)
            
            # 3. Tag with Cluster Name and append
            for v in videos:
                v['cluster'] = cluster_name
                all_videos.append(v)
                    
    # Convert list of dictionaries to a DataFrame
    df = pd.DataFrame(all_videos)
    return df

# --- Execution Block ---

if __name__ == "__main__":
    # Load environment variables from the .env file
    load_dotenv(dotenv_path="../.env")
    API_KEY = os.getenv("YOUTUBE_API_KEY")
    
    # 1. Load the cluster data from the config file (relative path from src/)
    config_path = "config/clusters.json"
    try:
        with open(config_path, 'r') as f:
            my_clusters = json.load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file not found at {config_path}. Did you create it?")
        exit()
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in {config_path}.")
        exit()
    
    # 2. Run the ingestion process
    df = ingest_clusters(my_clusters, API_KEY)
    
    # 3. Save the results
    if not df.empty:
        output_path = "../data/cluster_data.csv"
        # Ensure the data directory exists before saving
        os.makedirs(os.path.dirname(output_path), exist_ok=True) 
        
        df.to_csv(output_path, index=False)
        print(f"\n✅ Success! Saved {len(df)} videos to {output_path}")
        print("\n--- Sample Output ---")
        print(df[['cluster', 'channel_name', 'title', 'publish_date']].head())
    else:
        print("\n⚠️ Ingestion complete, but no data was found. Check API key and channel handles.")