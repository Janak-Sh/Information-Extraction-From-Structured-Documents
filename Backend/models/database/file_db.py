from mongoengine import *
from .connection import DB
import uuid
from datetime import datetime, timedelta
import json
import os
import requests


class DocumentType(Document):
    name = StringField(primary_key=True)
    model_type = StringField()
    description = StringField()
    fields = ListField(StringField())


class Files(Document):
    status_code = IntField()
    owner = StringField()
    path = StringField()
    status = ListField(StringField(max_length=100))
    media_type = StringField()
    doc_type = StringField()
    _id = StringField(primary_key=True)
    json = StringField()
    timestamp = LongField()

    def statusUpdate(self, msg):
        if (isinstance(msg, list)):
            self.status.extend(msg)
        else:
            self.status.append(msg)
        super().save()

    def save(self):
        self.status_code = 202
        self._id = str(uuid.uuid1())
        self.doc_type = None
        self.timestamp = int(datetime.now().timestamp())
        self.statusUpdate(
            [f"Document assigned with an id of {self._id}"])
        return self._id

    def delete(self):
        try:
            os.remove(self.path)
        except:
            pass
        super().delete()

    def setType(self, doc_type):
        self.statusUpdate(["Classifying the form type."])
        self.doc_type = doc_type
        self.statusUpdate(
            [f"Image classifed as {doc_type}", "Starting the data extraction."])

    def statusCodeUpdate(self, code):
        self.status_code = code
        self.statusUpdate([f"Status code updated to {code}"])

    def dataUpdate(self, data):
        self.json = json.dumps(data)
        self.statusUpdate([f"Data extraction complete"])


class AnnotationFiles(Document):
    status = StringField()
    filename = StringField()
    _id = StringField(primary_key=True)
    gdrive=StringField()
    doc_type_id = StringField()
    status_code = IntField()
    owner = StringField()
    path = StringField()
    ocr = ListField()
    timestamp = LongField()
    modified = LongField()
    media_type = StringField()
    annotation = ListField(DictField())
    width = IntField()
    height = IntField()

    def save(self):
        if not self._id:
            self.annotation = []
            self.ocr = []
            self.status_code = 202
            self.status = "Reviewing."
            self._id = str(uuid.uuid1())
            self.timestamp = int(datetime.now().timestamp())
        self.modified = int(datetime.now().timestamp())

        super().save()
        return self._id

    def get_metadata(self):
        return {
            "image_id": self._id,
            "timestamp": self.timestamp,
            "doc_type_id": self.doc_type_id,
            "status": self.status,
            "filename": self.filename,
            "width": self.width,
            "height": self.height,
            "owner": self.owner
        }

    def add_ocr(self, ocr):
        self.ocr = ocr
        self.status_code = 200
        super().save()

    def add_annotation(self, annotations):
        self.annotation = annotations
        self.save()

    def update_metadata(self, metadata):
        self.status = metadata["status"]
        self.modified = int(datetime.now().timestamp())
        super().save()

    def add_gdrive(self, gdrive):
        self.gdrive=gdrive
        super().save()

    def delete(self):
        try:
            os.remove(self.path)
        except:
            pass
        super().delete()


class GToken(Document):
    refresh = StringField()
    access = StringField()
    exp = StringField()
    owner = StringField()

    def save(self, expires):
        self.exp = datetime.now()+timedelta(seconds=int(expires*0.8))
        self.exp = self.exp.isoformat()
        super().save()

    def get_token(self):
        config = {
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "77719607766-lmtultpfa6b89gr69c5a2sm8j997koc3.apps.googleusercontent.com",
            "client_secret": "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",
            "redirect_uri": 'http://localhost:8000/drive/callback/',
        }
        if (datetime.now() < datetime.fromisoformat(self.exp)):
            return self.access
        else:
            config['refresh_token'] = self.refresh
            config['grant_type'] = 'refresh_token'
            response = requests.post(config['token_uri'], json=config).json()
            self.access = response['access_token']
            self.save(response["expires_in"])
            return self.access
