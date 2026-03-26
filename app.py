from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import os
from pymongo import MongoClient
import datetime
import jwt
from passlib.hash import pbkdf2_sha256
from user import User
from bson import ObjectId
import google.generativeai as genai
import json

load_dotenv()

app = Flask(__name__)
CORS(app)

print("Starting ARIA Backend...")
print("Connecting to MongoDB...")

try:
    mongodb_uri = os.getenv('MONGODB_URI')
    if not mongodb_uri:
        print("MONGODB_URI not found")
        app.db = None
    else:
        client = MongoClient(mongodb_uri)
        db = client.get_database('aria_db')
        app.db = db
        app.users_collection = db.users
        app.reports_collection = db.reports
        print("Connected to MongoDB!")
except Exception as e:
    print(f"MongoDB error: {e}")
    app.db = None

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
        new_user = User(email, password_hash, display_name)
        result = app.users_collection.insert_one(new_user.to_dict())
        token = jwt.encode({
            'user_id': str(result.inserted_id),
            'email': email,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
        }, os.getenv('JWT_SECRET', 'my-secret-key'), algorithm='HS256')
        return jsonify({
            'success': True,
            'token': token,
            'user': {'id': str(result.inserted_id), 'email': email, 'displayName': display_name}
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
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
        if pbkdf2_sha256.verify(password, user['password_hash']):
            token = jwt.encode({
                'user_id': str(user['_id']),
                'email': email,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
            }, os.getenv('JWT_SECRET', 'my-secret-key'), algorithm='HS256')
            return jsonify({
                'success': True,
                'token': token,
                'user': {'id': str(user['_id']), 'email': user['email'], 'displayName': user.get('display_name', email.split('@')[0])}
            }), 200
        else:
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/auth/test', methods=['GET'])
def test_auth():
    return jsonify({'success': True, 'message': 'Auth routes working!'})

def extract_json(text):
    try:
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end != 0:
            return json.loads(text[start:end])
        return {}
    except:
        return {}

def get_fallback_report(query):
    return {
        "market": {"market_size": f"Market for {query}", "growth_trends": ["Trend 1", "Trend 2"], "opportunities": ["Opp 1"], "risks": ["Risk 1"], "key_insight": "Insight"},
        "competitors": {"competitors": [{"name": "Comp A", "strength": "Strong", "weakness": "Price", "position": "Leader"}], "gaps": ["Gap"], "differentiation": "Differentiate"},
        "audience": {"demographics": {"age_range": "25-40"}, "psychographics": {}, "pain_points": [], "buying_behavior": {}},
        "content": {"platforms": ["Instagram"], "content_pillars": ["Pillar"], "post_ideas": ["Idea"], "tone_of_voice": "Friendly", "content_mix": {}}
    }

def generate_report_with_gemini(query):
    try:
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            return get_fallback_report(query)
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-pro')
        market_prompt = f"Market analysis for {query}. Return JSON with market_size, growth_trends, opportunities, risks, key_insight."
        market_resp = model.generate_content(market_prompt)
        market_data = extract_json(market_resp.text)
        return {
            "market": market_data,
            "competitors": {},
            "audience": {},
            "content": {}
        }
    except Exception as e:
        print(f"Gemini error: {e}")
        return get_fallback_report(query)

@app.route('/api/reports/generate', methods=['POST'])
def generate_report_endpoint():
    try:
        data = request.get_json()
        if not data or not data.get('query'):
            return jsonify({'success': False, 'message': 'Query required'}), 400
        query = data.get('query')
        report_data = generate_report_with_gemini(query)
        report = {
            "user_id": "temp_user",
            "query": query,
            "market": report_data.get("market"),
            "competitors": report_data.get("competitors"),
            "audience": report_data.get("audience"),
            "content": report_data.get("content"),
            "created_at": datetime.datetime.utcnow()
        }
        result = app.db.reports.insert_one(report)
        return jsonify({'success': True, 'report': {'id': str(result.inserted_id), 'query': query, **report_data}}), 201
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/reports', methods=['GET'])
def get_all_reports():
    try:
        reports = list(app.db.reports.find({'user_id': 'temp_user'}).sort('created_at', -1))
        for r in reports:
            r['_id'] = str(r['_id'])
            r['created_at'] = r['created_at'].isoformat()
        return jsonify({'success': True, 'reports': reports}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/reports/test', methods=['GET'])
def test_reports():
    return jsonify({'success': True, 'message': 'Reports working!'})

@app.route('/')
def home():
    return jsonify({"message": "ARIA API running", "database": "connected" if app.db else "disconnected"})

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "database": "connected" if app.db else "disconnected"})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"Server ready on http://localhost:{port}")
    app.run(debug=True, host='0.0.0.0', port=port)