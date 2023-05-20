import cv2
from pytesseract import Output
import pytesseract
from models.validator import Session
from models.database.doc_type_db import DocumentType,ModelInformation
from models.utils import JSONResponse
from models.database.file_db import AnnotationFiles
from models.validator import Session, AnnotationFileUpload
from fastapi import APIRouter, Depends, UploadFile, BackgroundTasks, File
from fastapi.responses import StreamingResponse
from typing import List
from inference.utils import predict
from loguru import logger
from time import time
import uuid


annotation_router = APIRouter(tags=["annotation"])


def ocr(id):
    file=AnnotationFiles.objects(_id=id)[0]
    img = cv2.imread(file.path)
    d = pytesseract.image_to_data(img, output_type=Output.DICT)
    keys = ['left', 'top', 'width', 'height', 'conf', 'text']
    d = {k:d[k] for k in keys}
    d = list(zip(d["left"], d["top"], d["width"], d["height"], d["text"]))
    d = [ list(i) for i in d if i[4].strip()!=""]
    ocr = []
    for i,row in enumerate(d):
        row = list(row)
        row.append(i)
        ocr.append(row)
    d = None
    file.add_ocr(ocr)

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
    return result, combined

def multiple_ocr(ids):
    for id in ids:
        file=AnnotationFiles.objects(_id=id)[0]
        img = cv2.imread(file.path)
        d = pytesseract.image_to_data(img, output_type=Output.DICT)
        keys = ['left', 'top', 'width', 'height', 'conf', 'text']
        d = {k:d[k] for k in keys}
        d = list(zip(d["left"], d["top"], d["width"], d["height"], d["text"]))
        d = [ list(i) for i in d if i[4].strip()!=""]
        ocr = []
        for i,row in enumerate(d):
            row = list(row)
            row.append(i)
            ocr.append(row)
        d = None
        file.add_ocr(ocr)

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

@annotation_router.post("/post/{doc_type_id}")
def annotation_fileupload(file: UploadFile,doc_type_id,background_tasks: BackgroundTasks, session: Session = Depends(Session),):
    logger.info("Single File being uploaded")
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]
    try:
        logger.debug(f"Doc type id: {doc_type_id}")
        file = AnnotationFileUpload(file, session.user_id,doc_type_id)
        doc_type = DocumentType.objects(_id=doc_type_id).first()
        logger.debug(f"Model id: {doc_type.model}")
        if doc_type.model.strip()!="":
            logger.info("Extracting data from the document using the model")
            model_info = ModelInformation.objects(_id=doc_type.model).first()
            logger.info("Task added to celery queue")
            background_tasks.add_task(perform_extraction, file.image_id, model_info)
        else:
            logger.info("Extracting data from the document using OCR")
            background_tasks.add_task(ocr, file.image_id)
            logger.info("Task being performed")
        return JSONResponse(status_code=202, content=file.metadata)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"msg": e.args[0]})

@annotation_router.post("/post/multiple/{doc_type_id}")
def annotation_fileupload(files: List[UploadFile],doc_type_id,background_tasks: BackgroundTasks, session: Session = Depends(Session),):
    logger.info("Multiple files being uploaded")
    logger.debug(f"Doc type id: {doc_type_id}")
    logger.debug(f"Total Files uploaded: {len(files)}")
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]
    logger.debug(f"User id: {session.user_id}")
    success=[]
    error=[]
    doc_type = DocumentType.objects(_id=doc_type_id).first()
    logger.debug(f"Model id: {doc_type.model}")
    model_info = None
    if doc_type.model.strip()!="":
        model_info = ModelInformation.objects(_id=doc_type.model).first()
        logger.debug(f"Model info: {model_info}")

    _files = []
    for file in files:
        try:
            file = AnnotationFileUpload(file, session.user_id,doc_type_id)
            _files.append(file.image_id)
            success.append(file.metadata)
        except ValueError as e:
            error.append(file.filename)

    if model_info is not None:
        logger.info("Extracting data from the document using the model")
        background_tasks.add_task(perform_multiple_extraction, _files, model_info)
        logger.info("Task added to queue")
    else:
        logger.info("Extracting data from the document using OCR")
        background_tasks.add_task(multiple_ocr, _files)
        logger.info("Task being performed")

    # for file in files:
    #     try:
    #         file = AnnotationFileUpload(file, session.user_id,doc_type_id)
    #         if model_info is not None:
    #             logger.info("Extracting data from the document using the model")
    #             background_tasks.add_task(perform_extraction, file.image_id, model_info)
    #             logger.info("Task added to queue")
    #         else:
    #             logger.info("Extracting data from the document using OCR")
    #             background_tasks.add_task(ocr, file.image_id)
    #             logger.info("Task being performed")
    #         success.append(file.metadata)
    #     except ValueError as e:
    #         error.append(file.filename)
    
    return JSONResponse(status_code=200, content={"success":success,"error":error})


@annotation_router.get("/get_file/{id}")
def annotation_streamFile(id: str):
    qset = AnnotationFiles.objects(_id=id)
    if (not qset):
        return JSONResponse(status_code=400, content={"msg": "File not found"})
    else:
        file = qset[0]

        def iterfile():
            with open(file.path, mode="rb") as document:
                yield from document
        return StreamingResponse(iterfile(), media_type=file.media_type)

@annotation_router.get("/{id}")
def annotation_get_data(id: str, session: Session = Depends(Session)):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]

    qset = AnnotationFiles.objects(_id=id, owner=session.user_id)
    if (not qset):
        return JSONResponse(status_code=400, content={"msg": "File not found"})
    else:
        file = qset[0]
        return JSONResponse(status_code=file.status_code,content={'ocr':file.ocr})

@annotation_router.post("/delete/{id}")
def deleteFile(id: str, session: Session = Depends(Session)):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]

    qset = AnnotationFiles.objects(_id=id, owner=session.user_id)
    if (not qset):
        return JSONResponse(status_code=400, content={"msg": "File not found"})
    else:
        file = qset[0]
        file.delete()
        return {"msg":"File deleted successfully"}
 
@annotation_router.post("/delete_multiple")
def deleteMultiple(ids: List[str], session: Session = Depends(Session)):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:   
        return e.args[0]
    success = []
    for _id in ids:
        qset = AnnotationFiles.objects(_id=_id, owner=session.user_id).first()
        if (qset):
            success.append(_id)
            qset.delete()
    return JSONResponse(status_code=200,content={"msg":"Files deleted successfully","success":success})