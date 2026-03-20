import datetime

class User:
    def __init__(self, email, password_hash, display_name=None):
        self.email = email
        self.password_hash = password_hash
        self.display_name = display_name
        self.created_at = datetime.datetime.utcnow()
        self._id = None
    
    def to_dict(self):
        return {
            'email': self.email,
            'password_hash': self.password_hash,
            'display_name': self.display_name,
            'created_at': self.created_at
        }
    
    @staticmethod
    def from_dict(data):
        user = User(
            email=data['email'],
            password_hash=data['password_hash'],
            display_name=data.get('display_name')
        )
        user.created_at = data.get('created_at', datetime.datetime.utcnow())
        user._id = data.get('_id')
        return user