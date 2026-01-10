"""Create sample analyzed data to demonstrate Phase 2 features."""

import pandas as pd
import random
from datetime import datetime, timedelta, timezone

# Sample themes by cluster
THEMES_BY_CLUSTER = {
    'Left': [
        ['Healthcare Reform', 'Climate Action', 'Education Funding'],
        ['Voting Rights', 'Income Inequality', 'Social Justice'],
        ['Immigration Reform', 'Gun Control', 'LGBTQ Rights'],
        ['Climate Change', 'Renewable Energy', 'Environmental Justice'],
        ['Democratic Process', 'Corruption Investigation', 'Campaign Finance'],
    ],
    'right': [
        ['Border Security', 'Immigration Control', 'National Sovereignty'],
        ['Second Amendment Rights', 'Gun Ownership', 'Self Defense'],
        ['Tax Cuts', 'Small Government', 'Free Market'],
        ['Traditional Values', 'Religious Freedom', 'Family Values'],
        ['Election Integrity', 'Voter ID Laws', 'Constitutional Rights'],
    ],
    'mainstream': [
        ['Breaking News', 'Political Analysis', 'Economic Indicators'],
        ['International Relations', 'Global Conflicts', 'Diplomacy'],
        ['Stock Market', 'Federal Reserve', 'Inflation'],
        ['Supreme Court Decisions', 'Legislative Action', 'Presidential Policy'],
        ['Technology Innovation', 'AI Development', 'Cybersecurity'],
    ],
    'manosphere': [
        ['Modern Dating', 'Relationship Dynamics', 'Gender Roles'],
        ['Self Improvement', 'Fitness', 'Career Success'],
        ['Social Media Culture', 'Online Dating', 'Hook-up Culture'],
        ['Men\'s Rights', 'Custody Laws', 'Divorce'],
        ['Masculinity', 'Personal Development', 'Financial Independence'],
    ],
    'my-env': [
        ['Climate Crisis', 'Global Warming', 'Carbon Emissions'],
        ['Renewable Energy', 'Solar Power', 'Wind Energy'],
        ['Biodiversity Loss', 'Species Extinction', 'Habitat Destruction'],
        ['Plastic Pollution', 'Ocean Health', 'Marine Conservation'],
        ['Sustainable Living', 'Zero Waste', 'Green Technology'],
    ]
}

CATEGORIES = {
    'Left': ['Political Issues', 'Social Issues', 'Political Issues'],
    'right': ['Political Issues', 'Political Issues', 'Political Issues'],
    'mainstream': ['Political Issues', 'International Affairs', 'Economic Topics'],
    'manosphere': ['Social Issues', 'Cultural Topics', 'Social Issues'],
    'my-env': ['Other', 'Technology & Science', 'Other']
}

SENTIMENT_DIST = {
    'Left': {'Positive': 0.3, 'Neutral': 0.3, 'Negative': 0.3, 'Mixed': 0.1},
    'right': {'Positive': 0.25, 'Neutral': 0.25, 'Negative': 0.35, 'Mixed': 0.15},
    'mainstream': {'Positive': 0.2, 'Neutral': 0.5, 'Negative': 0.2, 'Mixed': 0.1},
    'manosphere': {'Positive': 0.15, 'Neutral': 0.3, 'Negative': 0.4, 'Mixed': 0.15},
    'my-env': {'Positive': 0.15, 'Neutral': 0.25, 'Negative': 0.5, 'Mixed': 0.1}
}

FRAMING_DIST = {
    'Left': {'favorable': 0.35, 'critical': 0.4, 'neutral': 0.2, 'alarmist': 0.05},
    'right': {'favorable': 0.3, 'critical': 0.45, 'neutral': 0.15, 'alarmist': 0.1},
    'mainstream': {'favorable': 0.15, 'critical': 0.2, 'neutral': 0.6, 'alarmist': 0.05},
    'manosphere': {'favorable': 0.2, 'critical': 0.5, 'neutral': 0.25, 'alarmist': 0.05},
    'my-env': {'favorable': 0.1, 'critical': 0.3, 'neutral': 0.2, 'alarmist': 0.4}
}

ENTITIES = [
    'Joe Biden', 'Donald Trump', 'Kamala Harris', 'Ron DeSantis', 'Supreme Court',
    'Congress', 'Senate', 'House of Representatives', 'Federal Reserve', 'UN',
    'NATO', 'China', 'Russia', 'Ukraine', 'Israel', 'Gaza', 'EPA', 'CDC', 'FDA'
]

def weighted_choice(choices):
    """Make a weighted random choice."""
    options, weights = zip(*choices.items())
    return random.choices(options, weights=weights, k=1)[0]

def generate_sample_data(num_videos_per_cluster=70):
    """Generate sample analyzed data."""
    data = []
    base_date = datetime.now(timezone.utc) - timedelta(days=30)

    for cluster, theme_sets in THEMES_BY_CLUSTER.items():
        for i in range(num_videos_per_cluster):
            themes = random.choice(theme_sets)
            categories = [CATEGORIES[cluster][j % len(CATEGORIES[cluster])] for j in range(len(themes))]

            # Pick 2-4 entities
            num_entities = random.randint(2, 4)
            entities = random.sample(ENTITIES, num_entities)

            sentiment = weighted_choice(SENTIMENT_DIST[cluster])
            framing = weighted_choice(FRAMING_DIST[cluster])

            # Generate timestamps spread over 30 days
            video_date = base_date + timedelta(days=random.randint(0, 30))

            video = {
                'video_id': f'vid_{cluster}_{i}',
                'title': f'Sample {cluster.title()} Video: {themes[0]}',
                'publish_date': video_date.isoformat(),
                'channel_name': f'@Sample{cluster.title()}Channel',
                'url': f'https://youtube.com/watch?v=sample_{cluster}_{i}',
                'cluster': cluster,
                'run_timestamp': datetime.now(timezone.utc).isoformat(),
                'summary': f'This video discusses {themes[0].lower()} in the context of {cluster} political discourse.',
                'themes': ' | '.join(themes),
                'theme_categories': ' | '.join(categories),
                'sentiment': sentiment,
                'framing': framing,
                'named_entities': ' | '.join(entities),
                'analysis_timestamp': datetime.now(timezone.utc).isoformat()
            }
            data.append(video)

    return pd.DataFrame(data)

if __name__ == '__main__':
    # Generate sample data
    df = generate_sample_data(num_videos_per_cluster=70)

    # Save to CSV
    df.to_csv('data/analyzed_data.csv', index=False)
    print(f'Created sample analyzed data with {len(df)} videos')
    print(f'\nVideos per cluster:')
    print(df['cluster'].value_counts())
    print(f'\nSample data:')
    print(df[['cluster', 'themes', 'sentiment', 'framing']].head())

    # Also create historical snapshots for temporal analysis
    import shutil
    import os

    # Create 3 historical snapshots (different dates)
    for days_ago in [7, 14, 21]:
        snapshot_date = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        snapshot_dir = f'data/historical/{snapshot_date}'
        os.makedirs(snapshot_dir, exist_ok=True)

        # Generate slightly different data for each snapshot
        historical_df = generate_sample_data(num_videos_per_cluster=70)
        historical_df.to_csv(f'{snapshot_dir}/analyzed_data.csv', index=False)
        print(f'\nCreated historical snapshot for {snapshot_date}')
