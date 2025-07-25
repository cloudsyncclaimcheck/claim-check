import os
from flask import Flask, render_template, request, redirect
from googleapiclient.discovery import build
from dotenv import load_dotenv
import openai
from pathlib import Path
from datetime import datetime
import json

VERDICT_LOG_PATH = Path(__file__).resolve().parent / "verdict_log.json"

# Load .env variables
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CX_ID = os.getenv("GOOGLE_CX_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

assert GOOGLE_API_KEY, "Missing GOOGLE_API_KEY"
assert GOOGLE_CX_ID, "Missing GOOGLE_CX_ID"
assert OPENAI_API_KEY, "Missing OPENAI_API_KEY"

app = Flask(__name__)
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Constants for rate limiting
daily_limit = 20
LOG_FILE = Path(__file__).parent / "usage_log.json"
FEEDBACK_FILE = Path(__file__).parent / "feedback.json"

def read_usage():
    today = datetime.now().strftime("%Y-%m-%d")
    if LOG_FILE.exists():
        with open(LOG_FILE) as f:
            data = json.load(f)
    else:
        data = {}

    count = data.get(today, 0)
    return today, count, data

def write_usage(today, count, data):
    data[today] = count
    with open(LOG_FILE, "w") as f:
        json.dump(data, f)


def load_verdict_log():
    if not VERDICT_LOG_PATH.exists():
        return {}
    with open(VERDICT_LOG_PATH, "r") as f:
        return json.load(f)

def increment_verdict_count(verdict):
    today = datetime.now().strftime("%Y-%m-%d")
    data = load_verdict_log()

    if today not in data:
        data[today] = {}

    if verdict not in data[today]:
        data[today][verdict] = 0

    data[today][verdict] += 1

    with open(VERDICT_LOG_PATH, "w") as f:
        json.dump(data, f)


def search_google(query):
    try:
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        res = service.cse().list(q=query, cx=GOOGLE_CX_ID, num=5).execute()
        items = res.get('items', [])
        return [{
            'title': item['title'],
            'link': item['link'],
            'snippet': item.get('snippet', '')
        } for item in items]
    except Exception as e:
        return [{
            'title': "Google Search Error",
            'link': "#",
            'snippet': str(e)
        }]


def classify_with_gpt(statement, search_results):
    results_combined = "\n".join(
        f"{item['title']}: {item['snippet']} ({item['link']})" for item in search_results[:5]
    )

    prompt = f'''
You are a factual reasoning assistant.

Given a claim and some web search results, your job is to classify the **factual status** of the claim.

Use only the following categories:
- Factual
- False / Hallucinated
- Satirical / Joke
- Controversial
- Unclear / Ambiguous

You MUST respond in this format:
Classification: <one of the above>
Explanation: <one-sentence reasoning>

Claim:
"""{statement}"""

Web search results:
"""{results_combined}"""
'''

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"GPT Error: {str(e)}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/check', methods=['POST'])
def check():
    statement = request.form['statement']
    if len(statement) > 500:
        return render_template(
            'result.html',
            results=[{
                'statement': statement,
                'verdict': 'Input too long',
                'explanation': 'Please limit your input to 500 characters.',
                'sources': []
            }],
            usage_count=0,
            daily_limit=daily_limit
        )

    today, count, data = read_usage()
    if count >= daily_limit:
        return render_template(
            'result.html',
            results=[{
                'statement': statement,
                'verdict': 'Limit Reached',
                'explanation': 'You have reached your daily usage limit.',
                'sources': []
            }],
            usage_count=count,
            daily_limit=daily_limit
        )

    google_results = search_google(statement)
    gpt_result = classify_with_gpt(statement, google_results)

    classification = "Unknown"
    explanation = "Could not extract explanation."

    if "Classification:" in gpt_result and "Explanation:" in gpt_result:
        parts = gpt_result.split("Explanation:")
        classification = parts[0].replace("Classification:", "").strip()
        explanation = parts[1].strip()
        increment_verdict_count(classification)

    write_usage(today, count + 1, data)

    return render_template(
        'result.html',
        results=[{
            'statement': statement,
            'verdict': classification,
            'explanation': explanation,
            'sources': google_results
        }],
        usage_count=count + 1,
        daily_limit=daily_limit
    )

@app.route('/feedback', methods=['POST'])
def feedback():
    liked = request.form.get('liked', '')
    disliked = request.form.get('disliked', '')
    suggestion = request.form.get('suggestion', '')

    entry = {
        "timestamp": datetime.now().isoformat(),
        "liked": liked,
        "disliked": disliked,
        "suggestion": suggestion
    }

    # Save to feedback.json
    if not FEEDBACK_FILE.exists():
        with open(FEEDBACK_FILE, "w") as f:
            json.dump([], f)

    with open(FEEDBACK_FILE, "r+") as f:
        data = json.load(f)
        data.append(entry)
        f.seek(0)
        json.dump(data, f, indent=2)

    return render_template('thank_you.html')

    existing = []
    if FEEDBACK_FILE.exists():
        with open(FEEDBACK_FILE) as f:
            existing = json.load(f)

    existing.append(entry)
    with open(FEEDBACK_FILE, "w") as f:
        json.dump(existing, f, indent=2)

    return redirect('/')

@app.route('/admin/stats')
def admin_stats():
    verdict_data = load_verdict_log()
    return render_template('admin_stats.html', verdict_data=verdict_data)

if __name__ == '__main__':
    app.run(debug=True,port=5001)
