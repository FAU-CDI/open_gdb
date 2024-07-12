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
- Django Admin: Once the docker compose stack is deployed the Django admin interface is available on `localhost/admin`. You can login with the credentials you set int the `.env`.
- For debugging purposes there's a second RDF4J running on port `9999` that only serves the RDF4J workbench (access via `localhost:9999/rdf4j-workbench`). Some context: The RDF4J container serves both the workbench (`/rdf4j-workbench`) and the actual server (`/rdf4j-server`). Whenever the workbench has to talk to the server this is done via HTTP over the local network. Unfortunately it is not possible to set the outgoing proxy only for the server. This leads to requests from the workbench also being caught/denied by the outgoing proxy. A temporary solution is this second RDF4J server that does not use the outgoing proxy. To see what's going on in the actual RDF4J server you have to set the `RDF4J-Server-URL` to `http://rdf4j:8080/rdf4j-server` in the workbench interface.
- [RDF4J Routes](https://rdf4j.org/documentation/reference/rest-api/) are available (Graph Store, Transactions, and Protocol are not implemented yes)
- [GraphDB Routes](https://graphdb.ontotext.com/documentation/10.0/using-the-graphdb-rest-api.html) for repository and user management are also available
  - User management: `/rest/security/users`
  - Repository managent: `/rest/repositories/`

## Future development:
- Ideally we want to make this a drop in replacement for the GraphBB server that also works with the standalone [GraphDB Workbench](https://github.com/Ontotext-AD/graphdb-workbench)
