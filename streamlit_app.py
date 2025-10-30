import streamlit as st
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from generate_article import (
    get_nba_games,
    get_news_for_game,
    collect_all_games_and_articles,
    generate_article_from_data
)
from upload_to_server import (
    upload_article_to_sftp,
    generate_image_prompt_from_article,
    generate_image,
    create_slug
)

# Load environment variables
load_dotenv()

# Configuration
EVENTREGISTRY_API_KEY = os.getenv("EVENTREGISTRY_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# SFTP Configuration (can be loaded from .env or hardcoded)
SFTP_CONFIG = {
    "host": os.getenv("SFTP_HOST", "iad1-shared-b7-30.dreamhost.com"),
    "port": int(os.getenv("SFTP_PORT", "22")),
    "username": os.getenv("SFTP_USERNAME", "dh_dncxkw"),
    "password": os.getenv("SFTP_PASSWORD", "")
}

# Page configuration
st.set_page_config(
    page_title="NBA Article Generator",
    page_icon="🏀",
    layout="wide"
)

# Initialize session state
if 'generated_article' not in st.session_state:
    st.session_state.generated_article = None
if 'generated_date' not in st.session_state:
    st.session_state.generated_date = None
if 'games_data' not in st.session_state:
    st.session_state.games_data = None
if 'generated_image_path' not in st.session_state:
    st.session_state.generated_image_path = None

def main():
    st.title("🏀 NBA Article Generator")
    st.markdown("Generate daily NBA game summaries and upload them to the blog server.")
    
    # Check API keys
    if not EVENTREGISTRY_API_KEY or not OPENAI_API_KEY:
        st.error("⚠️ Missing API keys. Please check your .env file.")
        st.info("Required: EVENTREGISTRY_API_KEY, OPENAI_API_KEY")
        return
    
    if not SFTP_CONFIG.get("password"):
        st.error("⚠️ Missing SFTP password. Please check your .env file.")
        st.info("Required: SFTP_PASSWORD")
    
    # Sidebar
    with st.sidebar:
        st.header("Settings")
        
        # Date selector
        min_date = datetime(2023, 1, 1).date()
        max_date = datetime.now().date()
        
        selected_date = st.date_input(
            "Select Date",
            value=datetime.now().date() - timedelta(days=1),  # Default to yesterday
            min_value=min_date,
            max_value=max_date
        )
        
        st.markdown("---")
        
        # API Status
        st.subheader("API Status")
        st.success(f"✅ EventRegistry: {'Configured' if EVENTREGISTRY_API_KEY else 'Not configured'}")
        st.success(f"✅ OpenAI: {'Configured' if OPENAI_API_KEY else 'Not configured'}")
        st.success(f"✅ Google (Images): {'Configured' if GOOGLE_API_KEY else 'Not configured'}")
        st.success(f"✅ SFTP: {'Configured' if SFTP_CONFIG.get('password') else 'Not configured'}")
    
    # Main content
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("Generate Article")
        
        if st.button("🚀 Generate NBA Article", type="primary", use_container_width=True):
            with st.spinner("Fetching games and articles..."):
                try:
                    date_str = selected_date.strftime('%Y-%m-%d')
                    
                    # Step 1: Collect games and articles
                    progress = st.progress(0)
                    status_text = st.empty()
                    
                    status_text.text("📊 Fetching NBA games...")
                    progress.progress(10)
                    
                    games_data, output_file = collect_all_games_and_articles(
                        date_str,
                        EVENTREGISTRY_API_KEY,
                        output_file=f'temp_nba_games_{date_str}.json'
                    )
                    
                    if games_data is None:
                        st.error(f"No games found for {date_str}")
                        return
                    
                    st.session_state.games_data = games_data
                    progress.progress(50)
                    status_text.text(f"✅ Found {len(games_data)} games - Fetching news articles...")
                    
                    # Step 2: Generate article
                    progress.progress(70)
                    status_text.text("🤖 Generating article with AI...")
                    
                    article = generate_article_from_data(
                        input_file=output_file,
                        openai_key=OPENAI_API_KEY,
                        output_file=None
                    )
                    
                    progress.progress(85)
                    
                    # Clean up temporary file
                    import os as os_module
                    if os_module.path.exists(output_file):
                        os_module.remove(output_file)
                    
                    st.session_state.generated_article = article
                    st.session_state.generated_date = date_str
                    
                    # Generate image if Google API key is available
                    if GOOGLE_API_KEY:
                        status_text.text("🎨 Generating image...")
                        progress.progress(90)
                        
                        try:
                            # Extract title and content
                            article_lines = article.strip().split('\n')
                            title = article_lines[0] if article_lines else f"NBA Daily Recap - {date_str}"
                            content = '\n'.join(article_lines[1:]) if len(article_lines) > 1 else article
                            
                            # Generate image prompt
                            image_prompt = generate_image_prompt_from_article(
                                title, 
                                content, 
                                OPENAI_API_KEY
                            )
                            
                            # Generate image
                            slug = create_slug(title)
                            image_path = generate_image(
                                image_prompt, 
                                GOOGLE_API_KEY, 
                                slug
                            )
                            
                            if image_path and os_module.path.exists(image_path):
                                st.session_state.generated_image_path = image_path
                            else:
                                st.session_state.generated_image_path = None
                                
                        except Exception as img_error:
                            st.warning(f"⚠️ Image generation failed: {str(img_error)}")
                            st.session_state.generated_image_path = None
                    else:
                        st.session_state.generated_image_path = None
                    
                    progress.progress(100)
                    status_text.text("✅ Article generated successfully!")
                    
                    st.balloons()
                    st.success(f"✅ Article generated successfully!")
                    
                except Exception as e:
                    st.error(f"❌ Error generating article: {str(e)}")
                    st.exception(e)
    
    with col2:
        st.header("Upload to Server")
        
        if st.session_state.generated_article:
            st.info(f"Article ready for: {st.session_state.generated_date}")
            
            # Regenerate Image button
            if GOOGLE_API_KEY and st.button("🔄 Regenerate Image", use_container_width=True):
                with st.spinner("Generating new image..."):
                    try:
                        # Extract title and content
                        article_lines = st.session_state.generated_article.strip().split('\n')
                        title = article_lines[0] if article_lines else f"NBA Daily Recap - {st.session_state.generated_date}"
                        content = '\n'.join(article_lines[1:]) if len(article_lines) > 1 else st.session_state.generated_article
                        
                        # Generate new image prompt
                        image_prompt = generate_image_prompt_from_article(
                            title, 
                            content, 
                            OPENAI_API_KEY
                        )
                        
                        # Generate new image
                        slug = create_slug(title)
                        image_path = generate_image(
                            image_prompt, 
                            GOOGLE_API_KEY, 
                            slug
                        )
                        
                        if image_path and os.path.exists(image_path):
                            st.session_state.generated_image_path = image_path
                            st.success("✅ New image generated!")
                            st.rerun()
                        else:
                            st.error("❌ Image generation failed")
                            
                    except Exception as img_error:
                        st.error(f"❌ Error: {str(img_error)}")
            
            st.markdown("---")
            
            if st.button("📤 Upload to SFTP", type="primary", use_container_width=True):
                if not SFTP_CONFIG.get("password"):
                    st.error("SFTP password not configured")
                    return
                
                with st.spinner("Uploading to SFTP server..."):
                    try:
                        # Extract title from article (first line)
                        article_lines = st.session_state.generated_article.strip().split('\n')
                        title = article_lines[0] if article_lines else f"NBA Daily Recap - {st.session_state.generated_date}"
                        
                        # Remove title from content if it's there
                        content = '\n'.join(article_lines[1:]) if len(article_lines) > 1 else st.session_state.generated_article
                        
                        # Upload article and image
                        # The upload_article_to_sftp will reuse the existing image if it exists
                        result = upload_article_to_sftp(
                            title=title,
                            article_content=content,
                            sftp_config=SFTP_CONFIG,
                            author="Jordan Taylor",
                            base_url="/home/dh_dncxkw/nb.casinoxtra.com",
                            remote_path="/blog",
                            verbose=False,
                            google_api_key=GOOGLE_API_KEY if GOOGLE_API_KEY else None,
                            openai_api_key=OPENAI_API_KEY if OPENAI_API_KEY else None
                        )
                        
                        if result["success"]:
                            st.success("✅ Upload successful!")
                            st.balloons()
                            st.json({
                                "filename": result["upload_info"]["filename"],
                                "remote_path": result["upload_info"]["remote_path"],
                                "sftp_host": result["upload_info"]["sftp_host"]
                            })
                        else:
                            st.error("❌ Upload failed")
                            if "error" in result:
                                st.error(f"Error: {result['error']}")
                    
                    except Exception as e:
                        st.error(f"❌ Upload error: {str(e)}")
                        st.exception(e)
        else:
            st.info("Generate an article first")
    
    # Display article
    if st.session_state.generated_article:
        st.markdown("---")
        st.header("📄 Generated Article")
        
        # Display generated image if available
        if st.session_state.generated_image_path and os.path.exists(st.session_state.generated_image_path):
            st.subheader("🎨 Generated Image")
            st.image(st.session_state.generated_image_path, caption="Article Header Image", use_container_width=True)
            st.markdown("---")
        
        # Display article with expander for full view
        with st.expander("View Full Article", expanded=True):
            st.markdown(st.session_state.generated_article)
        
        # Show games data
        if st.session_state.games_data:
            st.subheader("Games Summary")
            for idx, game in enumerate(st.session_state.games_data, 1):
                with st.expander(f"{idx}. {game['score']}"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.write(f"**Home:** {game['home_team']} ({game['home_points']} pts)")
                        st.write(f"**Winner:** {game['winner']}")
                    with col_b:
                        st.write(f"**Away:** {game['away_team']} ({game['away_points']} pts)")
                        st.write(f"**Articles Found:** {len(game['articles'])}")
                    
                    if game['articles']:
                        st.write("**Related Articles:**")
                        for i, article in enumerate(game['articles'][:3], 1):
                            title = article.get('title', 'N/A')
                            url = article.get('url', '#')
                            st.markdown(f"{i}. [{title}]({url})")

if __name__ == "__main__":
    main()