from common.images import ImageUploadError, upload_image


class ClothingImageUploadMixin:
    def form_valid(self, form):
        image = form.cleaned_data.get("new_image")
        if image is not None:
            try:
                picture = upload_image(
                    image,
                    folder=f"swapify/clothing/{self.request.user.pk}",
                )
            except ImageUploadError as error:
                form.add_error("new_image", str(error))
                return self.form_invalid(form)
            form.instance.image = picture
        return super().form_valid(form)
