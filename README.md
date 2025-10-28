# NBA Article Generator

A Streamlit application that generates AI-powered NBA daily recap articles and uploads them to an SFTP server.

## Features

- 📅 **Date Selection**: Choose any date to generate articles for
- 🏀 **NBA Game Data**: Automatically fetches game results from the NBA API
- 📰 **News Integration**: Pulls relevant news articles for each game using EventRegistry
- 🤖 **AI Generation**: Uses OpenAI GPT to create engaging article summaries
- 📤 **SFTP Upload**: Uploads articles directly to your blog server

## Prerequisites

- Python 3.8 or higher
- API Keys for:
  - OpenAI (for article generation)
  - EventRegistry (for news articles)
  - SFTP credentials (for server upload)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd sports_blog
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file based on `sample.env`:
```bash
cp sample.env .env
```

4. Fill in your API keys and credentials in `.env`:
```
OPENAI_API_KEY=your_openai_key_here
EVENTREGISTRY_API_KEY=your_eventregistry_key_here
SFTP_HOST=iad1-shared-b7-30.dreamhost.com
SFTP_PORT=22
SFTP_USERNAME=dh_dncxkw
SFTP_PASSWORD=your_sftp_password_here
```

## Usage

### Running the Streamlit App

```bash
streamlit run streamlit_app.py
```

The app will open in your browser at `http://localhost:8501`

### How to Use

1. **Select a Date**: Use the date picker in the sidebar to choose the date for which you want to generate an article
2. **Generate Article**: Click the "Generate NBA Article" button
   - The app will fetch NBA games for the selected date
   - It will gather relevant news articles for each game
   - It will use AI to generate game summaries
   - Finally, it will create a comprehensive daily recap article
3. **Review Article**: The generated article will be displayed in the main area
4. **Upload to Server**: Click the "Upload to SFTP" button to publish the article
5. **View Game Details**: Expand each game section to see detailed information

### Command Line Usage (Alternative)

You can also run the generation process directly from the command line:

```bash
python -c "
from generate_article import collect_all_games_and_articles, generate_article_from_data
from dotenv import load_dotenv
import os

load_dotenv()

# Step 1: Collect games and articles
games_data, output_file = collect_all_games_and_articles(
    '2024-01-15',  # Change date as needed
    os.getenv('EVENTREGISTRY_API_KEY')
)

# Step 2: Generate article
article = generate_article_from_data(
    output_file,
    os.getenv('OPENAI_API_KEY')
)

print(article)
"
```

## Project Structure

```
sports_blog/
├── streamlit_app.py          # Main Streamlit application
├── generate_article.py       # Core article generation logic
├── upload_to_server.py       # SFTP upload functionality
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (create this)
├── sample.env               # Sample environment file
└── README.md                # This file
```

## How It Works

### 1. Game Data Collection
- Uses the `nba-api` library to fetch NBA games for the selected date
- Separates home and away teams with their scores
- Identifies the winner of each game

### 2. News Article Gathering
- Uses EventRegistry API to find relevant news articles
- Searches for articles mentioning both teams in each game
- Filters for recent, high-relevance articles

### 3. Article Generation
- For each game, generates a 2-3 paragraph summary using OpenAI
- Creates individual game summaries with highlights and context
- Combines all summaries into a comprehensive daily recap article

### 4. SFTP Upload
- Converts markdown to HTML with styling
- Creates structured JSON data with metadata
- Uploads to the configured SFTP server for blog publishing

## Configuration

### OpenAI Settings

The app uses GPT-4o-mini by default for cost efficiency. You can modify the model in `generate_article.py`:

```python
def call_openai(prompt, api_key, model="gpt-4o-mini", temperature=0.7):
```

### Article Format

The generated articles include:
- A professional title
- Introduction paragraph
- Game-by-game summaries with scores and highlights
- Standout performances
- Notable storylines
- Conclusion

### Upload Settings

SFTP upload settings are configured in `streamlit_app.py`:

```python
SFTP_CONFIG = {
    "host": os.getenv("SFTP_HOST", "iad1-shared-b7-30.dreamhost.com"),
    "port": int(os.getenv("SFTP_PORT", "22")),
    "username": os.getenv("SFTP_USERNAME", "dh_dncxkw"),
    "password": os.getenv("SFTP_PASSWORD", "")
}
```

## Troubleshooting

### No games found
- Check that there were actual NBA games on the selected date
- NBA season typically runs from October to June

### API Key Errors
- Verify all API keys are correctly set in `.env`
- Check that keys are not expired or rate-limited

### SFTP Upload Fails
- Verify SFTP credentials are correct
- Check network connectivity to SFTP server
- Ensure the SFTP server is accessible

### No Articles Found
- EventRegistry might not have articles for that specific date/game
- The app will still generate an article, but without news context

## Development

### Adding New Features

To add features like:
- Email notifications when articles are published
- Scheduled automatic generation
- Different article templates
- Additional sports leagues

Modify the appropriate functions in `generate_article.py` or `streamlit_app.py`.

### Testing

Run individual components:

```python
# Test NBA game fetching
from generate_article import get_nba_games
games = get_nba_games('2024-01-15')
print(games)

# Test article generation
from generate_article import generate_game_summary
summary = generate_game_summary(
    'Lakers', 'Warriors', 'Lakers 110 - 108 Warriors', 'Lakers',
    'Sample article text...', OPENAI_API_KEY
)
print(summary)
```

## License

This project is provided as-is for educational and personal use.

## Support

For issues or questions:
1. Check that all API keys are valid
2. Verify network connectivity
3. Review the console output for detailed error messages
