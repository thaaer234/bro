# import logging
# import os

# import firebase_admin
# from firebase_admin import credentials
# from django.conf import settings


# logger = logging.getLogger(__name__)


# def init_firebase():
#     if firebase_admin._apps:
#         return

#     cred_path = settings.FIREBASE_SERVICE_ACCOUNT
#     if not cred_path:
#         logger.warning("FIREBASE_SERVICE_ACCOUNT is not set.")
#         return

#     if not os.path.exists(cred_path):
#         logger.warning("Firebase service account file not found: %s", cred_path)
#         return

#     cred = credentials.Certificate(cred_path)
#     firebase_admin.initialize_app(cred)
