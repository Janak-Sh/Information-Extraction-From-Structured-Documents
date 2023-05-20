
from models.validator import Session,Annotations
from models.utils import JSONResponse
from models.database.file_db import AnnotationFiles
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from loguru import logger
import json
from typing import Dict
annotate_router = APIRouter(tags=["annotate"])
    
@annotate_router.post("/{file_id}")
def annotation_fileupload(file_id:str,annotations:Annotations,metadata:Dict, session: Session = Depends(Session),):
    logger.debug("annotation_fileupload",annotations)
    logger.debug("File metadata", metadata)
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]

    try:
        file = AnnotationFiles.objects(owner=session.user_id,_id=file_id).first()
        file.add_annotation(annotations.annotation)
        file.update_metadata(metadata)
        return JSONResponse(status_code=200, content={"image_id": file._id,'timestamp':file.timestamp,'doc_type_id':file.doc_type_id,'status':file.status})
    except Exception as e:
        logger.error(e)
        return JSONResponse(status_code=400, content={"msg": "Error"})


@annotate_router.get("/get/{file_id}")
def get_annotation(file_id:str,session: Session = Depends(Session)):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]
    
    try:
        file = AnnotationFiles.objects(owner=session.user_id,_id=file_id).first()
        return {
                "metadata":file.get_metadata(),
                'annotation':file.annotation,
                'ocr_data':file.ocr
            }
    except:
        return JSONResponse(status_code=400, content={"msg": "Error"})


def form_annotation(annotation):
    yield json.dumps(annotation)

def to_csv(annotation):
    csv="DocId,Key,Text\n"
    for row in annotation:
        csv+=f'{row["id"]},{row["name"]},{row["text"]},\n'
    yield csv

@annotate_router.get("/download/json/{file_id}")
def get_annotation(file_id:str):
    file= AnnotationFiles.objects(_id=file_id).first()  
    for ann in file.annotation:
        ann["text"] = " ".join(ann["value"])
        ann.pop("value")
        ann.pop("word_ids")
    return StreamingResponse(form_annotation(file.annotation),headers={'Content-Disposition': f'attachment; filename="{file_id}.json"'})

@annotate_router.get("/download/csv/{file_id}")
def get_annotation(file_id:str):
    file= AnnotationFiles.objects(_id=file_id).first() 
    for ann in file.annotation:
        ann["text"] = " ".join(ann["value"])
        ann.pop("value")
        ann.pop("word_ids") 
    return StreamingResponse(to_csv(file.annotation),headers={'Content-Disposition': f'attachment; filename="{file_id}.csv"'})


def _get_funsd(ocr1, annotations):
    ocr = ocr1.copy()
    for rec in ocr:
        rec["box"] = [rec["left"], rec["top"], rec["left"]+rec["width"], rec["top"]+rec["height"]]
        rec["label"] = "other"
        rec["words"] = []
        rec["linking"] = []
        del rec["left"], rec["top"], rec["width"], rec["height"]
    word_groups = { ann["name"]: [ocr[idx] for idx in ann["word_ids"]] for ann in annotations}
    ocr = {i: data for i, data in enumerate(ocr)}
    for ann in annotations:
        for idx in ann["word_ids"]:
            del ocr[idx]
    for label, word_group in word_groups.items():
        if not word_group:
            continue
        temp = {}
        words = []
        for word in word_group:
            words.append({"text": word["text"], "box": word["box"]})
        temp["words"] = words
        temp["label"] = label
        temp["box"] = [min([word["box"][0] for word in words]), min([word["box"][1] for word in words]), max([word["box"][2] for word in words]), max([word["box"][3] for word in words])]
        temp["text"] = " ".join([word["text"] for word in words])
        temp["id"] = word_group[0]["id"]
        ocr[word_group[0]["id"]] = temp
    return list(ocr.values())
        

@annotate_router.get("/get/funsd/{file_id}")
def get_funsd(file_id:str,session: Session = Depends(Session)):
    file= AnnotationFiles.objects(_id=file_id).first() 
    annotation = file.annotation
    ocr_data = file.ocr
    ocr_data = [{"id": int(row[5]), "top": int(row[1]), "left": int(row[0]), "width": int(row[2]), "height": int(row[3]), "text": row[4]} for row in ocr_data]

    funsd = _get_funsd(ocr_data, annotation)
    funsd.sort(key=lambda x: x["id"])
    return funsd

