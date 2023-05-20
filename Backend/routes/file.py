import json
from fastapi import APIRouter, Depends, UploadFile, BackgroundTasks
from models.validator import Session, FilesUpload,AnnotationFileUpload,DocType
from models.database.file_db import Files,AnnotationFiles
from fastapi.responses import StreamingResponse
from models.utils import JSONResponse

file_router = APIRouter(tags=["file-upload"])

@file_router.get("/get/{id}")
def streamFile(id: str, session: Session = Depends(Session)):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]

    qset = Files.objects(_id=id, owner=session.user_id)
    if (not qset):
        return JSONResponse(status_code=400, content={"msg": "File not found"})
    else:
        file = qset[0]

        def iterfile():
            with open(file.path, mode="rb") as document:
                yield from document

        return StreamingResponse(iterfile(), media_type=file.media_type)


@file_router.post("/delete/{id}")
def deleteFile(id: str, session: Session = Depends(Session)):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]

    qset = Files.objects(_id=id, owner=session.user_id)
    if (not qset):
        return JSONResponse(status_code=400, content={"msg": "File not found"})
    else:
        file = qset[0]
        file.delete()
        return {"msg":"File deleted successfully"}
        

@file_router.get("/status/{id}")
def streamFile(id: str, session: Session = Depends(Session)):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]

    qset = Files.objects(_id=id, owner=session.user_id).only(
        'status', 'status_code', 'json')
    if (not qset):
        return JSONResponse(status_code=400, content={"msg": "File not found"})
    else:
        qset = qset[0]
        if(qset['json']):
            qset['json']=json.loads(qset['json'])
        else:
            qset['json']={}
            
        return JSONResponse(status_code=int(qset.status_code), content=qset.to_mongo())