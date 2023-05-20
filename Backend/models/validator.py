from pydantic import BaseModel,BaseSettings
from mongoengine import *
from .database.user_db import User, SessionCookies, ResetPasswordToken
import uuid
import datetime
import shutil
from fastapi.requests import Request as FastAPIRequest
from .utils import JSONResponse, verifyPassword, hashPassword
from typing import Optional,List,Dict
from pathlib import Path
from .database.file_db import Files,AnnotationFiles,GToken
import cv2
import os
# from fastapi.logger import logger
from loguru import logger
from .database.doc_type_db import DocumentType, ModelInformation
from copy import copy
from models.database.doc_type_db import DriveMap
import requests
import pdf2image

class Config(BaseSettings):
    FILES: str
    DOMAIN: str
    def __init__(self):
        super().__init__()

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'


config = Config()
config = {
    "DOMAIN": config.DOMAIN,
    "FILES": config.FILES
}

CLEAR_COOKIE_RESPONSE = JSONResponse({})
CLEAR_COOKIE_RESPONSE.delete_cookie(key="session_id")
CLEAR_COOKIE_RESPONSE.delete_cookie(key="user_id")


class Session(FastAPIRequest):
    isValid: bool = False
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    session: Optional[SessionCookies] = None

    def __init__(self, request: FastAPIRequest):
        super().__init__(request)

        try:
            self.session_id = self.cookies['session_id']
        except:
            self.session_id = None

        try:
            self.user_id = self.cookies['user_id']
        except:
            self.user_id = None

        if (self.user_id and self.session_id):
            self.session = SessionCookies.objects(
                session_id=self.session_id, user_id=self.user_id)
            if (self.session):
                if (self.session[0].session_id == self.session_id and self.session[0].user_id == self.user_id):
                    self.isValid = True
                else:
                    logger.info(
                        (f"{__name__} deleting session-{self.session_id} of user-{self.user_id}"))
                    self.session.delete()

    def isAuthenticated(self, required: bool = True):
        if (self.isValid):
            return True, JSONResponse({})
        else:
            logger.info(
                (f"{__name__} invalid cookies session-{self.session_id} of user-{self.user_id}"))
            if (required):
                CLEAR_COOKIE_RESPONSE.status_code = 401
                CLEAR_COOKIE_RESPONSE.modify(
                    content={"msg": "User not logged in"})
                raise RuntimeError(CLEAR_COOKIE_RESPONSE)
            else:
                CLEAR_COOKIE_RESPONSE.status_code = 200
                return False, CLEAR_COOKIE_RESPONSE

    def logout(self):
        logger.info(
            (f"{__name__} logging out session-{self.session_id} of user-{self.user_id}"))
        if (self.isValid):
            CLEAR_COOKIE_RESPONSE.status_code = 200
            CLEAR_COOKIE_RESPONSE.modify(content={"msg": "User logged out."})
            self.session.delete()
        else:
            CLEAR_COOKIE_RESPONSE.status_code = 400
            CLEAR_COOKIE_RESPONSE.modify(
                content={"msg": "User not logged in."})

        return CLEAR_COOKIE_RESPONSE

    def terminateAllSessions(self):
        logger.info(
            (f"{__name__} terminatig all sessions with session-{self.session_id} of user-{self.user_id}"))
        if (self.isValid):
            SessionCookies.objects(user_id=self.user_id).delete()
            CLEAR_COOKIE_RESPONSE.status_code = 200
            CLEAR_COOKIE_RESPONSE.modify(
                content={"msg": "logged out of all sessions"})
        else:
            CLEAR_COOKIE_RESPONSE.status_code = 400
            CLEAR_COOKIE_RESPONSE.modify(content={"msg": "User not logged in"})

        return CLEAR_COOKIE_RESPONSE


class SignIn(BaseModel):
    # Can be Username or Email
    email: str
    password: str

    def signin(self):
        qset = User.objects(email=self.email)
        if (not qset):
            qset = User.objects(userName=self.email)

        if (not qset):
            logger.info(
                f"{__name__} invalid email or username provided {self.email} failed logging in")
            return JSONResponse(content={
                "emailError": "UserName or Email Doesnt Exist"
            },
                status_code=400
            )
        user = qset[0]
        if (verifyPassword(self.password, user.password)):
            cookies = SessionCookies(session_id=str(
                uuid.uuid1()), user_id=user._id).save()
            response = JSONResponse({"msg": "login successful", "session_id": cookies["session_id"], "user_id": cookies["user_id"], "username": user.userName, "email": user.email})
            response.set_cookie(
                key="session_id", value=cookies["session_id"], domain=config["DOMAIN"], httponly=True)
            response.set_cookie(
                key="user_id", value=cookies["user_id"], domain=config["DOMAIN"], httponly=True)
            logger.info(
                f"{__name__} password valid for  {self.email} successful login.")
            logger.debug(f"{__name__} {user._id} logged in with session {cookies['session_id']}")
            return response
        else:
            logger.info(
                f"{__name__} password not valid for  {self.email} failed login.")
            return JSONResponse(status_code=400, content={"passwordError": "Incorrect Password"})


