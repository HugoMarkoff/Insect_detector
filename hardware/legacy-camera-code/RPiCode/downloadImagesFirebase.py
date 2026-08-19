import os
import requests
import firebase_admin
from firebase_admin import credentials, firestore

# Function to sanitize file names for Windows
def sanitize_filename(filename):
    return "".join([c if c not in r'\/:*?"<>|' else '_' for c in filename])

# Function to download images
def download_image(url, local_path):
    # Check if the file already exists
    if not os.path.exists(local_path):
        response = requests.get(url)
        if response.status_code == 200:
            with open(local_path, 'wb') as file:
                file.write(response.content)
        else:
            print(f"Failed to download {url}")
    else:
        print(f"File already exists: {local_path}")

# Initialize Firebase Admin SDK assuming the credentials file is in the same directory as this python file
current_dir = os.path.dirname(os.path.abspath(__file__))
cred_path = os.path.join(current_dir, "trapapp-2f398-firebase-adminsdk-67nij-92340d351d.json")
cred = credentials.Certificate(cred_path)

firebase_admin.initialize_app(cred, {
    'storageBucket': 'trapapp-2f398.appspot.com'
})

# Firestore Client
db = firestore.client()

# Define the Firestore path to the sub-collection and the local download directory
user = 'hr3RHNUqanOm1F6AZj81a8gV7f73'
trap = 'EpQ5VUnnrwaUaZrK1tEC'
images_collection_path = 'users/{}/traps/{}/images'.format(user, trap)
local_download_dir = 'C:/Users/hma/Desktop/downloaded_images/{}/{}'.format(user, trap)

# Create the local directory if it does not exist
if not os.path.exists(local_download_dir):
    os.makedirs(local_download_dir)

# Access the sub-collection and download each image
print(f"Fetching documents from Firestore collection '{images_collection_path}'...")
image_docs = db.collection(images_collection_path).stream()

image_count = 0
for doc in image_docs:
    image_count += 1
    doc_dict = doc.to_dict()
    if 'url' in doc_dict:
        image_url = doc_dict['url']
        # Splitting the URL and inserting 'raw_' before the filename
        #url_parts = image_url.rsplit('/', 1)
        #modified_url = f"{url_parts[0]}/raw_{url_parts[1]}"

        file_name = sanitize_filename(requests.utils.unquote(image_url.split('/')[-1]))
        local_file_path = os.path.join(local_download_dir, file_name)
        print(f"Checking image: {file_name}")
        download_image(image_url, local_file_path)

print(f"Process complete. {image_count} images checked.")

