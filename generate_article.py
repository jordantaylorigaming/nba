from nba_api.stats.endpoints import leaguegamefinder
import pandas as pd
from datetime import datetime, timedelta
from eventregistry import *
import openai
import os
import json

from dotenv import load_dotenv
load_dotenv()

# Configuration
EVENTREGISTRY_API_KEY = os.getenv("EVENTREGISTRY_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def get_nba_games(date_str):
    """Fetch NBA games for a specific date."""
    gamefinder = leaguegamefinder.LeagueGameFinder()
    games = gamefinder.get_data_frames()[0]
    games['GAME_DATE'] = pd.to_datetime(games['GAME_DATE'])
    
    filtered_games = games[
        (games['GAME_DATE'] >= date_str) & 
        (games['GAME_DATE'] <= date_str)
    ]
    
    filtered_games = filtered_games[['GAME_DATE', 'TEAM_NAME', 'MATCHUP', 'PTS', 'GAME_ID']].copy()
    
    # Separate home and away games
    home_games = filtered_games[filtered_games['MATCHUP'].str.contains(r'\bvs\.?\b', regex=True)].copy()
    away_games = filtered_games[filtered_games['MATCHUP'].str.contains('@')].copy()
    
    # Merge home and away
    merged = home_games.merge(
        away_games,
        on=['GAME_ID'],
        how='inner',
        suffixes=('_HOME', '_AWAY')
    )
    
    merged['PTS_HOME'] = pd.to_numeric(merged['PTS_HOME'], errors='coerce')
    merged['PTS_AWAY'] = pd.to_numeric(merged['PTS_AWAY'], errors='coerce')
    
    results = merged[['GAME_DATE_HOME', 'TEAM_NAME_HOME', 'PTS_HOME', 'TEAM_NAME_AWAY', 'PTS_AWAY']].rename(
        columns={
            'GAME_DATE_HOME': 'Date',
            'TEAM_NAME_HOME': 'Home',
            'PTS_HOME': 'HomePTS',
            'TEAM_NAME_AWAY': 'Away',
            'PTS_AWAY': 'AwayPTS'
        }
    ).sort_values(['Date', 'Home']).reset_index(drop=True)
    
    results['Score'] = results.apply(
        lambda r: f"{r['Home']} {int(r['HomePTS'])} - {int(r['AwayPTS'])} {r['Away']}", 
        axis=1
    )
    results['Winner'] = results.apply(
        lambda r: r['Home'] if r['HomePTS'] > r['AwayPTS'] else r['Away'], 
        axis=1
    )
    
    return results

def get_news_for_game(team1, team2, date_str, api_key):
    """Fetch news articles for a specific game."""
    er = EventRegistry(apiKey=api_key)
    team1_wiki = team1.replace(" ", "_")
    team2_wiki = team2.replace(" ", "_")
    
    query = {
        "$query": {
            "$and": [
                {"conceptUri": f"http://en.wikipedia.org/wiki/{team1_wiki}"},
                {"conceptUri": f"http://en.wikipedia.org/wiki/{team2_wiki}"},
                {"categoryUri": "dmoz/Sports/Basketball"},
                {"locationUri": "http://en.wikipedia.org/wiki/United_States"},
                {
                    "dateStart": date_str,
                    "dateEnd": (pd.to_datetime(date_str) + timedelta(days=1)).strftime('%Y-%m-%d'),
                    "lang": "eng"
                }
            ]
        },
        "$filter": {
            "dataType": ["news", "pr", "blog"],
            "isDuplicate": "skipDuplicates"
        }
    }
    
    q = QueryArticlesIter.initWithComplexQuery(query)
    articles = []
    seen_titles = set()
    seen_urls = set()
    
    try:
        for article in q.execQuery(er, maxItems=3):
            if article.get("relevance", 0) >= 100:
                # Filter duplicates by title and URL
                title = article.get("title", "").strip().lower()
                url = article.get("url", "").strip()
                
                # Skip if we've seen this title or URL
                if title in seen_titles or url in seen_urls:
                    continue
                
                seen_titles.add(title)
                seen_urls.add(url)
                articles.append(article)
    except Exception as e:
        print(f"Error fetching articles for {team1} vs {team2}: {e}")
    
    return articles

def collect_all_games_and_articles(date_str, eventregistry_key, output_file=None):
    """
    STEP 1: Collect all games and their articles.
    Save to JSON file for inspection.
    """
    print(f"Fetching games for {date_str}...")
    games = get_nba_games(date_str)
    
    if games.empty:
        print(f"No NBA games found for {date_str}")
        return None
    
    print(f"Found {len(games)} games\n")
    
    # Collect all data
    games_data = []
    
    for idx, game in games.iterrows():
        print(f"Processing: {game['Home']} vs {game['Away']}")
        
        # Fetch articles
        articles = get_news_for_game(
            game['Home'], 
            game['Away'], 
            game['Date'].strftime('%Y-%m-%d'),
            eventregistry_key
        )
        
        print(f"  Found {len(articles)} relevant articles")
        
        game_info = {
            'date': game['Date'].strftime('%Y-%m-%d'),
            'home_team': game['Home'],
            'away_team': game['Away'],
            'home_points': int(game['HomePTS']),
            'away_points': int(game['AwayPTS']),
            'score': game['Score'],
            'winner': game['Winner'],
            'articles': articles
        }
        
        games_data.append(game_info)
        
        # Print article details
        if articles:
            print(f"  Article titles:")
            for i, article in enumerate(articles[:3], 1):
                print(f"    {i}. {article.get('title', 'N/A')}")
        print()
    
    # Save to file
    if output_file is None:
        output_file = f'nba_games_articles_{date_str}.json'
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(games_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Data saved to: {output_file}")
    print(f"✓ Total games: {len(games_data)}")
    print(f"✓ Total articles: {sum(len(g['articles']) for g in games_data)}")
    
    return games_data, output_file

def format_articles_for_prompt(articles):
    """Format article data for LLM prompt."""
    if not articles:
        return "No detailed articles available for this game."
    
    formatted = []
    for i, article in enumerate(articles[:3], 1):  # Limit to top 3 articles
        text = f"Article {i}:\n"
        text += f"Title: {article.get('title', 'N/A')}\n"
        text += f"Source: {article.get('source', {}).get('title', 'N/A')}\n"
        body = article.get('body', '')
        # Truncate body to avoid token limits
        text += f"Content: {body[:800]}...\n\n"
        formatted.append(text)
    
    return "\n".join(formatted)

def call_openai(prompt, api_key, model="gpt-4.1", temperature=0.7):
    """Call OpenAI API directly."""
    client = openai.OpenAI(api_key=api_key)
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a professional sports journalist writing NBA game summaries."},
            {"role": "user", "content": prompt}
        ],
        temperature=temperature,
        max_tokens=2000
    )
    
    return response.choices[0].message.content