class CreateUser(SignIn):
    confirm_password: str
    userName: str
    apiServices: Dict = {
    "Google Drive": {
        "status": False,
        "img": "https://upload.wikimedia.org/wikipedia/commons/d/da/Google_Drive_logo.png",
        "detail": "",
        "header": "Your Extracted Json are stored in the URL",
    },
    "Mail Server": {
        "status": False,
        "detail": "aayushshah@gmail.com",
        "header": "Your mailing address for services is",
        "img": "https://mailmeteor.com/logos/assets/PNG/Gmail_Logo_512px.png"
    },
    "Developers Documentation": {
        "status": False,
        "detail": "http://docbite.com/developer/docs",
        "header": "Your Extracted Json are stored in the URL",
        "img": "https://styles.redditmedia.com/t5_22y58b/styles/communityIcon_r5ax236rfw961.png"
    }
    }

    def isValid(self):
        error = {}
        if (self.confirm_password != self.password):
            error['rePasswordError'] = "Password do not match"
        elif (len(self.password) < 5):
            error['passwordError'] = "Password must be grater than 5 characters"

        if (User.objects(email__exact=self.email)):
            error['emailError'] = "The email is already registered"

        if (User.objects(userName__exact=self.userName)):
            error['userNameError'] = "The username is already taken"

        if (error):
            raise RuntimeError(error)

    def save(self):
        try:
            self.isValid()
        except RuntimeError as e:
            response = JSONResponse(
                content=e.args[0],
                status_code=400
            )
            return response
        
        _user = User(
            email=self.email,
            password=self.password,
            userName=self.userName,
            apiServices=self.apiServices
        )
        id = _user.save()
        
        default=ModelInformation.objects(_id="b9fa72b0-c2e4-11ed-bd3c-d5eb3b9ad62b").first()
        model=ModelInformation(doc_type=default.doc_type,owner=id,path=default.path,accuracy=default.accuracy,train_split=default.train_split,label_dict=default.label_dict,version=default.version)
        model.save()
        
        default=DocumentType.objects(_id=default.doc_type).first()
        model=DocumentType(owner=id,name=default.name,fields=default.fields,task_type=default.task_type,model=model._id)
        model.save()

        folder_id = self.get_folder_id(owner=id)
        _user.apiServices["Google Drive"]["detail"] = f"https://drive.google.com/drive/folders/{folder_id}?usp=sharing"
        _user.save()
        
        logger.info(f"{__name__} user created successfully with user id {id}")
        cookies = SessionCookies(session_id=str(
            uuid.uuid1()), user_id=id).save()
        response = JSONResponse({"msg": "Account Successfully Created", "success": True})
        # response.set_cookie(
        #     key="session_id", value=cookies["session_id"], domain=config["DOMAIN"], httponly=True)
        # response.set_cookie(
        #     key="user_id", value=cookies["user_id"], domain=config["DOMAIN"], httponly=True)
        return response
    
    def get_folder_id(self, owner):
        folder_id=DriveMap.objects(owner=owner).first()
        token=(GToken.objects().first()).get_token()
        headers={
                "Authorization": "Bearer " + (GToken.objects().first()).get_token()
            }
        logger.info(f"Existng drive folder of {owner} not found.") 
        response = requests.post(
            'https://www.googleapis.com/drive/v3/files',
            headers=headers,
            json={
                'name': owner, 
                'mimeType': 'application/vnd.google-apps.folder'
            }
        )
        folder_id=response.json()['id']
        params = {
            'role': 'reader',
            'type': 'anyone',
        }
        permission_url = f'https://www.googleapis.com/drive/v2/files/{folder_id}/permissions'
        response = requests.post(permission_url,headers=headers,json=params)
        DriveMap(owner=owner,drive_id=folder_id).save()

        return folder_id


class ForgotPassword(BaseModel):
    email: str

    def InitiatePasswordReset(self):
        user = User.objects(email=self.email).count()
        if (not user):
            return JSONResponse(status_code=400, content={"emailError": "User with that email doesnt exist"})

        ResetPasswordToken(email=self.email).save()
        logger.info(f"Password reset initiated for {self.email}")
        return JSONResponse(content={"msg": "Please check Email.Token is Valid for 30 mins"})


class ResetPassword(BaseModel):
    email: str
    token: str
    password: str

    def changePassword(self):
        qset = ResetPasswordToken.objects(email=self.email, token=self.token)
        if (not qset):
            logger.info(f"Password reset was not initiated for {self.email}.")
            return JSONResponse(content={"tokenError": "Token doesn't match"}, status_code=400)

        sel_query = qset[0]
        if (sel_query.time < datetime.datetime.now()):
            logger.info(f"Expired token provided for {self.email}.")
            sel_query.delete()
            return JSONResponse(content={"tokenError": "Token Has Expired"}, status_code=400)
        else:
            user = User.objects(email=self.email)
            user.update(password=hashPassword(self.password))
            qset.delete()
            logger.info(f"Password reset successful for {self.email}.")
            return SignIn(email=self.email, password=self.password).signin()


