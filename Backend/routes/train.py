from models.validator import Session
from models.utils import JSONResponse
from models.database.file_db import AnnotationFiles
from models.database.doc_type_db import ModelInformation
from models.validator import Session, ModelInfo
from fastapi import APIRouter, Depends, BackgroundTasks
from inference.train.train import train
from loguru import logger
from typing import List
import json

train_router = APIRouter(tags=["train"])

@train_router.post("/")
def do_training(model_info:ModelInfo,background_tasks: BackgroundTasks, session: Session = Depends(Session),):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]
    model_info.save(owner=session.user_id)
    document_ids = AnnotationFiles.objects(doc_type_id=model_info.doc_type).only("_id")
    document_ids = [_doc._id for _doc in document_ids]
    logger.debug(f"{len(document_ids)} is being subjected to train-test-split for model {model_info.id} of doctype {model_info.doc_type}")
    model = ModelInformation.objects(_id=model_info.id).first()
    background_tasks.add_task(train, model, document_ids)
    logger.info(model_info)
    return model_info

@train_router.get("/status/{id}")
def get_training_status(id: str, session: Session = Depends(Session)):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]
    model = ModelInformation.objects(_id=id).first()
    return json.loads(model.to_json())

@train_router.post("/delete/{id}")
def delete_model(id: str, session: Session = Depends(Session)):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]

    qset = ModelInformation.objects(_id=id, owner=session.user_id)
    if (not qset):
        return JSONResponse(status_code=400, content={"msg": "File not found"})
    else:
        file = qset[0]
        file.delete()
        return {"msg":"File deleted successfully"}
 
@train_router.post("/delete_multiple")
def delete_multiple_models(ids: List[str], session: Session = Depends(Session)):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:   
        return e.args[0]
    success = []
    for _id in ids:
        qset = ModelInformation.objects(_id=_id, owner=session.user_id).first()
        if (qset):
            success.append(_id)
            qset.delete()
    return JSONResponse(status_code=200,content={"msg":"Models deleted successfully","success":success})