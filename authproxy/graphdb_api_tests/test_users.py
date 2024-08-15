import json

from .helpers import (
    post_user,
    put_user,
    get_user,
    patch_user,
    delete_user,
    censor_password,
    change_password,
)
from .test_data import (
    BASE_URL,
    ADMIN,
    USER_READ_TEST,
    CHANGED_APP_SETTINGS,
    CHANGED_PASSWORD,
    DEFAULT_PASSWORD,
)


class BaseTest:
    """A base test case that builds test cases."""

    def pytest_generate_tests(self, metafunc):
        if all(
            name in ["auth", "user", "create", "delete", "expected", "request"]
            for name in metafunc.fixturenames
        ):
            metafunc.parametrize(
                "auth, user, create, delete, expected",
                self.__class__.get_test_cases(),
                indirect=True,
            )
        elif all(
            name
            in ["auth", "user", "create", "delete", "settings", "expected", "request"]
            for name in metafunc.fixturenames
        ):
            metafunc.parametrize(
                "auth, user, create, delete, settings, expected",
                self.__class__.get_test_cases(),
                indirect=True,
            )

    @classmethod
    def get_test_cases(cls) -> list[tuple]:
        """Return the test cases for this class"""
        return []


class TestPost(BaseTest):
    """Test the POST method for the /rest/security/users/{username} route"""

    @classmethod
    def get_test_cases(cls):
        # (Authentication User, User to add, if the user should exist before post, expected status code and message text)
        return [
            (
                ADMIN,
                ADMIN,
                False,
                False,
                {
                    "status_code": 400,
                    "text": "An account with the given username already exists.",
                },
            ),
            (
                USER_READ_TEST,
                USER_READ_TEST,
                False,
                False,
                {"status_code": 401, "text": "Unauthorized (HTTP status 401)\n"},
            ),
            (
                USER_READ_TEST,
                USER_READ_TEST,
                True,
                True,
                {"status_code": 403, "text": "Forbidden (HTTP status 403)\n"},
            ),
            (
                ADMIN,
                USER_READ_TEST,
                True,
                True,
                {
                    "status_code": 400,
                    "text": "An account with the given username already exists.",
                },
            ),
            (ADMIN, USER_READ_TEST, False, True, {"status_code": 201, "text": ""}),
        ]

    def test_post(self, auth, user, create, delete, expected):
        response = post_user(BASE_URL, auth, user)
        assert response.status_code == expected["status_code"]
        assert response.text == expected["text"]
        # TODO: do a get here to verify the settings are correct?


class TestGet(BaseTest):
    """Test the GET method for the /rest/security/users/{username} route"""

    @classmethod
    def get_test_cases(cls) -> list[tuple]:
        # (Authentication User, User to add, if the user should exist before post, expected status code and message text)
        return [
            (
                ADMIN,
                ADMIN,
                False,
                False,
                {"status_code": 200, "json": censor_password(ADMIN)},
            ),
            (
                USER_READ_TEST,
                USER_READ_TEST,
                False,
                False,
                {"status_code": 401, "text": "Unauthorized (HTTP status 401)\n"},
            ),
            (
                ADMIN,
                USER_READ_TEST,
                True,
                True,
                {"status_code": 200, "json": censor_password(USER_READ_TEST)},
            ),
            (
                USER_READ_TEST,
                USER_READ_TEST,
                True,
                True,
                {"status_code": 200, "json": censor_password(USER_READ_TEST)},
            ),
            (ADMIN, USER_READ_TEST, False, False, {"status_code": 404, "text": ""}),
        ]

    def test_get(self, auth, user, create, delete, expected):
        response = get_user(BASE_URL, auth, user)
        assert response.status_code == expected["status_code"]
        try:
            assert response.json() == expected["json"]
        except json.JSONDecodeError:
            assert response.text == expected["text"]


