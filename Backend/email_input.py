import time
from models.database.send_email import Email
from models.database.file_db import AnnotationFiles
from models.database.user_db import User
from models.database.doc_type_db import ModelInformation
from routes.predict import perform_extraction
import cv2

def email_input():
    email=Email()
    TERMINATE=False
    while not TERMINATE:
        try:
            emails=email.get_email()
            for i in emails:
                e=i["email"].split('<')[-1][:-1]
                user=User.objects(email=e).only('_id').first()
                if(user):  
                    model_id=i["subject"]
                    model=ModelInformation.objects(_id=model_id).first()
                    if(model):
                        for file in i["mapping"]:
                            img=cv2.imread(file['path'])
                            if(not isinstance(img,type(None))):
                                paras={
                                    'path':file['path'],
                                    'media_type':"image/png",
                                    'owner':user._id,
                                    'doc_type_id':model.doc_type,
                                    'filename':file['filename'],
                                    'height':img.shape[0],
                                    'width':img.shape[1]
                                }
                                file_obj = AnnotationFiles(**paras)
                                t=file_obj.save()
                                perform_extraction(t,model)
                time.sleep(300)
        except:
            pass