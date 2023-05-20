from pydantic import BaseSettings
from mongoengine import *

class Settings(BaseSettings):
    CLUSTER_URL: str
    DATABASE_NAME: str

    def createConnection(self):
        db = connect(db=self.DATABASE_NAME, host=self.CLUSTER_URL)
        db = db[self.DATABASE_NAME]
        return db

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'

DB = Settings().createConnection()
