import threading
import time
import sys
import os
import httpx
import uvicorn

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from database import SessionLocal
from models.user import User

class ServerThread(threading.Thread):
    def __init__(self, app, host='127.0.0.1', port=8000):
        super().__init__()
        self.config = uvicorn.Config(app, host=host, port=port, log_level='warning')
        self.server = uvicorn.Server(self.config)

    def run(self):
        self.server.run()

    def shutdown(self):
        self.server.should_exit = True

if __name__ == '__main__':
    # Clean up test user
    db = SessionLocal()
    db.query(User).filter(User.email.in_(['live_test@example.com', 'dup_test@example.com'])).delete()
    db.commit()
    db.close()

    server = ServerThread(app, port=8000)
    server.daemon = True
    server.start()
    time.sleep(1.5)

    try:
        # 1. Test registration
        res = httpx.post('http://127.0.0.1:8000/api/auth/register', json={
            'name': 'Live Test User',
            'email': 'live_test@example.com',
            'password': 'password123'
        }, headers={'Origin': 'http://localhost:3000'})
        print('1. Register status:', res.status_code)
        print('   Register response:', res.json())
        print('   CORS header:', res.headers.get('access-control-allow-origin'))
        token = res.json().get('access_token')

        # 2. Test duplicate email
        res_dup = httpx.post('http://127.0.0.1:8000/api/auth/register', json={
            'name': 'Duplicate User',
            'email': 'live_test@example.com',
            'password': 'password123'
        }, headers={'Origin': 'http://localhost:3000'})
        print('2. Duplicate register status:', res_dup.status_code)
        print('   Duplicate error:', res_dup.json())
        print('   CORS header:', res_dup.headers.get('access-control-allow-origin'))

        # 3. Test login
        res_login = httpx.post('http://127.0.0.1:8000/api/auth/login', json={
            'email': 'live_test@example.com',
            'password': 'password123'
        }, headers={'Origin': 'http://localhost:3000'})
        print('3. Login status:', res_login.status_code)
        print('   Login user:', res_login.json().get('user', {}).get('email'))

        # 4. Test invalid password login
        res_bad_pw = httpx.post('http://127.0.0.1:8000/api/auth/login', json={
            'email': 'live_test@example.com',
            'password': 'wrongpassword'
        }, headers={'Origin': 'http://localhost:3000'})
        print('4. Bad password status:', res_bad_pw.status_code)

        # 5. Test GET /api/auth/me
        res_me = httpx.get('http://127.0.0.1:8000/api/auth/me', headers={
            'Authorization': f'Bearer {token}',
            'Origin': 'http://localhost:3000'
        })
        print('5. GET /me status:', res_me.status_code)
        print('   GET /me data:', res_me.json())

        # 6. Test unauthenticated /api/auth/me
        res_unauth = httpx.get('http://127.0.0.1:8000/api/auth/me', headers={'Origin': 'http://localhost:3000'})
        print('6. Unauthenticated /me status:', res_unauth.status_code)

        # 7. Test logout
        res_logout = httpx.post('http://127.0.0.1:8000/api/auth/logout', headers={
            'Authorization': f'Bearer {token}',
            'Origin': 'http://localhost:3000'
        })
        print('7. Logout status:', res_logout.status_code)
        print('   Logout data:', res_logout.json())

    finally:
        server.shutdown()
        # Clean up
        db = SessionLocal()
        db.query(User).filter(User.email.in_(['live_test@example.com', 'dup_test@example.com'])).delete()
        db.commit()
        db.close()
