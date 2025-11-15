from django.contrib import admin
from django.urls import path, include
from .views import hello_world
from django.conf import settings
from django.conf.urls.static import static

from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

schema_view = get_schema_view(
    openapi.Info(
        title="Dropz API",
        default_version="v1",
        description="API documentation",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("hello/", hello_world),
    path("api/", include("accounts.urls")),
    path("api/", include("addresses.urls")),
    path("api/", include("products.urls")),
    path("api/", include("carts.urls")),
    path("api/", include("wishlists.urls")),
    path("api/support/", include("support.urls")),
    path("api/payments/", include("payments.urls")),
    path("api/", include("orders.urls")),
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="swagger-ui",
    ),
    path(
        "redoc/",
        schema_view.with_ui("redoc", cache_timeout=0),
        name="redoc-ui",
    ),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
