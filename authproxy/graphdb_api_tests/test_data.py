BASE_URL = "http://localhost:7200/"

DEFAULT_PASSWORD = "123456789"
CHANGED_PASSWORD = "987654321"

DEFAULT_APP_SETTINGS = {
    "DEFAULT_INFERENCE": True,
    "DEFAULT_SAMEAS": True,
    "DEFAULT_VIS_GRAPH_SCHEMA": True,
    "EXECUTE_COUNT": True,
    "IGNORE_SHARED_QUERIES": False,
}

CHANGED_APP_SETTINGS = {
    "DEFAULT_INFERENCE": False,
    "DEFAULT_SAMEAS": False,
    "DEFAULT_VIS_GRAPH_SCHEMA": False,
    "EXECUTE_COUNT": False,
    "IGNORE_SHARED_QUERIES": True,
}

TEST_READ_ACCESS = ["ROLE_USER", "READ_REPO_Test"]
ROLE_REPO_MANAGER = ["ROLE_REPO_MANAGER"]
ROLE_ADMIN = ["ROLE_ADMIN"]

USER_READ_TEST = {
    "username": "user_read_test",
    "password": DEFAULT_PASSWORD,
    "grantedAuthorities": TEST_READ_ACCESS,
    "appSettings": DEFAULT_APP_SETTINGS,
    "dateCreated": 1713778150153,
}

ADMIN = {
    "username": "admin",
    "password": DEFAULT_PASSWORD,
    "grantedAuthorities": ROLE_ADMIN,
    "appSettings": DEFAULT_APP_SETTINGS,
    "dateCreated": 1713778150153,
}
