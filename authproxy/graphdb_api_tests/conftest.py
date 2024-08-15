import pytest

from .helpers import get_auth, post_user, delete_user
from .test_data import BASE_URL, ADMIN


@pytest.fixture
def auth(request):
    yield get_auth(request.param)


@pytest.fixture
def user(request):
    yield request.param


@pytest.fixture
def create(request, user):
    # Create the user with the default admin account in case it should exist before running the test
    if request.param:
        post_user(BASE_URL, get_auth(ADMIN), user)
    yield request.param


@pytest.fixture
def delete(request, user):
    yield request.param
    if request.param:
        delete_user(BASE_URL, get_auth(ADMIN), user)


@pytest.fixture
def settings(request):
    yield request.param


@pytest.fixture
def expected(request):
    yield request.param
