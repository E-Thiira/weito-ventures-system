from drf_spectacular.extensions import OpenApiAuthenticationExtension


class ClientTokenAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "loans.auth.ClientTokenAuthentication"
    name = "ClientBearerAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "Token",
            "description": "Client portal access token from OTP verification",
        }