def generate_game_summary(home_team, away_team, score, winner, articles_text, api_key):
    """Generate a summary for a single game."""
    prompt = f"""You are a sports journalist writing a concise summary of an NBA game.

Game Details:
- Teams: {home_team} (Home) vs {away_team} (Away)
- Final Score: {score}
- Winner: {winner}

News Articles Available:
{articles_text}

Write a 2-3 paragraph summary of this game that includes:
1. The final score and winning team
2. Key highlights and standout performances mentioned in the articles
3. Any notable storylines or context

Keep it professional, engaging, and factual. Do not make up information not present in the articles.

Summary:"""
    
    return call_openai(prompt, api_key)

def generate_daily_summary(date_str, game_summaries, api_key):
    """Generate the overall daily summary article."""
    prompt = f"""You are a sports journalist writing a daily NBA recap article.

Date: {date_str}

Individual Game Summaries:
{game_summaries}

Write a comprehensive article (4-6 paragraphs) that:
1. Starts with an engaging introduction about the day's NBA action
2. Highlights the most exciting or significant games
3. Mentions standout individual performances
4. Includes any notable trends or storylines
5. Mentions the other games that were played that day and weren't mentioned before
6. Ends with a brief conclusion

IMPORTANT: The article title MUST include the date {date_str} in the title. Format it as part of an engaging and professional title (e.g., "NBA Recap {date_str}: Title Text" or similar format).

Article:"""
    
    return call_openai(prompt, api_key, temperature=0.7)

def generate_article_from_data(input_file, openai_key, output_file=None):
    """
    STEP 2: Generate article from collected data.
    Read from JSON file and create summaries.
    """
    print(f"Loading data from: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        games_data = json.load(f)
    
    print(f"Loaded {len(games_data)} games\n")
    
    # Process each game
    game_summaries = []
    
    for game_info in games_data:
        print(f"Generating summary: {game_info['home_team']} vs {game_info['away_team']}")
        
        articles_text = format_articles_for_prompt(game_info['articles'])
        
        summary = generate_game_summary(
            home_team=game_info['home_team'],
            away_team=game_info['away_team'],
            score=game_info['score'],
            winner=game_info['winner'],
            articles_text=articles_text,
            api_key=openai_key
        )
        
        game_summaries.append(f"## {game_info['score']}\n\n{summary}")
        print(f"  ✓ Summary generated\n")
    
    # Generate overall daily summary
    print("Generating daily summary article...")
    
    final_article = generate_daily_summary(
        date_str=games_data[0]['date'],
        game_summaries="\n\n".join(game_summaries),
        api_key=openai_key
    )
    
    # Remove ** from title if present
    lines = final_article.split('\n')
    if lines and lines[0].startswith('**') and lines[0].endswith('**'):
        lines[0] = lines[0].strip('*')
    final_article = '\n'.join(lines)
    
    # Save article
    if output_file is None:
        output_file = f'nba_summary_{games_data[0]["date"]}.md'
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(final_article)
    
    print(f"\n✓ Article saved to: {output_file}")
    
    return final_article
