from models.database.doc_type_db import DocumentType
from models.database.file_db import AnnotationFiles
from models.database.user_db import User
from PIL import Image
from functools import lru_cache
from loguru import logger

@lru_cache(maxsize=8)
def get_doc_type_name(id):
    try:
        obj=DocumentType.objects(_id=id).first()
        logger.debug(f"Fetched doc name: {obj.name}")
        return obj.name
    except Exception as e:
        return ""

@lru_cache(maxsize=8)
def get_user_name(id):
    try:
        obj=User.objects(_id=id).first()
        logger.debug(f"Fetched user name: {obj.userName}")
        return obj.userName
    except Exception as e:
        return ""
    
@lru_cache(maxsize=8)
def get_doctype_metadata(_id):
    files = AnnotationFiles.objects(doc_type_id=_id)
    uploaded = files.count()
    processed = files.filter(status="Processed.").count()
    reviewed = uploaded - processed
    return {"uploaded": uploaded, "processed": processed, "reviewed": reviewed}