"""Generate word clouds from analyzed themes."""

import os
import sys
import pandas as pd
from wordcloud import WordCloud, STOPWORDS
import matplotlib.pyplot as plt


def generate_word_cloud(text, filename, title):
    """Generate word cloud from text."""
    custom_stopwords = set(STOPWORDS)
    custom_stopwords.update(['video', 'youtube', 'podcast', 'show', 'clip', 'live',
                            'new', 'full', 'episode', 'watch', 'official', 'exclusive'])

    wordcloud = WordCloud(
        width=1200,
        height=800,
        background_color='white',
        stopwords=custom_stopwords,
        collocations=False,
        max_words=100
    ).generate(text.lower())

    plt.figure(figsize=(12, 8))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis('off')
    plt.title(title, fontsize=20, pad=20)

    os.makedirs(os.path.dirname(filename), exist_ok=True)
    plt.savefig(filename, bbox_inches='tight', dpi=300)
    plt.close()
    print(f"   -> Saved: {filename}")

def main():
    """Generate word clouds from themes."""
    print("🚀 Generating Theme Word Clouds...")

    # Load analyzed data
    df = pd.read_csv('data/analyzed_data.csv')

    # Filter to videos with themes
    df_with_themes = df[df['themes'].notna()]
    print(f"Found {len(df_with_themes)} videos with themes")

    # Combined word cloud from all themes
    all_themes = ' '.join(df_with_themes['themes'].astype(str))
    generate_word_cloud(
        all_themes,
        'figures/enhanced/combined_themes_wordcloud.png',
        'Combined Themes - All Clusters'
    )

    # Per-cluster word clouds
    for cluster in df['cluster'].unique():
        cluster_df = df_with_themes[df_with_themes['cluster'] == cluster]
        if len(cluster_df) == 0:
            continue

        cluster_themes = ' '.join(cluster_df['themes'].astype(str))
        generate_word_cloud(
            cluster_themes,
            f'figures/enhanced/{cluster}_themes_wordcloud.png',
            f'{cluster.title()} Cluster - Themes'
        )

    print("\n✅ Word cloud generation complete!")

if __name__ == '__main__':
    main()
