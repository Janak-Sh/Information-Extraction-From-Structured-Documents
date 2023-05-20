from fastapi import APIRouter, Depends
from models.database.doc_type_db import DocumentType
from models.validator import Session,DocType
from models.utils import JSONResponse
from models.database.file_db import AnnotationFiles
from loguru import logger
from utils import get_doctype_metadata
 
"""
This router handles all the requests related to document types.
"""
doc_type_router = APIRouter(tags=["doc_types"])
 
 
@doc_type_router.post("/post/")
def create_doc_type(doc_type:DocType, session: Session = Depends(Session),):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        logger.debug(f"RuntimeError: {e.args[0]}")
        return e.args[0]
    doc_type_info=doc_type.save(session.user_id)
    logger.info(f"Document type created: {doc_type_info}")
    return doc_type_info
 
@doc_type_router.get("/get_all/")
def get_all_doc_type(session: Session = Depends(Session),):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]
    obj=DocumentType.objects(owner=session.user_id)
    res=[]
    for i in obj:
        metadata = get_doctype_metadata(i._id)
        res.append({'id':i._id,'name':i.name, "metadata":metadata})
    return {"doctypes": res}
 
@doc_type_router.post("/update/{id}")
def update(id:str,doc_type:DocType,session: Session = Depends(Session)):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]
    obj=DocumentType.objects(_id=id,owner=session.user_id)[0]
    if(not obj):
        return JSONResponse(status_code=400, content={"msg": "No such document type found."})
    obj.name=doc_type.name
    obj.fields=doc_type.fields
    obj.save()
    # Update all the annotations in the documents of this type.
    return {"msg":"Document Type Updated Successfully.", 'data':{'id':obj._id,'name':obj.name,'fields':obj.fields,'task_type':obj.task_type,'model':obj.model}}
    
@doc_type_router.post("/{doc_type_id}/model")
def update(doc_type_id:str, model_id:dict, session: Session = Depends(Session)):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]
    obj=DocumentType.objects(_id=doc_type_id,owner=session.user_id)[0]
    if(not obj):
        return JSONResponse(status_code=400, content={"msg": "No such document type found."})
    obj.model = model_id["model_id"]
    obj.save()
    # Update all the annotations in the documents of this type.
    return {"msg":"Document Type Updated Successfully.", 'data':{'id':obj._id,'name':obj.name,'fields':obj.fields,'task_type':obj.task_type,'model':obj.model}}
    
 
@doc_type_router.get("/{doc_type_id}")
def get_doctype_info(doc_type_id:str,session: Session = Depends(Session),):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]
    try:
        obj = DocumentType.objects(_id=doc_type_id,owner=session.user_id)[0]
        files=[]
        try:
            for i in AnnotationFiles.objects(doc_type_id=doc_type_id):
                files.append(i.get_metadata())
        except Exception as e:
            logger.error(e)
            files = []
        
        return {'id':obj._id,'name':obj.name,'fields':obj.fields,'task_type':obj.task_type,'model':obj.model,'files':files}
    except Exception as e:
        return JSONResponse(status_code=400,content={"msg":f"Document type not found."})
 
@doc_type_router.post("/delete/{doc_type_id}")
def delete_doc_type(doc_type_id:str,session: Session = Depends(Session)):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]
    
    try:
        obj = DocumentType.objects(_id=doc_type_id,owner=session.user_id)[0]
        obj.delete()
        return {"msg":f"Doctype deleted successfully."}
    except:
        return JSONResponse(status_code=400,content={"msg":f"Doctype deletion failed."})
    

@doc_type_router.get("/new/{doc_type_id}")
def get_doctype(doc_type_id:str,session: Session = Depends(Session),):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]
    
    obj = DocumentType.objects(_id=doc_type_id,owner=session.user_id)[0]
    try:
        file = AnnotationFiles.objects(doc_type_id=doc_type_id,owner=session.user_id)[0]
        return {'file_id': file._id , 'meta':{'id':obj._id,'name':obj.name,'fields':obj.fields,'task_type':obj.task_type,'model':obj.model}}

    except Exception as e:
        logger.error(e)
        return {'file_id': "", 'meta':{'id':obj._id,'name':obj.name,'fields':obj.fields,'task_type':obj.task_type,'model':obj.model}}
 