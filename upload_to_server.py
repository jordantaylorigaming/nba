"""
Simple Article Upload to SFTP

Takes a markdown article (title + content) and uploads it to SFTP
in the same structured JSON format as the blog generation workflow.

Features:
- Uploads markdown articles to SFTP as structured JSON
- Auto-generates relevant image prompts from article content using OpenAI (optional)
- Generates images using Gemini API (optional)
- Uploads generated images to SFTP in the images/ subfolder
- Converts markdown to HTML with styling
"""

import re
import json
import os
import tempfile
import paramiko
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import openai


def generate_image_prompt_from_article(title: str, content: str, openai_api_key: str) -> Optional[str]:
    """Generate a relevant image prompt based on the article title and content using OpenAI."""
    try:
        # Initialize OpenAI client
        client = openai.OpenAI(api_key=openai_api_key)
        
        # Create a prompt for the text generation model
        system_prompt = """You are an expert at creating detailed, engaging image prompts for blog articles. 
Generate a concise, visually descriptive image prompt (maximum 50 words) that captures the essence and main theme of the article.

The image should be suitable for a blog header image (16:9 aspect ratio).
Focus on the key visual elements that represent the article's topic.
No text should be in the image.
Do not include any NBA players in the image. Do not make up any players.
You can include NBA logos, uniforms, and other NBA elements, but not players.
Do not overcomplicate the image. Simple and clean is best.
Return ONLY the image prompt, nothing else."""
        
        user_prompt = f"""Article Title: {title}
Article Content: {content[:500]}...
Generate a compelling image prompt for this article.
Do not overcomplicate the image. Simple and clean is best.
NO TEXT SHOULD BE IN THE IMAGE."""
        
        # Generate image prompt using OpenAI
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=100
        )
        
        # Extract the generated prompt
        if response.choices and len(response.choices) > 0:
            generated_prompt = response.choices[0].message.content.strip()
            return generated_prompt
        
        # Fallback: create a simple prompt from title
        return f"A professional image representing {title}"
            
    except Exception as e:
        print(f"[ERROR] Failed to generate image prompt: {str(e)}")
        # Fallback: create a simple prompt from title
        return f"A professional image representing {title}"


def generate_image(prompt: str, google_api_key: str, slug: str, output_dir: str = "images") -> Optional[str]:
    """Generate an image using Gemini API and save it locally."""
    try:
        # Create images directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Check if image already exists
        image_filename = f"{slug}.png"
        image_path = os.path.join(output_dir, image_filename)
        if os.path.exists(image_path):
            print(f"[IMAGE] Using existing image: {image_path}")
            return image_path
        
        # Initialize Gemini client
        client = genai.Client(api_key=google_api_key)
        
        # Generate image
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_modalities=["Image"],
                image_config=types.ImageConfig(
                    aspect_ratio="16:9"
                ),
            ),
        )
        print(response)
        # Extract and save image
        if not response.candidates or len(response.candidates) == 0:
            print("[ERROR] No candidates in response")
            return None
        
        candidate = response.candidates[0]
        if not candidate.content:
            print("[ERROR] No content in candidate")
            return None
        
        if not candidate.content.parts:
            print("[ERROR] No parts in content")
            return None
        
        for part in candidate.content.parts:
            if part.text is not None:
                print(f"[IMAGE] Text response: {part.text}")
            elif part.inline_data is not None:
                image = Image.open(BytesIO(part.inline_data.data))
                image_filename = f"{slug}.png"
                image_path = os.path.join(output_dir, image_filename)
                image.save(image_path)
                print(f"[IMAGE] Saved image as {image_path}")
                return image_path
        
        return None
        
    except Exception as e:
        print(f"[ERROR] Failed to generate image: {str(e)}")
        return None


