# Security
## No auth headers
| Route | Method | Code | Message |
|-------|--------|------|---------|
| /rest/security | GET | 200 | OK |
| /rest/security | POST | 401 | Unauthorized |
| /rest/security/free-access | GET | 200 | OK |
| /rest/security/free-access | POST | 401 | Unauthorized |
| /rest/security/users | GET | 401 | Unauthorized |
| /rest/security/users/Test | DELETE | 401 | Unauthorized |
| /rest/security/users/Test | GET | 401 | Unauthorized |
| /rest/security/users/Test | PATCH | 501 | Not Implemented |
| /rest/security/users/Test | POST | 401 | Unauthorized |
| /rest/security/users/Test | PUT | 401 | Unauthorized |
## User with write access to the test repo
| Route | Method | Code | Message |
|-------|--------|------|---------|
| /rest/security | GET | 200 | OK |
| /rest/security | POST | 403 | Forbidden |
| /rest/security/free-access | GET | 200 | OK |
| /rest/security/free-access | POST | 403 | Forbidden |
| /rest/security/users | GET | 403 | Forbidden |
| /rest/security/users/Test | DELETE | 403 | Forbidden |
| /rest/security/users/Test | GET | 200 | OK |
| /rest/security/users/Test | PATCH | 500 | Internal Server Error |
| /rest/security/users/Test | POST | 403 | Forbidden |
| /rest/security/users/Test | PUT | 403 | Forbidden |
## Admin user
| Route | Method | Code | Message |
|-------|--------|------|---------|
| /rest/security | GET | 200 | OK |
| /rest/security | POST | 500 | Internal Server Error |
| /rest/security/free-access | GET | 200 | OK |
| /rest/security/free-access | POST | 500 | Internal Server Error |
| /rest/security/users | GET | 200 | OK |
| /rest/security/users/Test | DELETE | 204 | No Content |
| /rest/security/users/Test | GET | 404 | Not Found |
| /rest/security/users/Test | PATCH | 500 | Internal Server Error |
| /rest/security/users/Test | POST | 500 | Internal Server Error |
| /rest/security/users/Test | PUT | 500 | Internal Server Error |
