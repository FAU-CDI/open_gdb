from rest_framework.authentication import TokenAuthentication


class GDBTokenAuthentication(TokenAuthentication):
    keyword = "GDB"