def upload_image_to_sftp(image_path: str, sftp_config: Dict[str, str], remote_path: str = "/blog/images") -> bool:
    """Upload an image file to SFTP server."""
    try:
        # Extract SFTP configuration
        host = sftp_config.get("host", "iad1-shared-b7-30.dreamhost.com")
        port = int(sftp_config.get("port", 22))
        username = sftp_config.get("username", "dh_dncxkw")
        password = sftp_config.get("password")
        
        if not password:
            print("[ERROR] SFTP password not provided")
            return False
        
        # Create SSH client
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Connect to SFTP server
        print(f"[CONNECTING] Connecting to SFTP server: {host}:{port}")
        ssh_client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            timeout=30
        )
        
        # Create SFTP client
        sftp_client = ssh_client.open_sftp()
        
        # Create remote directory structure if it doesn't exist
        path_parts = [p for p in remote_path.split('/') if p]
        is_absolute = remote_path.startswith('/')
        
        current_path = ''
        for i, part in enumerate(path_parts):
            if i == 0 and is_absolute:
                current_path = f"/{part}"
            elif current_path:
                current_path = f"{current_path}/{part}"
            else:
                current_path = part
            
            try:
                sftp_client.listdir(current_path)
            except IOError:
                try:
                    sftp_client.mkdir(current_path)
                    print(f"[DIRECTORY] Created directory: {current_path}")
                except IOError:
                    print(f"[DIRECTORY] Directory {current_path} exists or cannot be created")
        
        # Upload image file
        image_filename = os.path.basename(image_path)
        remote_file_path = f"{remote_path}/{image_filename}"
        
        print(f"[UPLOADING] Uploading image {image_filename} to {remote_file_path}")
        sftp_client.put(image_path, remote_file_path)
        
        # Close connections
        sftp_client.close()
        ssh_client.close()
        
        print(f"[SUCCESS] Successfully uploaded image {image_filename} to SFTP server")
        return True
        
    except Exception as e:
        print(f"[ERROR] SFTP image upload failed: {str(e)}")
        return False


def create_slug(title: str) -> str:
    """Create a URL-friendly slug from the title."""
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')


def create_excerpt(content: str, max_length: int = 200) -> str:
    """Create an excerpt from the article content."""
    # Remove markdown formatting for excerpt
    clean_content = re.sub(r'[#*_`]', '', content)
    clean_content = re.sub(r'\n+', ' ', clean_content)
    
    # Take first paragraph or first max_length characters
    sentences = clean_content.split('. ')
    excerpt = ""
    for sentence in sentences:
        if len(excerpt + sentence) < max_length:
            excerpt += sentence + ". "
        else:
            break
    
    # Fallback to first max_length characters
    if not excerpt.strip():
        excerpt = clean_content[:max_length].strip()
        if len(clean_content) > max_length:
            excerpt += "..."
    
    return excerpt.strip()


