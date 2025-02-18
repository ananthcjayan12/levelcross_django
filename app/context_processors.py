from django.conf import settings

def ad_image_url(request):
    return {'AD_IMAGE_URL': settings.AD_IMAGE_URL} 