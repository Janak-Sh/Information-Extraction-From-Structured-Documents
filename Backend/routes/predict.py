import cv2
from pytesseract import Output
import pytesseract
from models.validator import Session
from models.utils import JSONResponse
from models.database.file_db import AnnotationFiles,GToken
from models.database.doc_type_db import ModelInformation,DriveMap
from models.database.user_db import User
from models.validator import Session, AnnotationFileUpload
from fastapi import APIRouter, Depends, UploadFile, BackgroundTasks, Security, HTTPException
from inference.utils import predict
from typing import List
from loguru import logger
from time import time
from utils import get_doc_type_name
import json,requests
from fastapi.security.api_key import APIKeyHeader, APIKey

api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=True)

def annotation_fileupload(owner,filename,annotations):
    folder_id=DriveMap.objects(owner=owner).first()
    filename=filename.split('.')[0]
    token=(GToken.objects().first()).get_token()
    headers={
            "Authorization": "Bearer " + (GToken.objects().first()).get_token()
        }
    if(folder_id):
        logger.info(f"Existng drive folder of {owner} found.") 
        folder_id=folder_id.drive_id
    else:
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
    
    response = requests.post(
        'https://www.googleapis.com/drive/v3/files',
        headers=headers,
        json={
            'name': filename, 
            'mimeType': 'application/vnd.google-apps.folder',
            "parents":[folder_id]
        }
    )

    folder_id=response.json()['id']

    para = {
        "title": filename+".json",
        "parents": [{"id": folder_id}]
    }

    files = {
        "data": ("metadata", json.dumps(para), "application/json; charset=UTF-8"),
        "file": json.dumps(annotations)
    }
    response = requests.post(
        "https://www.googleapis.com/upload/drive/v2/files?uploadType=multipart", headers=headers, files=files)
    para['title'] =filename+".json"

    # csv="id,Field,Value\n"
    # for annotation in annotations:
    #     csv+=f"""
    #             {str(annotation['id']).replace(',',' ')},
    #             {str(annotation['name']).replace(',', ' ')},
    #             {str(annotation['value']).replace(',',' ')}\n
    #         """
        
    # files = {
    #     "data": ("metadata", json.dumps(para), "application/json; charset=UTF-8"),
    #     "file": csv
    # }
    response = requests.post(
        "https://www.googleapis.com/upload/drive/v2/files?uploadType=multipart", headers=headers, files=files)

    return f"https://drive.google.com/drive/folders/{folder_id}?usp=sharing"

    
def perform_extraction(image_id, model_info):
    start = time()
    file=AnnotationFiles.objects(_id=image_id).first()
    img = cv2.imread(file.path)
    d = pytesseract.image_to_data(img, output_type=Output.DICT)
    logger.debug(f"Performed ocr of document {image_id}")
    keys = ['left', 'top', 'width', 'height', 'conf', 'text']
    d = {k:d[k] for k in keys}
    d = list(zip(d["left"], d["top"], d["width"], d["height"], d["text"]))
    d = [list(i) for i in d if i[4].strip()!=""]
    ocr = []
    for i,row in enumerate(d):
        row = list(row)
        row.append(i)
        ocr.append(row)
    d = None
    file.add_ocr(ocr)
    logger.info(f"Time taken for OCR of image {image_id} is {time()-start}")

    logger.info(f"Passing the data to the model {model_info._id} for image {image_id}")
    result, combined = predict(model_info, file.path, file.ocr)
    logger.info(f"Completed extraction of information from image {image_id} by model {model_info._id}")
    end = time()
    logger.info(f"Time taken for extraction of information for image {image_id} by model {model_info._id} is {end-start}")
    annotations = [ {"id": str(row["id"]), "name": row["name"], "word_ids":[word for word in result.get(row["name"].upper(), {}).get("ids", [])], "value":[word for word in result.get(row["name"].upper(), {}).get("text", [])]} for row in file.annotation]
    file.add_annotation(annotations)
    gdrive=annotation_fileupload(file.owner,file.filename,annotations)
    file.add_gdrive(gdrive)
    return result, combined