def convert_markdown_to_html(content: str) -> str:
    """Convert markdown content to HTML with styling."""
    # Add CSS styling
    css_style = """
<style>
.mr-article p { margin: 0 0 1rem; }
.mr-article h1 { margin: 1.5rem 0 1rem; font-weight: 700; font-size: 1.875rem; }
.mr-article h2 { margin: 1.25rem 0 .5rem; font-weight: 700; font-size: 1.5rem; }
.mr-article h3 { margin: 1rem 0 .5rem; font-weight: 600; font-size: 1.25rem; }
.mr-article ul { margin: .5rem 0 1rem; padding-left: 1.25rem; }
.mr-article ol { margin: .5rem 0 1rem; padding-left: 1.25rem; }
.mr-article li { margin: .35rem 0; }
.mr-article blockquote { 
    margin: 1.25rem 0; 
    padding: .75rem 1rem; 
    border-left: 3px solid #e5e7eb; 
    background: #fafafa; 
    border-radius: .25rem; 
    font-style: italic;
}
.mr-article hr { margin: 1.25rem 0; border: 0; border-top: 1px solid #eee; }
.mr-article img { max-width: 100%; height: auto; border-radius: .25rem; }
.mr-article strong { font-weight: 600; }
.mr-article em { font-style: italic; }
.mr-article code { 
    background: #f3f4f6; 
    padding: .125rem .25rem; 
    border-radius: .25rem; 
    font-family: monospace; 
}
</style>"""
    
    html_content = content
    
    # Convert headers
    html_content = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html_content, flags=re.MULTILINE)
    
    # Convert bold and italic
    html_content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_content)
    html_content = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html_content)
    
    # Convert lists
    html_content = re.sub(r'^[\s]*[-*] (.+)$', r'<li>\1</li>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^[\s]*\d+\. (.+)$', r'<li>\1</li>', html_content, flags=re.MULTILINE)
    
    # Wrap consecutive list items in ul/ol tags
    html_content = re.sub(r'(<li>.*</li>\s*)+', lambda m: f'<ul>{m.group(0)}</ul>', html_content, flags=re.DOTALL)
    
    # Convert paragraphs
    lines = html_content.split('\n')
    html_lines = []
    in_list = False
    
    for line in lines:
        line = line.strip()
        if not line:
            html_lines.append('')
            continue
            
        # Check if we're in a list
        if line.startswith('<li>') or line.startswith('<ul>') or line.startswith('</ul>'):
            in_list = line.startswith('<ul>')
            html_lines.append(line)
        elif not line.startswith('<') and not line.startswith('#'):
            # Regular paragraph
            if not in_list:
                html_lines.append(f'<p>{line}</p>')
            else:
                html_lines.append(line)
        else:
            html_lines.append(line)
    
    html_content = '\n'.join(html_lines)
    
    # Clean up empty paragraphs and extra whitespace
    html_content = re.sub(r'<p>\s*</p>', '', html_content)
    html_content = re.sub(r'\n\s*\n', '\n', html_content)
    
    # Wrap in article div
    html_content = f'<div class="mr-article">{html_content}</div>'
    
    return css_style + html_content


def upload_to_sftp(structured_data: Dict[str, Any], sftp_config: Dict[str, str], remote_path: str = "/blog") -> bool:
    """Upload structured blog post data to SFTP server."""
    try:
        # Extract SFTP configuration
        host = sftp_config.get("host", "iad1-shared-b7-30.dreamhost.com")
        port = int(sftp_config.get("port", 22))
        username = sftp_config.get("username", "dh_dncxkw")
        password = sftp_config.get("password")
        
        if not password:
            print("[ERROR] SFTP password not provided")
            return False
        
        # Create SSH client
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Connect to SFTP server
        print(f"[CONNECTING] Connecting to SFTP server: {host}:{port}")
        ssh_client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            timeout=30
        )
        
        # Create SFTP client
        sftp_client = ssh_client.open_sftp()
        
        # Create remote directory structure if it doesn't exist
        # Split the path and create directories one by one
        path_parts = [p for p in remote_path.split('/') if p]  # Filter out empty parts
        is_absolute = remote_path.startswith('/')
        
        # Build path incrementally
        current_path = ''
        for i, part in enumerate(path_parts):
            if i == 0 and is_absolute:
                current_path = f"/{part}"
            elif current_path:
                current_path = f"{current_path}/{part}"
            else:
                current_path = part
            
            try:
                sftp_client.listdir(current_path)
                # Directory exists
            except IOError as e:
                # Directory doesn't exist, try to create it
                try:
                    sftp_client.mkdir(current_path)
                    print(f"[DIRECTORY] Created directory: {current_path}")
                except IOError as mkdir_error:
                    # Creation failed, assume it exists or we don't have permission
                    print(f"[DIRECTORY] Directory {current_path} exists or cannot be created: {str(mkdir_error)}")
                    # Try to continue anyway - might still work
                except Exception as mkdir_error:
                    print(f"[WARNING] Unexpected error creating directory {current_path}: {str(mkdir_error)}")
        
        # Verify final directory exists
        try:
            sftp_client.listdir(remote_path)
            print(f"[DIRECTORY] Remote directory ready: {remote_path}")
        except Exception as e:
            print(f"[WARNING] Cannot verify directory access: {str(e)}")
        
        # Generate filename from slug
        slug = structured_data.get("slug", "blog-post")
        filename = f"{datetime.now().strftime('%Y%m%d')}-{slug}.json"
        remote_file_path = f"{remote_path}/{filename}"
        
        # Convert structured data to JSON string
        json_content = json.dumps(structured_data, indent=2, ensure_ascii=False)
        
        # Upload file
        print(f"[UPLOADING] Uploading {filename} to {remote_file_path}")
        
        # Write to temporary local file first, then upload
        temp_file_path = None
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.json') as temp_file:
                temp_file.write(json_content)
                temp_file_path = temp_file.name
            
            # Upload the file
            sftp_client.put(temp_file_path, remote_file_path)
            
            # Clean up temporary file
            os.unlink(temp_file_path)
            
        except Exception as file_error:
            # Clean up temporary file if it still exists
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            print(f"[ERROR] Failed to write file: {str(file_error)}")
            raise
        
        # Close connections
        sftp_client.close()
        ssh_client.close()
        
        print(f"[SUCCESS] Successfully uploaded {filename} to SFTP server")
        return True
        
    except Exception as e:
        print(f"[ERROR] SFTP upload failed: {str(e)}")
        return False