class FilesUpload(BaseModel):
    file_id: str = None
    file_path: str = None

    def __init__(self, file, user_id):
        super().__init__()
        logger.info(f"File uploaded by  {user_id}.")
        suffix = Path(file.filename).suffix
        self.file_path = f'{config["FILES"]+str(uuid.uuid1())+suffix}'
        with open(self.file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        if (isinstance(cv2.imread(self.file_path), type(None))):
            os.remove(self.file_path)
            logger.info(
                f"File not accepted because it was not an image {user_id}.")
            raise ValueError("Only pictures are accepted.")
        else:
            file_obj = Files(path=self.file_path, media_type=file.content_type,
                             owner=user_id)
            self.file_id = file_obj.save()
            logger.info(f"File assigned with id  {self.file_id}")


class AnnotationFileUpload(BaseModel):
    image_id: str = None
    timestamp:int=None
    doctype_id:str=None
    status:str=None
    metadata:Dict={}

    def _save_image(self, file, file_path):
        file_extension = file.filename.split('.')[-1]
        if file_extension.lower() in ['jpg', 'jpeg', 'png']:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        elif file_extension.lower() in ["pdf"]:
            pdf = pdf2image.convert_from_bytes(file.file.read())
            pdf[0].save(file_path, "JPEG")

    def __init__(self, file, user_id,doc_type_id):
        super().__init__()
        logger.info(f"Annotation file uploaded by  {user_id}.")
        file_path = f'{config["FILES"]+str(uuid.uuid1())+".jpg"}'
        self._save_image(file, file_path)
        img=cv2.imread(file_path)
        if (isinstance(img, type(None))):
            os.remove(file_path)
            logger.info(
                f"Annotation file not accepted because it was not an image {user_id}.")
            raise ValueError("Only pictures are accepted.")
        else:
            doc_type = DocumentType.objects(_id=doc_type_id).first()
            if(doc_type):
                file_obj = AnnotationFiles(path=file_path,media_type=file.content_type,owner=user_id,doc_type_id=doc_type_id,filename=file.filename,height=img.shape[0],width=img.shape[1])
                file_obj.save()
                logger.debug(f"Metadata of annotated file is: {file_obj.get_metadata()}")
                fields = [ {"name": field["name"], "id": field["id"], "word_ids": []} for field in doc_type.fields]
                file_obj.add_annotation(fields)
                self.metadata=file_obj.get_metadata()
                self.image_id = file_obj._id
                self.timestamp=file_obj.timestamp
                self.doctype_id=file_obj.doc_type_id
                self.status=file_obj.status
                logger.info(f"Annotation file assigned with id  {self.image_id}")
            else:
                logger.error("No such doc_type for the user.")
                raise ValueError("No such doc_type for the user.")


class DocType(BaseModel):
    id: str = None
    name:str
    task_type:str
    model: str
    fields:Optional[List[Dict]]=[]

    def save(self,owner):
        obj=DocumentType(name=self.name,owner=owner,fields=self.fields, task_type=self.task_type,model=self.model)
        id=obj.save()
        return {"id":id, "name":self.name, "task_type":self.task_type, "model":self.model, "fields":self.fields}

class Annotations(BaseModel):
    annotation:Optional[List[Dict]]=[]

class ModelInfo(BaseModel):
    id:str=None
    doc_type:str
    created_at:str=None
    owner:str=None
    train_split:float=0.9
    path: str=None
    epochs: int=1
    batch: int=2
    label_dict: Dict={}
    metrics: Dict={}
    accuracy: Dict={}
    version: str = "v1"

    def save(self,owner):
        # perform pre-validation, get the train and test split
        # get the labels for the model
        doc_type = DocumentType.objects(_id=self.doc_type,owner=owner).first()
        self.label_dict = {}
        total_fields = ['O']
        for field in doc_type.fields:
            total_fields.append(f'B-{field["name"]}'.upper())
            total_fields.append(f'I-{field["name"]}'.upper())    
        
        self.label_dict = {field: i for i, field in enumerate(total_fields)}
        self.owner = str(owner)
        # increase the version number
        self.version = f"v{ModelInformation.objects(owner=owner, doc_type=doc_type._id).count()+1}"
        obj=ModelInformation(doc_type=self.doc_type, owner=self.owner,train_split=self.train_split,label_dict=self.label_dict,
                         batch=self.batch, accuracy=self.accuracy, metrics=self.metrics,path=self.path, version=self.version, 
                         epochs=self.epochs, trained_epochs=0, status="running")
        self.id=obj.save()
        self.created_at = obj.created_at
        self.path = obj.path
        return {"id":self.id, "doc_type":self.doc_type, "train_split":self.train_split,"label_dict":self.label_dict,
                    "batch": self.batch, "metrics":self.metrics,"path":self.path, "version": self.version, "created_at":self.created_at, "epochs": self.epochs}

