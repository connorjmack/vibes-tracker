import os
import json
import pandas as pd
from googleapiclient.discovery import build
from dotenv import load_dotenv

# --- Configuration ---
CHANNEL_ID_CACHE = "../data/channel_ids.json"

# --- Helper Functions ---

def load_channel_id_cache():
    """Loads the stored Channel ID cache from the data directory."""
    if os.path.exists(CHANNEL_ID_CACHE):
        with open(CHANNEL_ID_CACHE, 'r') as f:
            return json.load(f)
    return {}

def save_channel_id_cache(cache):
    """Saves the updated Channel ID cache to the data directory."""
    os.makedirs(os.path.dirname(CHANNEL_ID_CACHE), exist_ok=True)
    with open(CHANNEL_ID_CACHE, 'w') as f:
        json.dump(cache, f, indent=4)

def resolve_channel_id(youtube, handle, cache):
    """Checks cache first, then resolves handle to Channel ID using search API (100 units)."""
    if handle in cache:
        return cache[handle]

    print(f"     [CACHE MISS] Resolving handle {handle} (100 units)...")
    try:
        request = youtube.search().list(
            part="snippet",
            type="channel",
            q=handle,
            maxResults=1
        )
        response = request.execute()
        if response.get('items'):
            cid = response['items'][0]['snippet']['channelId']
            cache[handle] = cid  # Update cache
            return cid
        return None
    except Exception as e:
        print(f"     ⚠️ Error resolving handle {handle}: {e}")
        return None

def get_recent_videos(youtube, channel_id, channel_name, limit=30):
    """Fetches the most recent X videos from a specific channel ID."""
    videos = []
    
    try:
        # 1. Get the 'Uploads' Playlist ID (1 unit)
        res = youtube.channels().list(id=channel_id, part='contentDetails').execute()
        playlist_id = res['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        
        # 2. Get videos from that playlist (1 unit, up to 50 results)
        res = youtube.playlistItems().list(
            playlistId=playlist_id,
            part='snippet',
            maxResults=limit
        ).execute()
        
        for item in res['items']:
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
        print(f"     ❌ Error fetching videos for {channel_name}: {e}")
        return []

# --- Main Ingestion Logic ---

def ingest_clusters(clusters_config, api_key):
    """Main function to process clusters and fetch video metadata."""
    if not api_key:
        print("Error: YOUTUBE_API_KEY not found. Please check your .env file.")
        return pd.DataFrame()

    youtube = build('youtube', 'v3', developerKey=api_key)
    all_videos = []
    channel_id_cache = load_channel_id_cache() # Load existing cache

    print(f"🚀 Starting Quota-Optimized Ingestion for {len(clusters_config)} clusters...")

    try:
        for cluster_name, handles in clusters_config.items():
            print(f"\n📂 Processing Cluster: {cluster_name}")
            
            for handle in handles:
                print(f"  -> Fetching data for: {handle}")
                
                # 1. Resolve Handle to ID (Cached call)
                cid = resolve_channel_id(youtube, handle, channel_id_cache)
                if not cid:
                    continue
                
                # 2. Fetch Videos (Cheap calls: 2 units per channel)
                videos = get_recent_videos(youtube, cid, handle, limit=30)
                
                # 3. Tag with Cluster Name and append
                for v in videos:
                    v['cluster'] = cluster_name
                    all_videos.append(v)
    finally:
        # Always save the cache even if an error occurs mid-run
        save_channel_id_cache(channel_id_cache) 
        
    df = pd.DataFrame(all_videos)
    return df

# --- Execution Block ---

if __name__ == "__main__":
    load_dotenv(dotenv_path="../.env")
    API_KEY = os.getenv("YOUTUBE_API_KEY")
    
    config_path = "config/clusters.json" # Relative from root
    try:
        with open(config_path, 'r') as f:
            my_clusters = json.load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file not found at {config_path}. Did you create it?")
        exit()
    
    df = ingest_clusters(my_clusters, API_KEY)
    
    if not df.empty:
        output_path = "data/cluster_data.csv"
        os.makedirs(os.path.dirname(output_path), exist_ok=True) 
        df.to_csv(output_path, index=False)
        print(f"\n✅ Success! Saved {len(df)} videos to {output_path}")
        print(df[['cluster', 'channel_name', 'title', 'publish_date']].head())
    else:
        print("\n⚠️ Ingestion complete, but no data was found.")