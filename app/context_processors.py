from django.conf import settings

def ad_image_url(request):
    return {
        'AD_IMAGE_URL': settings.AD_IMAGE_URL,
        'TOP_AD_IMAGE_URL': settings.TOP_AD_IMAGE_URL,
        'MIDDLE_AD_IMAGE_URL_1': settings.MIDDLE_AD_IMAGE_URL_1,
        'MIDDLE_AD_IMAGE_URL_2': settings.MIDDLE_AD_IMAGE_URL_2,
        'MIDDLE_AD_IMAGE_URL_3': settings.MIDDLE_AD_IMAGE_URL_3,
    } 