def upload_article_to_sftp(
    title: str,
    article_content: str,
    sftp_config: Dict[str, str],
    author: str = "Jordan Taylor",
    base_url: str = "/home/dh_dncxkw/nb.casinoxtra.com",
    remote_path: str = "/blog",
    verbose: bool = True,
    google_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Upload a markdown article to SFTP server in structured JSON format.
    
    Args:
        title: Article title
        article_content: Article content in markdown format
        sftp_config: SFTP connection configuration dict with keys:
            - host (optional, defaults to "iad1-shared-b7-30.dreamhost.com")
            - port (optional, defaults to 22)
            - username (optional, defaults to "dh_dncxkw")
            - password (required)
        author: Author name
        base_url: Base URL for the article URL
        remote_path: Remote directory path on SFTP server
        verbose: Whether to print progress messages
        google_api_key: Google API key for image generation (optional)
                       If provided, will generate an image from the prompt
        openai_api_key: OpenAI API key for image prompt generation (optional)
                       If provided, will auto-generate an image prompt based on article content
        
    Returns:
        Dictionary with upload result and structured data
    """
    try:
        if verbose:
            print(f"[PROCESSING] Processing article: '{title}'")
        
        # Generate structured components
        article_id = create_slug(title)
        slug = article_id
        excerpt = create_excerpt(article_content)
        html_content = convert_markdown_to_html(article_content)
        current_time = datetime.now(timezone.utc).isoformat()
        article_url = f"{base_url}/{slug}"
        
        # Generate and upload image if API keys are provided
        image_path = ""
        if google_api_key:
            if openai_api_key:
                # Generate image prompt from article content using OpenAI
                if verbose:
                    print(f"[IMAGE] Generating image prompt from article content...")
                
                image_prompt = generate_image_prompt_from_article(title, article_content, openai_api_key)
            else:
                # Fallback: create a simple prompt from title
                if verbose:
                    print(f"[IMAGE] Creating simple image prompt from title...")
                image_prompt = f"A professional image representing {title}"
            
            if image_prompt:
                if verbose:
                    print(f"[IMAGE] Using prompt: {image_prompt[:80]}...")
                
                # Generate image locally using Gemini
                local_image_path = generate_image(image_prompt, google_api_key, slug)
                
                if local_image_path and os.path.exists(local_image_path):
                    # Upload image to SFTP
                    if verbose:
                        print(f"[IMAGE] Uploading image to SFTP server...")
                    
                    # Construct image remote path
                    full_remote_path = f"{base_url}{remote_path}" if remote_path.startswith('/') else f"{base_url}/{remote_path}"
                    image_remote_path = f"{full_remote_path}/images"
                    
                    image_upload_success = upload_image_to_sftp(local_image_path, sftp_config, image_remote_path)
                    
                    if image_upload_success:
                        # Set image path (relative to the blog folder)
                        image_path = f"https://nb.casinoxtra.com/blog/images/{slug}.png"
                        if verbose:
                            print(f"[IMAGE] Image uploaded successfully: {image_path}")
                    else:
                        if verbose:
                            print(f"[IMAGE] Failed to upload image to SFTP")
                else:
                    if verbose:
                        print(f"[IMAGE] Failed to generate image")
        
        # Create structured data
        structured_data = {
            "id": article_id,
            "slug": slug,
            "title": title,
            "excerpt": excerpt,
            "image": image_path,
            "author": author,
            "published_at": current_time,
            "url": article_url,
            "content_html": html_content
        }
        
        if verbose:
            print(f"[GENERATED] Structured data:")
            print(f"   ID: {article_id}")
            print(f"   Slug: {slug}")
            print(f"   Excerpt: {excerpt[:80]}...")
            print(f"   Image: {image_path}")
            print(f"   HTML Length: {len(html_content)} characters")
        
        # Upload to SFTP
        if verbose:
            print(f"[UPLOADING] Uploading to SFTP server...")
        
        # Construct full remote path from base_url and remote_path
        if base_url and remote_path:
            full_remote_path = f"{base_url}{remote_path}" if remote_path.startswith('/') else f"{base_url}/{remote_path}"
        else:
            full_remote_path = remote_path
        
        upload_success = upload_to_sftp(structured_data, sftp_config, full_remote_path)
        
        result = {
            "success": upload_success,
            "structured_data": structured_data,
            "upload_info": {
                "filename": f"{datetime.now().strftime('%Y%m%d')}-{slug}.json",
                "remote_path": f"{full_remote_path}/{datetime.now().strftime('%Y%m%d')}-{slug}.json",
                "sftp_host": sftp_config.get("host", "iad1-shared-b7-30.dreamhost.com")
            }
        }
        
        if verbose:
            print("=" * 60)
            if upload_success:
                print("[SUCCESS] Article successfully uploaded to SFTP!")
                print(f"   Remote file: {result['upload_info']['remote_path']}")
            else:
                print("[FAILED] Article upload failed")
            print("=" * 60)
        
        return result
        
    except Exception as e:
        if verbose:
            print(f"[ERROR] Article processing and upload failed: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "structured_data": None,
            "upload_info": None
        }


# ------------------------------
# Example Usage
# ------------------------------
if __name__ == "__main__":
    # Example article
    title = "The Future of AI in Healthcare"
    article_content = """
## Introduction

Artificial intelligence is transforming healthcare in unprecedented ways.

## Key Benefits

- Improved diagnostic accuracy
- Faster treatment planning
- Reduced costs

## Conclusion

The future of AI in healthcare is bright and full of potential.
"""
    
    # SFTP configuration
    sftp_config = {
        "host": "iad1-shared-b7-30.dreamhost.com",
        "port": 22,
        "username": "dh_dncxkw",
        "password": "your_password_here"  # Replace with actual password
    }
    
    # API configuration (optional, for image generation)
    google_api_key = "your_google_api_key_here"  # Replace with actual Google API key for image generation
    openai_api_key = "your_openai_api_key_here"  # Replace with actual OpenAI API key for image prompt generation
    # Note: Image prompt will be auto-generated from article title and content using OpenAI
    
    # Upload article
    result = upload_article_to_sftp(
        title=title,
        article_content=article_content,
        sftp_config=sftp_config,
        author="Jordan Taylor",
        verbose=True,
        google_api_key=google_api_key,  # For image generation
        openai_api_key=openai_api_key  # For image prompt generation
    )
    
    if result["success"]:
        print("\n✅ Upload successful!")
        print(f"File: {result['upload_info']['filename']}")
    else:
        print("\n❌ Upload failed!")
        if "error" in result:
            print(f"Error: {result['error']}")