from fastapi import APIRouter, Depends
from models.validator import Session
from models.database.file_db import AnnotationFiles
from loguru import logger
from utils import get_doc_type_name, get_user_name
from math import ceil
import time
 
get_documents_router = APIRouter(tags=["get_documents"])

@get_documents_router.get("")
def get_documents(page:int=1, limit:int=20, session: Session = Depends(Session)):
    start = time.time()
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        logger.debug(f"RuntimeError: {e.args[0]}")
        return e.args[0]
    documents = AnnotationFiles.objects(owner=session.user_id).order_by('-timestamp')
    max_pages = ceil(documents.count()/limit)
    documents = documents.skip((page-1)*limit).limit(limit).select_related()
    documents = [
        {'image_id': doc._id, 'owner': get_user_name(doc.owner), 'filename': doc.filename,
        'timestamp': doc.timestamp, 'doc_type_id': doc.doc_type_id, 'doc_type_name': get_doc_type_name(doc.doc_type_id),
        'status': doc.status}
        for doc in documents if get_doc_type_name(doc.doc_type_id).strip()!=""
    ]
    logger.debug(f"Time taken to fetch documents: {time.time()-start}")
    return {'documents':documents, "max_pages":max_pages}