"""
REST API контроллеры для приложения users.
Реализует требования раздела 3.7 ТЗ (JWT-аутентификация, регистрация).
"""

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from users.serializers import UserRegistrationSerializer


class UserRegistrationAPIView(APIView):
    """
    POST /api/users/register/

    Регистрация нового пользователя через REST API.
    Возвращает 201 Created с данными пользователя и JWT-токенами.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                'user': serializer.data,
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                },
            },
            status=status.HTTP_201_CREATED,
        )
