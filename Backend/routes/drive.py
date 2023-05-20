
from models.validator import Session
from models.utils import JSONResponse
from models.database.file_db import GToken, AnnotationFiles
from models.validator import Session
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from urllib.parse import quote_plus as urlencode
import requests
import json

drive = APIRouter(tags=["drive"])

def to_csv(annotation):
    csv="key,value\n"
    for i in annotation:
        csv+=f'{i["name"]},{" ".join(i["value"]).replace(","," ")}\n'
    return csv

config = {
        "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": "77719607766-lmtultpfa6b89gr69c5a2sm8j997koc3.apps.googleusercontent.com",
    "client_secret": "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",
    "redirect_uri": 'http://localhost:8000/drive/callback/',
}


@drive.get("/")
def annotation_fileupload(session: Session = Depends(Session),):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]
    token_obj = GToken.objects(owner=session.user_id).first()
    if (token_obj):
        return JSONResponse(status_code=200, content={"msg": "Access token already exist."})

    client_id = config['client_id']
    redirect = urlencode(config['redirect_uri'])
    url = f'https://accounts.google.com/o/oauth2/v2/auth/oauthchooseaccount?redirect_uri={redirect}&prompt=consent&response_type=code&client_id={client_id}&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fdrive&access_type=offline&service=lso&o2v=2&flowName=GeneralOAuthFlow'
    return RedirectResponse(status_code=302, url=url)


@drive.get("/callback/")
def annotation_fileupload(code: str = None, session: Session = Depends(Session),):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]
    try:
        config['code'] = code
        config['grant_type'] = 'authorization_code'
        response = (requests.post(config['token_uri'], json=config)).json()
        token_obj = GToken.objects(owner=session.user_id).first()
        if (token_obj):
            token_obj.delete()

        GToken(access=response["access_token"], refresh=response["refresh_token"], owner=session.user_id).save(
            expires=int(response["expires_in"]))
        return response["access_token"]
    except:
        return JSONResponse(status_code=400, content={"msg": "Bad Request."})


@drive.get("/upload/")
def annotation_fileupload(id: str = None, session: Session = Depends(Session),):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]
    if (id):
        pass
        token_obj = GToken.objects(owner=session.user_id).first()
        if (not token_obj):
            return RedirectResponse(status_code=302, url="/drive")

        headers = {"Authorization": "Bearer " + token_obj.get_token(config)}
        file = AnnotationFiles.objects(_id=id).first()
        if (file):
            para = {
                "title": file.filename.split('.')[0]+".json",
                "parents": [{"id": "root"}]
            }
            files = {
                "data": ("metadata", json.dumps(para), "application/json; charset=UTF-8"),
                "file": json.dumps({"annotations": file.annotation})
            }
            response = requests.post(
                "https://www.googleapis.com/upload/drive/v2/files?uploadType=multipart", headers=headers, files=files)

@drive.get("/new/upload/")
def annotation_fileupload(id: str = None, session: Session = Depends(Session),):
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]
    if (id):
        pass
        token_obj = GToken.objects().first()
        if (not token_obj):
            return RedirectResponse(status_code=302, url="/drive")

        headers = {"Authorization": "Bearer " + token_obj.get_token(config)}
        file = AnnotationFiles.objects(_id=id).first()
        if (file):
            para = {
                "title": file.filename.split('.')[0]+".json",
                "parents": [{"id": file.filename}]
            }
            files = {
                "data": ("metadata", json.dumps(para), "application/json; charset=UTF-8"),
                "file": json.dumps({"annotations": file.annotation})
            }
            response = requests.post(
                "https://www.googleapis.com/upload/drive/v2/files?uploadType=multipart", headers=headers, files=files)
            file_ids=[response.json()['id']]
            para = {
                "title": file.filename.split('.')[0]+".csv",
                "parents": [{"id": "root"}]
            }
            files = {
                "data": ("metadata", json.dumps(para), "application/json; charset=UTF-8"),
                "file": to_csv(file.annotation)
            }
            response = requests.post(
                "https://www.googleapis.com/upload/drive/v2/files?uploadType=multipart", headers=headers, files=files)

            file_ids.append(response.json()['id'])
            params = {
                'role': 'reader',
                'type': 'anyone',
            }
            headers['Content-Type']='application/json'
            for file_id in file_ids:
                permission_url = f'https://www.googleapis.com/drive/v2/files/{file_id}/permissions'
                response = requests.post(permission_url,headers=headers,json=params)
            return {"csv":f"https://drive.google.com/uc?id={file_ids[0]}","json":f"https://drive.google.com/uc?id={file_ids[1]}"} 