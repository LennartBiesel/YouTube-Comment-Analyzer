from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import google.generativeai as genai
import os
from dotenv import load_dotenv
from youtube_comment_downloader import YoutubeCommentDownloader
import json
import tempfile
import uuid

load_dotenv()
def configure_gemini():
    """Configure the Gemini API."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables or .env file")
   
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-2.0-flash')

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24).hex())
app.config['SESSION_TYPE'] = 'filesystem'

def download_comments(url):
    """Download comments from a YouTube video URL."""
    try:
        downloader = YoutubeCommentDownloader()
        comments_generator = downloader.get_comments_from_url(url)
       
        comments = []
        count = 0
       
        for comment in comments_generator:
            comments.append(comment)
            count += 1
               
        return comments, None
    except Exception as e:
        return [], str(e)

def extract_comment_text(comments):
    """Extract text from comments."""
    return [comment.get("text", "") for comment in comments]

def ask_gemini(model, comments, question):
    context = "\n".join(comments)
    prompt = f"""Context (YouTube comments):
{context}


Based only on the above comments, please answer the following question:
{question}


If the answer cannot be determined from the comments, please say so."""


    try:
        response = model.generate_content(prompt)
        return response.text, None
    except Exception as e:
        return "", str(e)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process_url', methods=['POST'])
def process_url():
    # Get URL from form
    url = request.form['youtube_url']

    comments, error = download_comments(url)

    if error:
        return jsonify({'success': False, 'error': error})
   
    if not comments:
        return jsonify({'success': False, 'error': 'No comments found'})

    session_id = str(uuid.uuid4())
    temp_file = os.path.join(tempfile.gettempdir(), f"comments_{session_id}.json")
   
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(comments, f)
   
    session['comments_file'] = temp_file
    session['video_url'] = url
    session['comment_count'] = len(comments)
   
    return jsonify({'success': True, 'redirect': url_for('chat')})

@app.route('/chat')
def chat():
    # Check if comments are loaded
    if 'comments_file' not in session:
        return redirect(url_for('index'))
   
    video_url = session.get('video_url', 'Unknown')
    comment_count = session.get('comment_count', 0)
   
    return render_template('chat.html', video_url=video_url, comment_count=comment_count)

@app.route('/ask', methods=['POST'])
def ask():
    # Check if comments are loaded
    if 'comments_file' not in session:
        return jsonify({'success': False, 'error': 'No comments loaded. Please load a YouTube video first.'})
   
    # Get question from request
    question = request.form['question']
   
    # Load comments from temp file
    comments_file = session['comments_file']

    try:
        with open(comments_file, 'r', encoding='utf-8') as f:
            comments = json.load(f)
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error loading comments: {str(e)}'})

    comment_texts = extract_comment_text(comments)
   
    # Configure Gemini
    try:
        model = configure_gemini()
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error configuring Gemini API: {str(e)}'})
    
    answer, error = ask_gemini(model, comment_texts, question)

    if error:
        return jsonify({'success': False, 'error': error})
   
    return jsonify({'success': True, 'answer': answer})

@app.route('/clear', methods=['POST'])
def clear_session():
    # Remove temp file if exists
    if 'comments_file' in session and os.path.exists(session['comments_file']):
        try:
            os.remove(session['comments_file'])
        except:
            pass
   
    # Clear session
    session.clear()
   
    return jsonify({'success': True})

if __name__ == '__main__':
    print("Open http://127.0.0.1:5000 in your browser")
    app.run(debug=True)