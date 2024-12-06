# Open GDB
Implementation of graph database including user and repository management based on RDF4J.

## Architecture:
The service consists of:
1. [nginx](https://nginx.org/en/): reverse proxy that handles all incoming traffic
2. [authproxy](https://github.com/FAU-CDI/authproxy): [Django](https://www.djangoproject.com/) based authentication proxy for RDF4J that handles user and repository management
3. [RDF4J](https://rdf4j.org/): Serves as the triplestore backend
4. [outproxy](https://github.com/FAU-CDI/outproxy): An outgoing proxy that blocks all outgoing requests into the local network. RDF4J uses this proxy for outgoing traffic to prevent users from accessing every RDF4J repository using SPARQL `SERVICE` strings that target `localhost`.


## Deployment
1. Rename `.env.sample` to `.env` and replace in the variables to your liking.
2. Deploy using `docker compose up --build -d`

## Usage:
Django Admin: Once the docker compose stack is deployed the Django admin interface is available on `localhost/admin`. You can login with the credentials you set int the `.env`.

In case you want to debug RDF4J there's `docker-compose.debug.yml`, which runs a second RDF4J on port `9999`.
This only serves the RDF4J workbench (access via `localhost:9999/rdf4j-workbench`).

Some context: The RDF4J container serves both the workbench (`/rdf4j-workbench`) and the actual server (`/rdf4j-server`).
Whenever the workbench has to talk to the server this is done via HTTP over the local network.
Unfortunately it is not possible to set the outgoing proxy only for the server.
This leads to requests from the workbench also being caught/denied by the outgoing proxy.
A temporary solution is running the second RDF4J server that does not use the outgoing proxy.
To see what's going on in the actual RDF4J server you have to set the `RDF4J-Server-URL` to `http://rdf4j:8080/rdf4j-server` in the workbench interface of the second RDF4J server.

## APIs:
- [RDF4J Routes](https://rdf4j.org/documentation/reference/rest-api/) are available (Graph Store, Transactions, and Protocol are not implemented yet)
- [GraphDB Routes](https://graphdb.ontotext.com/documentation/10.0/using-the-graphdb-rest-api.html) for repository and user management are also available
  - User management: `/rest/security/users`
  - Repository managent: `/rest/repositories/`

### Token authentication:
#### DISCLAIMER: Only use the token authentication if you are deploying `open_gdb` over HTTPS!
Since Django by default uses strong password hashing functions, authenticating Users in every API request takes a lot of time. (slows down requests by a factor of 30-50)
This is especially noticeable when you send a lot of API requests at once that are all authenticated via BasicAuth.

For this reason the authproxy has the option to use Token Authentication.
The endpoint for getting a token is `/api-token-auth/`.
Send a post request to this endpoint containing the credentials encoded in JSON format.

#### `curl` example
```bash
$ curl -X POST https://ts.my-domain.com/api-token-auth/ -d username=MY_USERNAME -d password=MY_PASSWORD
{"token": "SOME_TOKEN"}
# Now you can access the API like this
$ curl -X GET https://ts.my-domain.com/repositories -H 'Authorization: Token SOME_TOKEN'
```

#### Python example
```py
import requests

data = {
  "username": "MY_USERNAME",
  "password": "MY_PASSWORD"
}
token_response = requests.post("https://ts.my-domain.com/api-token-auth/", data=data)
token = token_response.json()['token']

# Now you can access the API like this
headers = { "Authorization": f"Token {token}"}
api_response = requests.get("https://ts.my-domain.com/repositories", headers=headers)
```

## Future development:
- Ideally we want to make this a drop in replacement for the GraphBB server that also works with the standalone [GraphDB Workbench](https://github.com/Ontotext-AD/graphdb-workbench)
