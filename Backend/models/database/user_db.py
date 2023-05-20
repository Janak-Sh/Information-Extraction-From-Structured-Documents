from mongoengine import *
from .connection import DB
import uuid
import datetime
import random,string
from ..utils import hashPassword
from .send_email import email

TOKEN_CHARACTERS=string.ascii_uppercase+string.ascii_lowercase + string.digits

class SessionCookies(Document):
    session_id=StringField()
    user_id=StringField()
    _id=StringField()
    def save(self):
        self._id=str(uuid.uuid1())
        super().save()
        return {
            "session_id":self.session_id,
            "user_id":self.user_id
        }
    
   
class User(Document):
    _id=StringField()
    email=StringField()
    password=StringField()
    userName=StringField()
    apiServices=DictField()
    apikey=StringField(default=''.join(random.choice(TOKEN_CHARACTERS) for _ in range(10)))

    def save(self):
        if not self._id:
            self._id=str(uuid.uuid1())
            self.password=hashPassword(self.password)
            self.apikey = ''.join(random.choice(TOKEN_CHARACTERS) for _ in range(10))
        super().save()
        return self._id
    
    def update_apiservices(self, api):
        self.apiServices[api["name"]]["status"] = not self.apiServices[api["name"]]["status"]
        self.save()
        return self.apiServices
    
    def generate_apikey(self):
        self.apikey=''.join(random.choice(TOKEN_CHARACTERS) for _ in range(10))
        self.save()
        return self.apikey


class ResetPasswordToken(Document):
    token=StringField()
    email=StringField()
    time=DateTimeField(default=datetime.datetime.utcnow)
    _id=StringField()
    def save(self):
        self._id=str(uuid.uuid1())
        self.token=''.join(random.choice(TOKEN_CHARACTERS) for _ in range(5))
        self.time=datetime.datetime.now()+datetime.timedelta(seconds=1800)
        super().save()
        email.send_email(self.email,f"Your password reset token for {self.email} is {self.token}")