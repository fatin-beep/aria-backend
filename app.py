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

# Load environment variables
load_dotenv()

# Create Flask app
app = Flask(__name__)
CORS(app)

print("🚀 Starting ARIA Backend...")
print("🔄 Connecting to MongoDB...")

# MongoDB Connection
try:
    mongodb_uri = os.getenv('MONGODB_URI')
    
    if not mongodb_uri:
        print("❌ MONGODB_URI not found in .env file")
        app.db = None
    else:
        print("✅ Found MONGODB_URI in .env file")
        client = MongoClient(mongodb_uri)
        db = client.get_database('aria_db')
        app.db = db
        app.users_collection = db.users
        app.reports_collection = db.reports
        print("✅ Connected to MongoDB successfully!")
        
except Exception as e:
    print(f"❌ MongoDB connection failed: {e}")
    app.db = None

# ============= AUTH ROUTES =============

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        display_name = data.get('displayName', email.split('@')[0])
        
        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password required'}), 400
        
        existing = app.users_collection.find_one({'email': email})
        if existing:
            return jsonify({'success': False, 'message': 'User already exists'}), 400
        
        password_hash = pbkdf2_sha256.hash(password)
        new_user = User(email, password_hash, display_name)
        result = app.users_collection.insert_one(new_user.to_dict())
        
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
    """Login existing user"""
    try:
        data = request.get_json()
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

@app.route('/api/auth/test', methods=['GET'])
def test_auth():
    return jsonify({
        'success': True,
        'message': 'Auth routes are working!',
        'endpoints': {
            'register': 'POST /api/auth/register',
            'login': 'POST /api/auth/login'
        }
    })

# ============= GEMINI AI FUNCTION =============

def extract_json(text):
    """Extract JSON from AI response"""
    try:
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end != 0:
            return json.loads(text[start:end])
        return {}
    except:
        return {}

def generate_report_with_gemini(query):
    """Generate report using Google Gemini AI"""
    try:
        api_key = os.getenv('GEMINI_API_KEY')
        
        if not api_key:
            print("❌ GEMINI_API_KEY not found")
            return get_fallback_report(query)
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.0-pro')
        
        # Market Analysis
        market_prompt = f"""You are a market research expert. Analyze this market: {query}
        Return ONLY JSON in this exact format:
        {{
            "market_size": "estimate with context",
            "growth_trends": ["trend1", "trend2", "trend3"],
            "opportunities": ["opp1", "opp2", "opp3"],
            "risks": ["risk1", "risk2", "risk3"],
            "key_insight": "most important insight"
        }}"""
        
        market_response = model.generate_content(market_prompt)
        market_data = extract_json(market_response.text)
        
        # Competitor Analysis
        competitor_prompt = f"""You are a competitive analyst. Identify competitors for: {query}
        Return ONLY JSON in this exact format:
        {{
            "competitors": [
                {{"name": "name", "strength": "strength", "weakness": "weakness", "position": "position"}}
            ],
            "gaps": ["gap1", "gap2"],
            "differentiation": "how to stand out"
        }}"""
        
        competitor_response = model.generate_content(competitor_prompt)
        competitor_data = extract_json(competitor_response.text)
        
        # Audience Profile
        audience_prompt = f"""You are a consumer psychologist. Profile audience for: {query}
        Return ONLY JSON in this exact format:
        {{
            "demographics": {{"age_range": "", "location": "", "income": "", "profession": ""}},
            "psychographics": {{"values": [], "motivations": [], "aspirations": []}},
            "pain_points": [],
            "buying_behavior": {{"discovery": [], "evaluation": [], "purchase": []}}
        }}"""
        
        audience_response = model.generate_content(audience_prompt)
        audience_data = extract_json(audience_response.text)
        
        # Content Strategy
        content_prompt = f"""You are a content strategist. Create strategy for: {query}
        Return ONLY JSON in this exact format:
        {{
            "platforms": ["platform1", "platform2"],
            "content_pillars": ["pillar1", "pillar2", "pillar3"],
            "post_ideas": ["idea1", "idea2", "idea3", "idea4", "idea5"],
            "tone_of_voice": "description",
            "content_mix": {{"video": "40%", "carousel": "30%", "short_form": "30%"}}
        }}"""
        
        content_response = model.generate_content(content_prompt)
        content_data = extract_json(content_response.text)
        
        return {
            "market": market_data,
            "competitors": competitor_data,
            "audience": audience_data,
            "content": content_data
        }
        
    except Exception as e:
        print(f"Gemini API error: {e}")
        return get_fallback_report(query)

