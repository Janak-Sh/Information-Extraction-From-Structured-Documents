import smtplib
from pydantic import BaseSettings
from fastapi.logger import logger
from email.message import Message
import imaplib
from email import message_from_bytes
from uuid import uuid1
class Config(BaseSettings):
    EMAIL: str
    PASSWORD: str

    def __init__(self):
        super().__init__()

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'


class Email:
    def __init__(self):
        config = Config()
        config = {
            'email': config.EMAIL,
            'password': config.PASSWORD
        }

        logger.info(f"{__name__} Logging in... to email {config['email']}")
        smtp = smtplib.SMTP('smtp.gmail.com', 587)
        smtp.starttls()
        EMAIL = config['email']
        PASSWORD = config['password']
        smtp.login(EMAIL, PASSWORD)
        self.SMTP = smtp
        imap = imaplib.IMAP4_SSL("imap.gmail.com")
        imap.login(config['email'], config['password'])
        imap.select('Inbox')
        self.imap=imap
    
    def get_email(self):
        tmp, messages = self.imap.search(None, 'UNSEEN')
        all=[]
        for num in messages[0].split():
            # Retrieve email message by ID
            typ, msg_data = self.imap.fetch(num, '(RFC822)')
            msg=message_from_bytes(msg_data[0][1])
            ids=[]
            for part in msg.walk():
                if part.get_content_maintype() == 'multipart' or part.get('Content-Disposition') is None:
                    continue

                file=part.get_filename()                
                if(file):
                    fname="./documents/"+str(uuid1())+"."+file.split('.')[-1]
                    open(fname,'wb').write(part.get_payload(decode=True))
                    ids.append({"filename":file,"path":fname})
            all.append(
                {
                    "subject":msg["Subject"],
                    "email":msg["From"],
                    "mapping":ids
                }
            )
        return all

            

    def send_email(self, email, text):
        msg = Message()
        msg['Subject'] = 'Password Reset'
        msg['From'] = self.SMTP.user
        msg['To'] = email
        msg.add_header('Content-Type','text/html')
        msg.set_payload(f'<b>{text}</b>')
        try:
            logger.info(f"{__name__} sending email to {email}")
            self.SMTP.sendmail(self.SMTP.user, email, msg.as_string())
        except:
            logger.error(f"{__name__} user doesnt exist")


    def send_image(self,email,image_url):
        msg = Message()
        msg['Subject'] = 'What subject to put here'
        msg['From'] = self.SMTP.user
        msg['To'] = email
        msg.add_header('Content-Type','text/html')
        msg.set_payload(f'<b>Hello</b><br/><img src="{image_url}"/>')
        try:
            logger.info(f"{__name__} sending email to {email}")
            self.SMTP.sendmail(self.SMTP.user, email, msg.as_string())
        except:
            logger.info(f"{__name__} user doesnt exist")


email = Email()