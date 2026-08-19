#!/usr/bin/env python3
import cv2
from datetime import datetime
import time
import os

#Variables for testing
battery_response = 69 #Battery charge in percentage, shgould be between 0 and 100
triggerType = 1 #PIR [1] PING [2] or REED [3]
signalStrength = 69 #Signal strength in percentage, should be between 0 and 100
TRAPID = "7A01k63jG5Gma3yQpLky" #Trap ID, please change this to your trap ID

def take_image():
    try:
        # Initialize the webcam
        # If you have multiple cameras on your system, you may need to adjust the index.
        cap = cv2.VideoCapture(0)  # default camera
        # Check if the webcam is opened correctly
        if not cap.isOpened():
            raise IOError("Cannot open webcam")
        ret, frame = cap.read()
        fileName = "img-" + datetime.now().strftime("%d-%m-%Y-%H-%M-%S") + ".jpg"
        if ret:
            # Save the captured image to a file
            cv2.imwrite(fileName, frame)
        # Release the webcam
        cap.release()
        return fileName if ret else False
    except Exception as e:
        print(f"Exception in taking image: {e}")
        time.sleep(1)
        return False

# Capture image first
_fn = take_image()
# Then import the rest of your modules
from firebase_admin import initialize_app, credentials, storage, firestore
cred_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "trapapp-2f398-firebase-adminsdk-67nij-92340d351d.json")
cred = credentials.Certificate(cred_path)
initialize_app(cred, {"storageBucket": "trapapp-2f398.appspot.com"})

def registerImage(_tid, batVal, signalStrength, triggerType):
    db = firestore.client()
    data = {
        u'server_ts': firestore.SERVER_TIMESTAMP,
        u'trap_id': _tid,
        u'battery_charge': batVal,
        u'signal_strength': signalStrength,
        u'trigger_type': triggerType,
    }
    update_time, image_ref = db.collection(u'imageInbox').add(data)

    return image_ref.id

def uploadImage(_fn, _iid):
    # Put your local file path 
    bucket = storage.bucket()
    blob = bucket.blob('images/'+_iid +'/'+_fn)
    blob.upload_from_filename(_fn)
    # Opt : if you want to make public access from the URL
    blob.make_public()
    return blob.public_url

def deleteImage(_fn):
    os.remove(_fn)

def updateImageReference(_iid, _url):
    db = firestore.client()
    data = {
        u'url': _url,
    }
    update_time = db.collection(u'imageInbox').document(_iid).set(data,merge=True)

def main(_fn, battery_response):
    _iid = registerImage(TRAPID, battery_response, signalStrength, triggerType)
    _url = uploadImage(_fn, _iid)
    updateImageReference(_iid, _url)
    deleteImage(_fn)
            
if __name__ == "__main__":
    main(_fn, battery_response)