def get_fallback_report(query):
    """Fallback report when Gemini fails"""
    return {
        "market": {
            "market_size": f"Market analysis for {query}",
            "growth_trends": ["Growing demand", "Digital transformation", "Consumer awareness"],
            "opportunities": ["Untapped segments", "Innovation gap", "Partnership potential"],
            "risks": ["Competition", "Regulatory changes", "Economic factors"],
            "key_insight": f"{query} shows strong growth potential"
        },
        "competitors": {
            "competitors": [
                {"name": "Competitor A", "strength": "Market presence", "weakness": "High pricing", "position": "Premium"}
            ],
            "gaps": ["Better pricing", "More features", "Better support"],
            "differentiation": "Focus on user experience and affordability"
        },
        "audience": {
            "demographics": {"age_range": "25-40", "location": "Urban areas", "income": "Middle to high", "profession": "Professionals"},
            "psychographics": {"values": ["Quality", "Innovation"], "motivations": ["Efficiency"], "aspirations": ["Success"]},
            "pain_points": ["Time consuming", "Complex solutions", "High costs"],
            "buying_behavior": {"discovery": ["Social media"], "evaluation": ["Reviews"], "purchase": ["Online"]}
        },
        "content": {
            "platforms": ["Instagram", "LinkedIn", "Twitter"],
            "content_pillars": ["Education", "Inspiration", "How-to guides"],
            "post_ideas": ["Tip 1", "Tip 2", "Tip 3", "Tip 4", "Tip 5"],
            "tone_of_voice": "Professional and friendly",
            "content_mix": {"video": "40%", "carousel": "30%", "short_form": "30%"}
        }
    }

# ============= REPORT ENDPOINTS =============

def create_report_object(user_id, query, report_data):
    """Create a report document for MongoDB"""
    return {
        "user_id": user_id,
        "query": query,
        "market": report_data.get("market", {}),
        "competitors": report_data.get("competitors", {}),
        "audience": report_data.get("audience", {}),
        "content": report_data.get("content", {}),
        "created_at": datetime.datetime.utcnow()
    }

@app.route('/api/reports/generate', methods=['POST'])
def generate_report_endpoint():
    """Generate a new report using Gemini AI"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        query = data.get('query')
        
        if not query:
            return jsonify({'success': False, 'message': 'Query is required'}), 400
        
        # Call Gemini AI to generate report
        report_data = generate_report_with_gemini(query)
        
        # Create report object
        temp_user_id = "temp_user_123"
        report = create_report_object(temp_user_id, query, report_data)
        
        # Save to MongoDB
        result = app.db.reports.insert_one(report)
        
        return jsonify({
            'success': True,
            'message': 'Report generated successfully',
            'report': {
                'id': str(result.inserted_id),
                'query': query,
                'market': report_data.get('market'),
                'competitors': report_data.get('competitors'),
                'audience': report_data.get('audience'),
                'content': report_data.get('content'),
                'created_at': report['created_at'].isoformat()
            }
        }), 201
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/reports', methods=['GET'])
def get_all_reports():
    """Get all reports for the user"""
    try:
        temp_user_id = "temp_user_123"
        
        reports = list(app.db.reports.find({'user_id': temp_user_id}).sort('created_at', -1))
        
        for report in reports:
            report['_id'] = str(report['_id'])
            report['created_at'] = report['created_at'].isoformat()
        
        return jsonify({
            'success': True,
            'reports': reports
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/reports/<report_id>', methods=['GET'])
def get_single_report(report_id):
    """Get a single report by ID"""
    try:
        temp_user_id = "temp_user_123"
        
        report = app.db.reports.find_one({
            '_id': ObjectId(report_id),
            'user_id': temp_user_id
        })
        
        if not report:
            return jsonify({'success': False, 'message': 'Report not found'}), 404
        
        report['_id'] = str(report['_id'])
        report['created_at'] = report['created_at'].isoformat()
        
        return jsonify({
            'success': True,
            'report': report
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/reports/test', methods=['GET'])
def test_reports():
    """Test route to check if reports endpoints are working"""
    return jsonify({
        'success': True,
        'message': 'Reports endpoints are working!',
        'endpoints': {
            'generate': 'POST /api/reports/generate',
            'all_reports': 'GET /api/reports',
            'single_report': 'GET /api/reports/:id'
        }
    })

# ============= BASIC ROUTES =============

@app.route('/')
def home():
    return jsonify({
        "message": "ARIA API is running",
        "version": "1.0",
        "status": "online",
        "database": "connected" if app.db is not None else "disconnected"
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "database": "connected" if app.db is not None else "disconnected"
    })

@app.route('/api/test')
def test_api():
    return jsonify({
        "success": True,
        "message": "API is working!",
        "data": {
            "server_time": datetime.datetime.utcnow().isoformat(),
            "database_status": "connected" if app.db is not None else "disconnected"
        }
    })

# ============= START SERVER =============

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print("="*50)
    print(f"✅ Server is ready!")
    print(f"📍 Local URL: http://localhost:{port}")
    print(f"💾 Database: {'✅ Connected' if app.db is not None else '❌ Disconnected'}")
    print("📝 Auth endpoints: /api/auth/register, /api/auth/login")
    print("📝 Reports endpoints: /api/reports/generate, /api/reports, /api/reports/:id")
    print("🤖 Gemini AI: Enabled")
    print("="*50)
    app.run(debug=True, host='0.0.0.0', port=port)