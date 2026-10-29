import logging

import cloudinary
from cloudinary import uploader
from cloudinary.exceptions import AuthorizationRequired, NotAllowed
from cloudinary.exceptions import Error as CloudinaryError
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


class ImageUploadError(Exception):
    pass


def validate_uploaded_image(image):
    """Validate an image after Django's ImageField has decoded its contents."""
    if image.size > MAX_IMAGE_BYTES:
        raise ValidationError("Choose an image smaller than 5 MB.")
    if image.image.format not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError("Choose a JPG, PNG, or WebP image.")


def upload_image(image, *, folder):
    config = cloudinary.config()
    if not all((config.cloud_name, config.api_key, config.api_secret)):
        raise ImageUploadError("Image uploads are unavailable. Please try again later.")

    try:
        image.seek(0)
        return uploader.upload_image(
            image,
            resource_type="image",
            folder=folder,
            use_filename=False,
            overwrite=False,
            timeout=30,
        )
    except AuthorizationRequired as error:
        # Never log raw provider errors: they can contain credentials.
        logger.warning(
            "Cloudinary rejected the upload credentials. Check the cloud name, "
            "API key and API secret for the selected product environment."
        )
        raise ImageUploadError(
            "Image uploads are unavailable. Please try again later."
        ) from error
    except NotAllowed as error:
        logger.warning(
            "Cloudinary denied asset creation. Check upload/create permissions "
            "for this API key and destination folder."
        )
        raise ImageUploadError(
            "Image uploads are unavailable. Please try again later."
        ) from error
    except CloudinaryError as error:
        logger.warning("Cloudinary upload failed (%s).", type(error).__name__)
        raise ImageUploadError(
            "Your image could not be uploaded. Please select it again and try again."
        ) from error
