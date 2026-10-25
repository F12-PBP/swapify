from common.images import ImageUploadError, upload_image


class ProfilePhotoUploadError(ImageUploadError):
    pass


def upload_profile_picture(image, user_id):
    try:
        return upload_image(
            image,
            folder=f"swapify/profile-pictures/{user_id}",
        )
    except ImageUploadError as error:
        raise ProfilePhotoUploadError(str(error)) from error
