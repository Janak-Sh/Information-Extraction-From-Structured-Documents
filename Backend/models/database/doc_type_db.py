from mongoengine import *
from .connection import DB
import uuid
import datetime

class DriveMap(Document):
    owner=StringField()
    drive_id=StringField()
    gdrive=StringField()
    def save(self):
        self.gdrive=f"https://drive.google.com/drive/folders/{self.drive_id}?usp=sharing"
        super().save()

class DocumentType(Document):
    name = StringField()
    owner=StringField()
    _id = StringField(primary_key=True)
    fields = ListField(DictField())
    task_type=StringField()
    model=StringField()
    timestamp=LongField()
    modified=LongField()
 
    def save(self):
        if(not self._id):
            self._id = str(uuid.uuid1())
            self.timestamp = int(datetime.datetime.now().timestamp())
        
        self.modified = int(datetime.datetime.now().timestamp())
        for i in range(len(self.fields)):
            if('id' not in self.fields[i].keys()):
                self.fields[i]['id']=uuid.uuid1()
        
            for j in list(self.fields[i].keys()):    
                if(j not in ["name","data_type","id"]):
                    self.fields[i].pop(j)
            
        super().save()
        return self._id
    

class   ModelInformation(Document):
    created_at = LongField()
    doc_type = StringField()
    _id = StringField(primary_key=True)
    owner = StringField()
    path = StringField()
    metrics = DictField()
    accuracy = DictField()
    train_split = FloatField()
    batch = IntField()
    label_dict = DictField()
    version = StringField()
    epochs = IntField(min_value=1)
    trained_epochs = IntField()
    status = StringField()

    def save(self):
        if not self._id:
            self._id = str(uuid.uuid1())
            self.status = "running"
            self.created_at = int(datetime.datetime.now().timestamp())
            if self.path is None:
                self.path = f"{self.owner}/{self.doc_type}/{self._id}/{self.version}"
        super().save()
        return self._id

    def get_metadata(self):
        return {
            "id": self._id,
            "created_at": self.created_at,
            "doc_type": self.doc_type,
            "owner": self.owner,
            "path": self.path,
            "epochs": self.epochs,
            "train_split": self.train_split,
            "label_dict": self.label_dict,
            "accuracy": self.accuracy,
            "metrics": self.metrics,
            "version": self.version,
            "batch": self.batch,
            "status": self.status,
            "trained_epochs": self.trained_epochs
        }

    def add_model_path(self, path):
        self.path = path
        super().save()