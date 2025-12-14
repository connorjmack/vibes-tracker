import os
import json
import pandas as pd
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from google.genai import types
from dotenv import load_dotenv

# --- Configuration ---
INPUT_DATA_PATH = "data/cluster_data.csv"
OUTPUT_DATA_PATH = "data/analyzed_data.csv"
MAX_TOKENS = 64000 # Use a safe, large chunk size for the long context model
MODEL_NAME = "gemini-1.5-flash" # Excellent for summarization/classification

# --- Core Functions ---

def get_transcript(video_id):
    """Fetches the full transcript text for a given video ID."""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        # Combine list of dictionaries into one big string
        full_text = " ".join([t['text'] for t in transcript_list])
        return full_text
    except Exception as e:
        # Transcript might be disabled or unavailable
        return None

def analyze_transcript(client, video_title, transcript):
    """Sends the transcript to Gemini 1.5 Flash for theme and sentiment analysis."""
    
    # We use a JSON schema to force the model to return a structured, usable format
    response_schema = {
        "type": "object",
        "properties": {
            "core_themes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "A list of 3 to 5 core topics or themes discussed in the video, like 'Immigration Policy', 'Tech Layoffs', or 'Climate Change Action'."
            },
            "overall_sentiment": {
                "type": "string",
                "enum": ["Positive", "Neutral", "Negative", "Mixed"],
                "description": "The dominant emotional tone of the discussion."
            },
            "one_sentence_summary": {
                "type": "string",
                "description": "A single, concise sentence summarizing the main takeaway."
            }
        },
        "required": ["core_themes", "overall_sentiment", "one_sentence_summary"]
    }
    
    prompt = f"""
    The following is a transcript for a video titled: "{video_title}".
    
    Analyze the text and extract the key information. Follow the JSON schema provided exactly.
    
    Transcript:
    ---
    {transcript}
    ---
    """
    
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema
            )
        )
        # The response.text is already a valid JSON string
        return response.text
    
    except Exception as e:
        print(f"     ⚠️ LLM Error: {e}")
        return None


def run_analysis():
    """Main function to orchestrate the transcript fetching and AI analysis."""
    load_dotenv()
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not found in .env. Please check your file.")
        return

    # Initialize the Gemini Client
    client = genai.Client(api_key=GEMINI_API_KEY)

    try:
        df = pd.read_csv(INPUT_DATA_PATH)
    except FileNotFoundError:
        print(f"Error: Input data file not found at {INPUT_DATA_PATH}. Run ingest.py first.")
        return

    print(f"🚀 Starting AI Analysis for {len(df)} videos...")
    
    # Lists to store the new data
    summaries = []
    themes = []
    sentiments = []
    
    for index, row in df.iterrows():
        video_id = row['video_id']
        video_title = row['title']
        
        print(f"[{index + 1}/{len(df)}] Analyzing: {video_title} ({row['cluster']})")
        
        # 1. Get Transcript
        transcript = get_transcript(video_id)
        if not transcript or len(transcript) < 100:
            print("     -> Skipping: Transcript unavailable or too short.")
            summaries.append(None)
            themes.append(None)
            sentiments.append(None)
            continue
            
        # 2. Analyze with Gemini
        analysis_json = analyze_transcript(client, video_title, transcript)
        
        if analysis_json:
            try:
                data = json.loads(analysis_json)
                summaries.append(data.get('one_sentence_summary'))
                sentiments.append(data.get('overall_sentiment'))
                # Join themes into a single string for CSV (e.g., "Theme 1 | Theme 2")
                themes.append(" | ".join(data.get('core_themes', [])))
            except json.JSONDecodeError:
                print("     ⚠️ Failed to parse Gemini JSON response.")
                summaries.append(None)
                themes.append(None)
                sentiments.append(None)
        else:
            summaries.append(None)
            themes.append(None)
            sentiments.append(None)
            
    # 3. Save Results
    df['summary'] = summaries
    df['themes'] = themes
    df['sentiment'] = sentiments

    os.makedirs(os.path.dirname(OUTPUT_DATA_PATH), exist_ok=True)
    df.to_csv(OUTPUT_DATA_PATH, index=False)
    
    print(f"\n✅ Analysis Complete! Saved enriched data to {OUTPUT_DATA_PATH}")
    print("\n--- Sample Enriched Output ---")
    print(df[['cluster', 'title', 'themes', 'sentiment']].head())


if __name__ == "__main__":
    # Ensure execution from the root directory
    if os.path.basename(os.getcwd()) == 'src':
        os.chdir('..') 
        
    run_analysis()