class TestPut(BaseTest):
    """Test the PUT method for the /rest/security/users/{username} route"""

    @classmethod
    def get_test_cases(cls) -> list[tuple]:
        return [
            # Admin user can change password
            (
                ADMIN,
                ADMIN,
                False,
                False,
                change_password(ADMIN, CHANGED_PASSWORD),
                {"status_code": 200, "text": ""},
            ),
            # Admin user cannot login with the old password
            (
                ADMIN,
                ADMIN,
                False,
                False,
                ADMIN,
                {"status_code": 401, "text": "Unauthorized (HTTP status 401)\n"},
            ),
            # Change admin user password back to to old password
            (
                change_password(ADMIN, CHANGED_PASSWORD),
                ADMIN,
                False,
                False,
                change_password(ADMIN, DEFAULT_PASSWORD),
                {"status_code": 200, "text": ""},
            ),
            # Unauthorized user cannot change settings
            (
                USER_READ_TEST,
                USER_READ_TEST,
                False,
                False,
                USER_READ_TEST,
                {"status_code": 401, "text": "Unauthorized (HTTP status 401)\n"},
            ),
            # Logged in normal user is forbidden from changing settings
            (
                USER_READ_TEST,
                USER_READ_TEST,
                True,
                True,
                USER_READ_TEST,
                {"status_code": 403, "text": "Forbidden (HTTP status 403)\n"},
            ),
            # Admin can change password
            (
                ADMIN,
                USER_READ_TEST,
                True,
                True,
                USER_READ_TEST,
                {"status_code": 200, "text": ""},
            ),
            (
                ADMIN,
                USER_READ_TEST,
                False,
                False,
                USER_READ_TEST,
                {"status_code": 404, "text": ""},
            ),
        ]

    def test_put(self, auth, user, create, delete, settings, expected):
        response = put_user(BASE_URL, auth, user, settings)
        assert response.status_code == expected["status_code"]
        try:
            assert response.json() == expected["json"]
        except (json.JSONDecodeError, KeyError):
            assert response.text == expected["text"]


class TestPatch(BaseTest):
    """Test the PATCH method for the /rest/security/users/{username} route"""

    @classmethod
    def get_test_cases(cls) -> list[tuple]:
        return [
            (ADMIN, ADMIN, False, False, None, {"status_code": 200, "text": ""}),
            (
                USER_READ_TEST,
                USER_READ_TEST,
                False,
                False,
                None,
                {"status_code": 501, "text": ""},
            ),
            (
                USER_READ_TEST,
                USER_READ_TEST,
                True,
                True,
                None,
                {"status_code": 200, "text": ""},
            ),
            (
                USER_READ_TEST,
                USER_READ_TEST,
                True,
                True,
                CHANGED_APP_SETTINGS,
                {"status_code": 200, "text": ""},
            ),
            (
                ADMIN,
                USER_READ_TEST,
                True,
                True,
                CHANGED_APP_SETTINGS,
                {"status_code": 200, "text": ""},
            ),
            (
                ADMIN,
                USER_READ_TEST,
                False,
                False,
                None,
                {"status_code": 404, "text": ""},
            ),
        ]

    def test_patch(self, auth, user, create, delete, settings, expected):
        response = patch_user(BASE_URL, auth, user, settings)
        assert response.status_code == expected["status_code"]
        try:
            assert response.json() == expected["json"]
        except json.JSONDecodeError:
            assert response.text == expected["text"]


class TestDelete(BaseTest):

    @classmethod
    def get_test_cases(cls) -> list[tuple]:
        return [
            (
                ADMIN,
                ADMIN,
                False,
                False,
                {
                    "status_code": 500,
                    "json": {
                        "message": "Deleting the default admin user is not allowed!"
                    },
                },
            ),
            (
                USER_READ_TEST,
                USER_READ_TEST,
                False,
                False,
                {"status_code": 401, "text": "Unauthorized (HTTP status 401)\n"},
            ),
            (
                USER_READ_TEST,
                USER_READ_TEST,
                True,
                True,
                {"status_code": 403, "text": "Forbidden (HTTP status 403)\n"},
            ),
            (
                ADMIN,
                USER_READ_TEST,
                True,
                True,
                {"status_code": 204, "text": ""},
            ),
            (
                ADMIN,
                USER_READ_TEST,
                False,
                False,
                {"status_code": 404, "text": ""},
            ),
        ]

    def test_delete(self, auth, user, create, delete, expected):
        response = delete_user(BASE_URL, auth, user)
        assert response.status_code == expected["status_code"]
        try:
            assert response.json() == expected["json"]
        except (json.JSONDecodeError, KeyError):
            assert response.text == expected["text"]