def perform_multiple_extraction(image_ids, model_info):
    for image_id in image_ids:
        start = time()
        file=AnnotationFiles.objects(_id=image_id).first()
        img = cv2.imread(file.path)
        d = pytesseract.image_to_data(img, output_type=Output.DICT)
        logger.debug(f"Performed ocr of document {image_id}")
        keys = ['left', 'top', 'width', 'height', 'conf', 'text']
        d = {k:d[k] for k in keys}
        d = list(zip(d["left"], d["top"], d["width"], d["height"], d["text"]))
        d = [list(i) for i in d if i[4].strip()!=""]
        ocr = []
        for i,row in enumerate(d):
            row = list(row)
            row.append(i)
            ocr.append(row)
        d = None
        file.add_ocr(ocr)
        logger.info(f"Time taken for OCR of image {image_id} is {time()-start}")

        logger.info(f"Passing the data to the model {model_info._id} for image {image_id}")
        result, combined = predict(model_info, file.path, file.ocr)
        logger.info(f"Completed extraction of information from image {image_id} by model {model_info._id}")
        end = time()
        logger.info(f"Time taken for extraction of information for image {image_id} by model {model_info._id} is {end-start}")
        annotations = [ {"id": str(row["id"]), "name": row["name"], "word_ids":[word for word in result.get(row["name"].upper(), {}).get("ids", [])], "value":[word for word in result.get(row["name"].upper(), {}).get("text", [])]} for row in file.annotation]
        file.add_annotation(annotations)
        gdrive=annotation_fileupload(file.owner,file.filename,  annotations)
        file.add_gdrive(gdrive)


predict_router = APIRouter(tags=["predict"])

   
@predict_router.post("/new/{model_id}")
async def apikey_inference(model_id, files: List[UploadFile],background_tasks: BackgroundTasks,api_key_header: str = Security(api_key_header)):
    user = User.objects(apikey=api_key_header).first()
    if user.apikey!=api_key_header:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    success=[]
    error=[]
    model_info = ModelInformation.objects(_id=model_id, owner=user._id).first()
    _files = []
    for file in files:
        try:
            file = AnnotationFileUpload(file, user._id,model_info.doc_type)
            if model_info is not None:
                _files.append(file.image_id)
            success.append(file.metadata)
        except ValueError as e:
            error.append(file.filename)

    logger.info("Extracting data from the document using the model")
    background_tasks.add_task(perform_multiple_extraction, _files, model_info)
    logger.info("Task added to queue")

    # for file in files:
    #     try:
    #         logger.info(f"Uploading file {file.filename} for user {user._id}")
    #         file = AnnotationFileUpload(file, user._id,model.doc_type)
    #         logger.info(f"Uploaded file {file.image_id}")
    #         logger.info(f"Starting information extraction from image {file.image_id} by model {model._id}")
    #         background_tasks.add_task(perform_extraction, file.image_id, model)
    #         return {"document_id": file.image_id, "model_id": model._id}
    #     except ValueError as e:
    #         error.append(file.filename)
    
    return JSONResponse(status_code=200, content={"success":success,"error":error})

@predict_router.post("/{model_id}")
async def inference(model_id, files: List[UploadFile],background_tasks: BackgroundTasks, session: Session = Depends(Session),):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]
    success=[]
    error=[]
    model = ModelInformation.objects(_id=model_id, owner=session.user_id).first()
    for file in files:
        try:
            logger.info(f"Uploading file {file.filename} for user {session.user_id}")
            file = AnnotationFileUpload(file, session.user_id,model.doc_type)
            logger.info(f"Uploaded file {file.image_id}")
            logger.info(f"Starting information extraction from image {file.image_id} by model {model._id}")
            background_tasks.add_task(perform_extraction, file.image_id, model)
            return {"document_id": file.image_id, "model_id": model._id}
        except ValueError as e:
            error.append(file.filename)
    
    return JSONResponse(status_code=200, content={"success":success,"error":error})


@predict_router.get("/")
def get_all_models(session: Session = Depends(Session),):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]
    res = []
    models = ModelInformation.objects(owner=session.user_id).only("_id", "created_at", "owner", "doc_type", "accuracy", "version", "epochs", "trained_epochs", "status")
    for model in models:
        if get_doc_type_name(model["doc_type"])!="":
            model = json.loads(model.to_json())
            model['doc_type_name'] = get_doc_type_name(model["doc_type"]) 
            res.append(model)
            res[-1]['id']=res[-1].pop('_id')

    return JSONResponse(status_code=200, content={"models":res[::-1]})

@predict_router.get("/{model_id}")
def get_model(model_id, session: Session = Depends(Session),):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]
    res = []
    models = ModelInformation.objects(_id=model_id, owner=session.user_id)
    for model in models:
        res.append(json.loads(model.to_json()))
        res[-1]['id']=res[-1].pop('_id')
        
    return JSONResponse(status_code=200, content={"models":res})