import smtplib
import os
from dotenv import load_dotenv

def mailotp(email,subject,message):
    load_dotenv()
    sender_mail=os.getenv('sender_mail')
    sender_pass=os.getenv('password')
    server=smtplib.SMTP('smtp.gmail.com',587)
    server.starttls()
    server.login(sender_mail,sender_pass)
    server.sendmail(sender_mail, email, f"Subject: {subject}\n\n{message}")

    server.quit()

    return 'Successfully'

