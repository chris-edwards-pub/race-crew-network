import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://racecrew:racecrew@localhost:3306/racecrew",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB max upload
    PROFILE_IMAGE_MAX_BYTES = 10 * 1024 * 1024
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
    BUCKET_NAME = os.environ.get("BUCKET_NAME", "")
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
    SES_ACCESS_KEY_ID = os.environ.get("SES_ACCESS_KEY_ID", "")
    SES_SECRET_ACCESS_KEY = os.environ.get("SES_SECRET_ACCESS_KEY", "")
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
