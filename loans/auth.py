from django.utils import timezone
from rest_framework import authentication
from rest_framework import exceptions

from loans.models import ClientAccessToken, hash_value


class ClientTokenAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith(f"{self.keyword} "):
            return None

        raw_token = auth_header.split(" ", 1)[1].strip()
        token_hash = hash_value(raw_token)

        try:
            token_obj = ClientAccessToken.objects.select_related("client").get(token_hash=token_hash)
        except ClientAccessToken.DoesNotExist as exc:
            raise exceptions.AuthenticationFailed("Invalid client token") from exc

        if not token_obj.is_active():
            raise exceptions.AuthenticationFailed("Expired or revoked client token")

        token_obj.last_used_at = timezone.now()
        token_obj.save(update_fields=["last_used_at"])
        return token_obj.client, token_obj
