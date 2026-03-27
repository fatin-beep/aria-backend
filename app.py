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

# NEW: Correct imports for the modern Google GenAI package
from google import genai
from google.genai import types

load_dotenv()

app = Flask(__name__)
CORS(app)

# MongoDB Connection
try:
    mongodb_uri = os.getenv('MONGODB_URI')
    if not mongodb_uri:
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

# ============= AUTH ROUTES (RESTORED TO ORIGINAL) =============

@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json() or {}
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password required'}), 400
        
        display_name = data.get('displayName') or email.split('@')[0]
        
        existing = app.users_collection.find_one({'email': email})
        if existing:
            return jsonify({'success': False, 'message': 'User already exists'}), 400
        
        password_hash = pbkdf2_sha256.hash(password)
        # Using a simple dict since I don't have your User class file, 
        # but following your 'to_dict' structure
        new_user = {
            "email": email,
            "password_hash": password_hash,
            "display_name": display_name,
            "created_at": datetime.datetime.utcnow()
        }
        result = app.users_collection.insert_one(new_user)
        
        token = jwt.encode(
            {
                'user_id': str(result.inserted_id),
                'email': email,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
            },
            os.getenv('JWT_SECRET', 'my-secret-key'),
            algorithm='HS256'
        )
        
        return jsonify({
            'success': True,
            'message': 'User registered successfully',
            'token': token,
            'user': {
                'id': str(result.inserted_id),
                'email': email,
                'displayName': display_name
            }
        }), 201
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json() or {}
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password required'}), 400
        
        user = app.users_collection.find_one({'email': email})
        
        if not user:
            return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
        
        if pbkdf2_sha256.verify(password, user['password_hash']):
            token = jwt.encode(
                {
                    'user_id': str(user['_id']),
                    'email': email,
                    'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
                },
                os.getenv('JWT_SECRET', 'my-secret-key'),
                algorithm='HS256'
            )
            
            return jsonify({
                'success': True,
                'message': 'Login successful',
                'token': token,
                'user': {
                    'id': str(user['_id']),
                    'email': user['email'],
                    'displayName': user.get('display_name', email.split('@')[0])
                }
            }), 200
        else:
            return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ============= GEMINI 2.5 FLASH (UPDATED) =============

def generate_report_with_gemini(query):
    try:
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            return None
        
        client = genai.Client(api_key=api_key)
        
        # We use GenerateContentConfig to ensure Gemini 2.5 Flash sends clean JSON
        config = types.GenerateContentConfig(
            response_mime_type='application/json'
        )

        # Simplified prompt to get all data in one go for speed and reliability
        prompt = f"""Analyze market for: {query}. Return JSON exactly:
        {{
            "market": {{"market_size": "", "growth_trends": [], "opportunities": [], "risks": [], "key_insight": ""}},
            "competitors": {{"competitors": [], "gaps": [], "differentiation": ""}},
            "audience": {{"demographics": {{}}, "psychographics": {{}}, "pain_points": [], "buying_behavior": {{}}}},
            "content": {{"platforms": [], "content_pillars": [], "post_ideas": [], "tone_of_voice": "", "content_mix": {{}}}}
        }}"""
        
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt, 
            config=config
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Gemini API error: {e}")
        return None

# ============= REPORTS ENDPOINT =============

@app.route('/api/reports/generate', methods=['POST'])
def generate_report_endpoint():
    try:
        data = request.get_json()
        query = data.get('query')
        if not query:
            return jsonify({'success': False, 'message': 'Query required'}), 400
        
        report_data = generate_report_with_gemini(query)
        if not report_data:
            return jsonify({'success': False, 'message': 'AI failed'}), 500
        
        report = {
            "user_id": "temp_user_123",
            "query": query,
            **report_data,
            "created_at": datetime.datetime.utcnow()
        }
        
        result = app.db.reports.insert_one(report)
        
        return jsonify({
            'success': True,
            'report': {
                'id': str(result.inserted_id),
                'query': query,
                **report_data,
                'created_at': report['created_at'].isoformat()
            }
        }), 201
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ... Rest of your GET routes ...

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))