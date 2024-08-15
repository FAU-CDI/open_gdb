# RDF4J:
We wanted to skip this and only serve the actual graphdb API.
This however does not work since the graphdb API does not provide any routes to the SPARQL endpoints, so we need to at least serve these.

| Unclear | Route                                     | Method | Short description           | Read | Write |
|---------|-------------------------------------------|--------|-----------------------------|------|-------|
|         | `/repositories`                           | GET    | List all repos              |  x   |       |
|    x    | `/repositories/{repositoryID}`            | DELETE | Delete repo                 |      |       |
|         | `/repositories/{repositoryID}/statements` | DELETE | Delete statments            |      |   x   |
|         | `/repositories/{repositoryID}/statements` | GET    | Fetch statements            |  x   |       |
|         | `/repositories/{repositoryID}/statements` | PUT    | Replace existing statements |      |   x   |
|         | `/repositories/{repositoryID}/size`       | GET    | Get repo size               |  x   |       |

The delete repo route is already covered by the graphDB api?


# GraphDB
The following permissions need to be checked how they actually work

## Repository Management controller
Basically these should only be accessible by admins except.
Read and write refer to the specific repos' read and write permissions.
`View`, `Delete` `Add` and `Edit` refer to the specific Django permissions on the `Repository` model.

| Route                                        | Method | Short description | Read | Write | Admin | ViewRepo | DeleteRepo | AddRepo | EditRepo |
|----------------------------------------------|--------|-------------------|------|-------|-------|----------|------------|---------|----------|
| `/rest/repositories`                         | GET    | List all repos    |  x   |       |   x   |    x     |            |         |          |
| `/rest/repositories`                         | POST   | Create repo       |      |       |   x   |          |            |    x    |          |
| `/rest/repositories/{repositoryID}`          | DELETE | Delete repo       |      |       |   x   |          |      x     |         |          |
| `/rest/repositories/{repositoryID}`          | GET    | Get Repo config   |  x   |       |   x   |    x     |            |         |          |
| `/rest/repositories/{repositoryID}`          | PUT    | Edit repo config  |      |   x   |   x   |          |            |         |    x     |
| `/rest/repositories/{repositoryID}/restart`  | POST   | Restart a repo    |      |   x   |   x   |          |            |         |    x     |
| `/rest/repositories/{repositoryID}/size`     | GET    | Get repo size     |  x   |       |   x   |    x     |            |         |          |

## Security Management Controller
Do we even want/need free-access? probably not.
`View`, `Delete` `Add` and `Edit` refer to the specific Django permissions on the `User` model.

| Route                             | Method | Short description            | ViewUser | DeleteUser | AddUser | EditUser |
|-----------------------------------|--------|------------------------------|----------|------------|---------|----------|
| `/rest/security`                  | GET    | Check if security is enabled |          |            |         |          |
| `/rest/security`                  | POST   | Enable or disable Security   |          |            |         |          |
| `/rest/security/free-access`      | GET    | Check if free access is on   |          |            |         |          |
| `/rest/security/free-access`      | POST   | En or disable free access    |          |            |         |          |
| `/rest/security/users`            | GET    | Get all users                |     x    |            |         |          |
| `/rest/security/users/{username}` | DELETE | Delete a user                |          |     x      |         |          |
| `/rest/security/users/{username}` | GET    | Get a user                   |     x    |            |         |          |
| `/rest/security/users/{username}` | PATCH  | Change settings for user     |          |            |         |    x     |
| `/rest/security/users/{username}` | POST   | Create user                  |          |            |    x    |          |
| `/rest/security/users/{username}` | PUT    | Edit a user                  |          |            |         |    x     |

## Stateless Login Controller
only has `/rest/login` should be available to every user and return a token?


## Notes:
- `Locations` are for external GraphDB instances that can also be managed by the frontend
- Oddities with the GraphDB `users` API
    - When editing a user with `PUT` only the last role in `grantedAuthorities` is assigned, not the one with the highest/lowest permissions
    - `POST` AND `PUT` just ignore non relevant keys in the data
    - cannot change a users name


