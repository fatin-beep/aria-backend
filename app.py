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

# Correct imports for the modern Google GenAI package
from google import genai
from google.genai import types

load_dotenv()

app = Flask(__name__)
CORS(app)

# MongoDB Connection
try:
    mongodb_uri = os.getenv('MONGODB_URI')
    client = MongoClient(mongodb_uri)
    db = client.get_database('aria_db')
    app.db = db
    app.users_collection = db.users
    app.reports_collection = db.reports
    print("✅ Connected to MongoDB")
except Exception as e:
    print(f"❌ MongoDB Error: {e}")
    app.db = None

# ============= AUTH LOGIC (FIXED) =============

@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json() or {}
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password required'}), 400
        
        if app.users_collection.find_one({'email': email}):
            return jsonify({'success': False, 'message': 'User already exists'}), 400
        
        user_data = {
            'email': email,
            'password_hash': pbkdf2_sha256.hash(password),
            'display_name': data.get('displayName', email.split('@')[0]),
            'created_at': datetime.datetime.now(datetime.timezone.utc)
        }
        
        result = app.users_collection.insert_one(user_data)
        user_id = str(result.inserted_id)
        
        # Create Token
        token = jwt.encode({
            'user_id': user_id,
            'email': email,
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
        }, os.getenv('JWT_SECRET', 'your_fallback_secret'), algorithm='HS256')
        
        return jsonify({
            'success': True,
            'token': token,
            'user': {'id': user_id, 'email': email, 'displayName': user_data['display_name']}
        }), 201
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json() or {}
        email = data.get('email')
        password = data.get('password')
        
        user = app.users_collection.find_one({'email': email})
        
        if user and pbkdf2_sha256.verify(password, user['password_hash']):
            token = jwt.encode({
                'user_id': str(user['_id']),
                'email': email,
                'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
            }, os.getenv('JWT_SECRET', 'your_fallback_secret'), algorithm='HS256')
            
            return jsonify({
                'success': True,
                'token': token,
                'user': {
                    'id': str(user['_id']),
                    'email': user['email'],
                    'displayName': user.get('display_name', email.split('@')[0])
                }
            }), 200
        
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ============= GEMINI 2.5 FLASH LOGIC =============

def generate_report_with_gemini(query):
    try:
        client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
        config = types.GenerateContentConfig(response_mime_type='application/json')
        
        prompt = f"""Perform a full market research for {query}. 
        Return a single JSON object with these exact keys: 
        'market' (size, growth_trends, opportunities, risks, key_insight), 
        'competitors' (competitors list, gaps, differentiation), 
        'audience' (demographics, psychographics, pain_points, buying_behavior), 
        'content' (platforms, content_pillars, post_ideas, tone_of_voice)."""
        
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt, 
            config=config
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"AI Error: {e}")
        return None

# ============= REPORT ENDPOINTS =============

@app.route('/api/reports/generate', methods=['POST'])
def generate_report():
    data = request.get_json()
    query = data.get('query')
    # Using a helper to get user_id from token (recommended) or use your temp logic
    auth_header = request.headers.get('Authorization')
    
    report_data = generate_report_with_gemini(query)
    if not report_data:
        return jsonify({'success': False, 'message': 'AI failed'}), 500
    
    report_doc = {
        "user_id": data.get('user_id', 'temp_user_123'),
        "query": query,
        **report_data,
        "created_at": datetime.datetime.now(datetime.timezone.utc)
    }
    
    result = app.db.reports.insert_one(report_doc)
    report_doc['_id'] = str(result.inserted_id)
    report_doc['created_at'] = report_doc['created_at'].isoformat()
    
    return jsonify({'success': True, 'report': report_doc}), 201

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)