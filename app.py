from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import os
from pymongo import MongoClient
import datetime
import jwt
from passlib.hash import pbkdf2_sha256
from bson import ObjectId
import json

# NEW: Correct import for the modern Google GenAI package
from google import genai
from google.genai import types

load_dotenv()

app = Flask(__name__)
CORS(app)

# MongoDB Connection
try:
    mongodb_uri = os.getenv('MONGODB_URI')
    if not mongodb_uri:
        print("❌ MONGODB_URI not found")
        app.db = None
    else:
        client = MongoClient(mongodb_uri)
        db = client.get_database('aria_db')
        app.db = db
        app.users_collection = db.users
        app.reports_collection = db.reports
        print("✅ Connected to MongoDB successfully!")
except Exception as e:
    print(f"❌ MongoDB connection failed: {e}")
    app.db = None

# ============= GEMINI AI FUNCTION =============

def generate_report_with_gemini(query):
    """Generate report using Google Gemini 2.5 Flash with JSON Mode"""
    try:
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            return None # Handle error in the endpoint
        
        client = genai.Client(api_key=api_key)
        
        # Use a unified prompt for efficiency or separate them as you had.
        # Below is the implementation for your multi-step process using 2.5 Flash.
        
        # We tell the model to strictly return JSON.
        config = types.GenerateContentConfig(
            response_mime_type='application/json'
        )

        # 1. Market Analysis
        market_prompt = f"Analyze market size, growth, opportunities, and risks for: {query}. Return JSON with keys: market_size, growth_trends (list), opportunities (list), risks (list), key_insight."
        market_res = client.models.generate_content(model='gemini-2.5-flash', contents=market_prompt, config=config)
        market_data = json.loads(market_res.text)

        # 2. Competitor Analysis
        comp_prompt = f"Identify competitors and gaps for: {query}. Return JSON with keys: competitors (list of objects with name, strength, weakness, position), gaps (list), differentiation."
        comp_res = client.models.generate_content(model='gemini-2.5-flash', contents=comp_prompt, config=config)
        competitor_data = json.loads(comp_res.text)

        # 3. Audience Profile
        aud_prompt = f"Profile the audience for: {query}. Return JSON with keys: demographics (object), psychographics (object), pain_points (list), buying_behavior (object)."
        aud_res = client.models.generate_content(model='gemini-2.5-flash', contents=aud_prompt, config=config)
        audience_data = json.loads(aud_res.text)

        # 4. Content Strategy
        cont_prompt = f"Create a content strategy for: {query}. Return JSON with keys: platforms (list), content_pillars (list), post_ideas (list), tone_of_voice, content_mix (object)."
        cont_res = client.models.generate_content(model='gemini-2.5-flash', contents=cont_prompt, config=config)
        content_data = json.loads(cont_res.text)

        return {
            "market": market_data,
            "competitors": competitor_data,
            "audience": audience_data,
            "content": content_data
        }
        
    except Exception as e:
        print(f"🤖 Gemini API error: {e}")
        return None

# ============= UPDATED REGISTER/LOGIN (MODERN DATETIME) =============

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    email, password = data.get('email'), data.get('password')
    
    if not email or not password:
        return jsonify({'success': False, 'message': 'Missing credentials'}), 400
        
    if app.users_collection.find_one({'email': email}):
        return jsonify({'success': False, 'message': 'User exists'}), 400

    password_hash = pbkdf2_sha256.hash(password)
    user_data = {"email": email, "password_hash": password_hash, "display_name": data.get('displayName', email.split('@')[0])}
    result = app.users_collection.insert_one(user_data)
    
    token = jwt.encode({
        'user_id': str(result.inserted_id),
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
    }, os.getenv('JWT_SECRET', 'secret'), algorithm='HS256')
    
    return jsonify({'success': True, 'token': token}), 201

# ============= UPDATED REPORT ENDPOINT =============

@app.route('/api/reports/generate', methods=['POST'])
def generate_report_endpoint():
    try:
        data = request.get_json()
        query = data.get('query')
        if not query:
            return jsonify({'success': False, 'message': 'Query required'}), 400
        
        report_data = generate_report_with_gemini(query)
        
        if not report_data:
            return jsonify({'success': False, 'message': 'AI Generation failed'}), 500
        
        # Save to DB
        report_doc = {
            "user_id": "temp_user_123", # Replace with actual auth logic later
            "query": query,
            **report_data,
            "created_at": datetime.datetime.now(datetime.timezone.utc)
        }
        result = app.db.reports.insert_one(report_doc)
        
        report_doc['_id'] = str(result.inserted_id)
        report_doc['created_at'] = report_doc['created_at'].isoformat()
        
        return jsonify({'success': True, 'report': report_doc}), 201
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Include your other routes (GET /api/reports, etc.) here...

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))