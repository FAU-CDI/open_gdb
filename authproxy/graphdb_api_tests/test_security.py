import requests
import json
import pytest

from http.client import responses
from urllib.parse import urljoin


SECURITY_ROUTES = {
    "/rest/security": ["GET", "POST"],
    "/rest/security/free-access": ["GET", "POST"],
    "/rest/security/users/Test": ["POST", "GET", "PATCH", "PUT", "DELETE"],
    "/rest/security/users": ["GET"],
}


# @pytest.mark.parametrize("user_id, expected_name, expected_age", [
#     (1, 'Alice', 30),
#     (2, 'Bob', 40),
#     (3, 'Charlie', 50),
#     (4, None, None),
# ])


def tttest_user_route():
    admin_auth = get_auth(admin)
    user_read_test_auth = get_auth(user_read_test)

    return

    # Try to de delete admin user
    response = delete_user(admin_auth, admin)
    assert (
        response.text
        == """{"message":"Deleting the default admin user is not allowed!"}"""
    )
    assert response.status_code == 500

    # Get admin user
    response = get_user(admin_auth, admin)
    assert response.status_code == 200

    # Get non existing user
    response = get_user(admin_auth, user_read_test)
    assert response.status_code == 404

    # Create user_read_test
    response = post_user(admin_auth, user_read_test)
    assert response.status_code == 201

    # Get user_read_test
    response = get_user(admin_auth, user_read_test)
    assert response.status_code == 200

    # Change appSettings for user_read_test
    response = patch_user(admin_auth, user_read_test)
    assert response.status_code == 200

    # Check if the changes went through
    response = get_user(admin_auth, user_read_test)
    assert response.status_code == 200
    assert json.loads(response.text)["appSettings"] == changed_settings

    # Change permissions and password for user_read_test
    user_read_test["password"] = CHANGED_PASSWORD
    user_read_test["grantedAuthorities"] = ["ROLE_USER"]
    # When putting nonsense into granted Authorities
    # {
    #   "message": "Unknown authority. One of READ_REPO_xxx, WRITE_REPO_xxx, ROLE_USER, ROLE_MONITORING, ROLE_REPO_MANAGER, ROLE_CLUSTER, ROLE_ADMIN is required."
    # }

    response = put_user(admin_auth, user_read_test)
    assert response.status_code == 200
    assert json.loads(response.text)["appSettings"] == changed_settings

    # Delete user_read_test
    response = delete_user(admin_auth, user_read_test)
    assert response.status_code == 204


def print_results(results: dict):
    print("| Route | Method | Code | Message |")
    print("|-------|--------|------|---------|")
    for route, methods in results.items():
        for method in methods:
            status_code = results[route][method]
            print(
                "|",
                route,
                "|",
                method,
                "|",
                status_code,
                "|",
                responses[status_code],
                "|",
            )


print("# Security")
# for user in users:
#     print(f"## {user['description']}")
#     print_results(test_security(user))
