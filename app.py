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
        # Connect to MongoDB
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
        
        # Check if user exists
        existing = app.users_collection.find_one({'email': email})
        if existing:
            return jsonify({'success': False, 'message': 'User already exists'}), 400
        
        # Hash password
        password_hash = pbkdf2_sha256.hash(password)
        
        # Create user
        new_user = User(email, password_hash, display_name)
        result = app.users_collection.insert_one(new_user.to_dict())
        
        # Create token
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
        
        # Find user
        user = app.users_collection.find_one({'email': email})
        
        if not user:
            return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
        
        # Check password
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

# ============= REPORT ROUTES =============

# Temporary AI function (Abdullah will replace this)
def generate_report(query):
    """Temporary function - Abdullah will replace with AI"""
    return {
        "market": {
            "market_size": "Sample market size for: " + query,
            "growth_trends": ["Trend 1", "Trend 2", "Trend 3"],
            "opportunities": ["Opportunity 1", "Opportunity 2"],
            "risks": ["Risk 1", "Risk 2"],
            "key_insight": "This is a sample key insight"
        },
        "competitors": {
            "competitors": [
                {"name": "Competitor A", "strength": "Strong brand", "weakness": "High price", "position": "Premium"}
            ],
            "gaps": ["Gap 1", "Gap 2"],
            "differentiation": "Stand out by offering better value"
        },
        "audience": {
            "demographics": {"age_range": "25-40", "location": "Urban", "income": "Middle to high"},
            "psychographics": {"values": ["Quality", "Innovation"], "motivations": ["Efficiency"]},
            "pain_points": ["Pain point 1", "Pain point 2"],
            "buying_behavior": {"discovery": ["Social media"], "evaluation": ["Reviews"]}
        },
        "content": {
            "platforms": ["Instagram", "LinkedIn"],
            "content_pillars": ["Education", "Inspiration"],
            "post_ideas": ["Idea 1", "Idea 2", "Idea 3"],
            "tone_of_voice": "Professional and friendly",
            "content_mix": {"video": "40%", "carousel": "30%", "short_form": "30%"}
        }
    }

# Helper function to create report object
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

# ============= REPORT ENDPOINTS =============

@app.route('/api/reports/generate', methods=['POST'])
def generate_report_endpoint():
    """Generate a new report using AI"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        query = data.get('query')
        
        if not query:
            return jsonify({'success': False, 'message': 'Query is required'}), 400
        
        # Call the AI function
        report_data = generate_report(query)
        
        # Create report object
        # TODO: Replace with actual user_id after auth
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
        # TODO: Replace with actual user_id from token
        temp_user_id = "temp_user_123"
        
        # Get reports from database
        reports = list(app.db.reports.find({'user_id': temp_user_id}).sort('created_at', -1))
        
        # Convert ObjectId to string
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
        # TODO: Replace with actual user_id from token
        temp_user_id = "temp_user_123"
        
        # Get report from database
        report = app.db.reports.find_one({
            '_id': ObjectId(report_id),
            'user_id': temp_user_id
        })
        
        if not report:
            return jsonify({'success': False, 'message': 'Report not found'}), 404
        
        # Convert ObjectId to string
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
    print("="*50)
    app.run(debug=True, host='0.0.0.0', port=port)