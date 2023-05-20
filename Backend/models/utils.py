from fastapi.responses import JSONResponse as FastAPIJSONResponse
from typing import Optional
from passlib.context import CryptContext

class JSONResponse(FastAPIJSONResponse):
    def modify(self,content:Optional[dict]={},headers:Optional[dict]={}):
        self.body = self.render(content)
        self.headers.update({'content-length':str(len(self.body))})
        self.headers.update(headers)
        
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verifyPassword(plain_password, hashed_password):
        return pwd_context.verify(plain_password, hashed_password)

def hashPassword(password):
        return pwd_context.hash(password)