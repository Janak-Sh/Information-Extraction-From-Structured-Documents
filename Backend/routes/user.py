from fastapi import APIRouter,HTTPException,status,Depends,Request,UploadFile
from fastapi.responses import JSONResponse
from models.validator import SignIn,CreateUser,Session,ForgotPassword,ResetPassword
import json
import uuid
from typing import Optional
from models.database.user_db import User
from models.database.file_db import Files
from models.database.doc_type_db import DriveMap
from loguru import logger

user_router=APIRouter(tags=["User"])

users={}

@user_router.get("/")
async def test():
    return "response"

@user_router.post("/signup")
async def signUp(data:CreateUser)->dict:
    response=data.save()
    return response
        

@user_router.post("/signin")
async def signIn(userCredentials: SignIn,session:Session=Depends(Session)) -> dict:    
    status,response=session.isAuthenticated(required=False)
    if(status):
        response.status_code=400
        response.modify(content={
            "msg":"Already logged in.Logout to continue "
        })
        return response
    else:
        cred = userCredentials.signin()
        logger.debug(f"User Credentials: {cred}")
        return cred
    

@user_router.get("/apikey")
async def get_apikey(session:Session=Depends(Session)) -> dict:    
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]
    user=User.objects(_id=session.user_id).first()
    return {"apikey": user.apikey}

    
@user_router.get("/generate_apikey")
async def generate_apikey(session:Session=Depends(Session)) -> dict:    
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]
    user=User.objects(_id=session.user_id).first()
    apikey = user.generate_apikey()
    return {"apikey": apikey}

@user_router.post("/apiservices")
async def update_apiservices(api:dict, session:Session=Depends(Session)) -> dict:   
    logger.debug(api) 
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]
    user=User.objects(_id=session.user_id).first()
    apiservices = user.update_apiservices(api)
    return {"apiservices": apiservices}


@user_router.get("/apiservices")
async def generate_apikey(session:Session=Depends(Session)) -> dict:    
    try:
        response = session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]
    user=User.objects(_id=session.user_id).first()
    apiServices = user.apiServices
    return {"apiServices": apiServices}


@user_router.post("/logout")
def logout(session:Session=Depends(Session)):
    response=session.logout()
    return response

@user_router.post("/terminate_sessions")
def terminate_sessions(session:Session=Depends(Session)):
    response=session.terminateAllSessions()
    return response

@user_router.post("/forgotpassword")
async def forgotpassword(forgotRequest:ForgotPassword,session:Session=Depends(Session)):
    status,response=session.isAuthenticated(required=False)
    if(status):
        response.status_code=400
        response.modify(content={
            "msg":"Already logged in.Logout to continue "
        })
        return response
    
    response=forgotRequest.InitiatePasswordReset()
    return response

@user_router.post("/resetPassword")
def resetPassword(resetRequest:ResetPassword,session:Session=Depends(Session)):
    status,response=session.isAuthenticated(required=False)
    if(status):
        response.status_code=400
        response.modify(content={
            "msg":"Already logged in.Logout to continue "
        })
        return response
    
    response=resetRequest.changePassword()
    return response

@user_router.get("/dashboard")
def dashboard(session:Session=Depends(Session)):
    try:
        response=session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]
    
    user=(User.objects(_id=session.user_id).only('_id','email','userName')).first()
    
    files=Files.objects(owner=session.user_id).only('_id','status','doc_type','json','timestamp').to_json()
    files=json.loads(files)
    for i in range(len(files)):
        try:
            files[i]['json']=json.loads(files[i]['json'])
        except:
            files[i]['json']={}

    response=JSONResponse(status_code=200,content={
        "email":user.email,
        "user_id":user._id,
        "user_name":user.userName,
        "files":files,
    })
    return response


@user_router.get("/drive")
def dashboard(session:Session=Depends(Session)):
    try:
        response=session.isAuthenticated(required=True)
    except RuntimeError as e:
        return e.args[0]
    try:
        link=DriveMap.objects(owner=session.user_id).first()
        return {"drive":link.gdrive}
    except:
        return JSONResponse(status_code=400,content={"msg":"No drive for user created."})