import os
import pandas as pd
from wordcloud import WordCloud, STOPWORDS
import matplotlib.pyplot as plt

# --- Configuration ---
DATA_PATH = "../data/cluster_data.csv"
FIGURES_DIR = "../figures"
WIDTH = 1200
HEIGHT = 800
BACKGROUND_COLOR = 'white'

def generate_word_cloud(text, filename, title, extra_stopwords=None):
    """Generates a word cloud from text and saves it to the figures directory."""
    
    # 1. Customize Stopwords
    # Add common podcast filler words or irrelevant titles
    custom_stopwords = set(STOPWORDS)
    custom_stopwords.update(['video', 'youtube', 'podcast', 'show', 'clip', 'live', 'new', 'full', 'episode', 'watch', 'official', 'exclusive', 'what', 'why', 'how', 'when', 'amp', 'gets'])
    
    if extra_stopwords:
        custom_stopwords.update(extra_stopwords)

    # 2. Generate WordCloud object
    wordcloud = WordCloud(
        width=WIDTH,
        height=HEIGHT,
        background_color=BACKGROUND_COLOR,
        stopwords=custom_stopwords,
        collocations=False, # Avoids counting bigrams like 'new york' as one word
        max_words=100
    ).generate(text.lower())
    
    # 3. Plot and Save
    plt.figure(figsize=(12, 8))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis('off')
    plt.title(title, fontsize=20, pad=20)
    
    save_path = os.path.join(FIGURES_DIR, filename)
    plt.savefig(save_path, bbox_inches='tight')
    plt.close()
    print(f"   -> Saved: {save_path}")

def make_word_clouds():
    """Main function to generate word clouds for all combined and cluster titles."""
    print("🚀 Starting Word Cloud Generation...")
    
    # 1. Check for data and figures directory
    try:
        df = pd.read_csv(DATA_PATH)
    except FileNotFoundError:
        print(f"Error: Data file not found at {DATA_PATH}. Run ingest.py first.")
        return

    os.makedirs(FIGURES_DIR, exist_ok=True)
    
    # --- 2. Combined Word Cloud ---
    print("\n[1/2] Generating Combined Titles Word Cloud...")
    all_titles = " ".join(df['title'].astype(str).tolist())
    generate_word_cloud(
        all_titles, 
        "combined_titles_wordcloud.png", 
        "Combined Titles Across All Clusters"
    )

    # --- 3. Cluster Word Clouds ---
    print("\n[2/2] Generating Cluster-Specific Word Clouds...")
    
    # Group by the cluster column and process each group
    grouped = df.groupby('cluster')
    
    for cluster_name, group_df in grouped:
        print(f"  Processing cluster: {cluster_name}")
        cluster_titles = " ".join(group_df['title'].astype(str).tolist())
        
        generate_word_cloud(
            cluster_titles,
            f"{cluster_name}_wordcloud.png",
            f"Titles for Cluster: {cluster_name.upper()}"
        )
        
    print("\n✅ Word Cloud Generation Complete.")

if __name__ == "__main__":
    # Adjust pathing if the script is run directly from src/ (standard practice)
    # This block assumes execution from the project root directory
    
    # Get the directory of the current script (src/) and navigate up one level (..)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir) # Change current working directory to src/ temporarily
    
    make_word_clouds()