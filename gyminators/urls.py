from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static as serve_media

urlpatterns=[path("django-admin/",admin.site.urls),path("",include("website.urls"))]
if settings.DEBUG:
    urlpatterns += serve_media(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
