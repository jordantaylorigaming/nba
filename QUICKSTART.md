# Quick Start Guide

## Installation & Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Create Environment File

Create a `.env` file in the project root:

```bash
# Copy the sample
cp sample.env .env
```

Then edit `.env` and add your API keys:

```env
OPENAI_API_KEY=sk-proj-your-key-here
EVENTREGISTRY_API_KEY=your-eventregistry-key-here
SFTP_HOST=iad1-shared-b7-30.dreamhost.com
SFTP_PORT=22
SFTP_USERNAME=dh_dncxkw
SFTP_PASSWORD=your-sftp-password-here
```

### 3. Run the Application

```bash
streamlit run streamlit_app.py
```

The app will open automatically in your browser at `http://localhost:8501`

## First Use

1. **Select Date**: Use the date picker in the left sidebar (defaults to yesterday)
2. **Generate**: Click "🚀 Generate NBA Article" button
3. **Wait**: The process takes 30-60 seconds:
   - Fetching NBA games
   - Finding news articles
   - Generating AI summaries
4. **Review**: The article will appear in the main area
5. **Upload**: Click "📤 Upload to SFTP" when ready to publish

## Tips

- **Best Results**: Choose dates during NBA season (Oct-Jun)
- **Recent Dates**: Recent games have more news articles available
- **Preview First**: Always review generated articles before uploading
- **API Costs**: Each generation uses OpenAI API credits

## Troubleshooting

**No games found?**
- Check date is during NBA season
- Try a different date

**API Errors?**
- Verify all keys in `.env` are correct
- Check API quotas/limits

**Upload fails?**
- Verify SFTP credentials
- Check server connectivity

## Command Line Alternative

If you prefer command line:

```bash
python -c "
from generate_article import *
from dotenv import load_dotenv
import os

load_dotenv()

date = '2024-01-15'  # Change date
games_data, output_file = collect_all_games_and_articles(date, os.getenv('EVENTREGISTRY_API_KEY'))
article = generate_article_from_data(output_file, os.getenv('OPENAI_API_KEY'))
print(article)
"
```
