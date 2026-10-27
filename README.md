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
  - Repository management: `/rest/repositories/`

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

### Changing service names
In case you need to change the service/container names for the docker-compose project for whatever reason, you have to change the following:

- `rdf4j`:
    - Adjust `depends_on` and the `RDF4J_HOSTNAME` env variable in `nginx` and `authproxy` services
    - Adjust `depends_on` in `outproxy`
- `nginx`: Can just be renamed
- `authproxy`:
    - Adjust `depends_on` and the `AUTHPROXY_HOSTNAME` env variable in `nginx` service
- `outproxy`:
    - Adjust the `-Dhttp.proxyHost` and `-Dhttps.proxyHost` flags in the `JAVA_OPTS` in `rdf4j` service
    - Adjust `depends_on` in `nginx` service


## Change log

The `rdf4j` image contains a Sail that records every committed change of a repository in a reserved graph of the same repository, in the same transaction. [WissKI](https://wiss-ki.eu/) 5 reads it to refresh exactly the cached pages that a change affects, also after updates that bypass WissKI (scripts, the RDF4J Workbench, other systems). RDF4J itself has no change feed. Design decisions and performance measurements: [docs/change-log.md](docs/change-log.md).

### Requirements

- **WissKI 5 or later** on every repository with the change log. WissKI 4 does not know the log graph, and these features fail on such a repository:

  | WissKI 4 code | Query | Effect |
  |---|---|---|
  | `Sparql11EngineWithPB::deleteEntity()` | `DELETE { GRAPH ?g { ?s ?p <uri> } } WHERE { GRAPH ?g { ?s ?p <uri> } }` | The update also matches log entries and is rejected: recently edited entities can't be deleted. |
  | `wisski_merge` `Merger::engineReplaceUris()` | `INSERT { GRAPH ?g { ?s ?p <to> } } WHERE { … GRAPH ?g { ?s ?p ?o } }` | Rejected, so merging fails. |
  | `ReferencedEntityDeleter::referringEntityIds()` | `GRAPH ?g { ?s ?p ?o }` | Finds log entries as referrers and refuses to delete. |
  | `drush wisski-salz:export-nquads` / `import-nquads` | `GRAPH ?g { ?s ?p ?o }`, then N-Quads upload | The export contains the log; importing it is rejected. |
  | Triple counts, statistics, `ASK {{ <uri> ?p ?o } UNION { ?s ?p <uri> }}` | | Include the log; deleted entities still seem to exist. |

- The change log is therefore **off by default**. `RDF4J_CHANGELOG=1` (authproxy) creates new repositories with it; existing repositories are switched with `enable_changelog`.

### Configuration

New repositories with `RDF4J_CHANGELOG=1` get this store configuration (see `Repository.CHANGELOG_TEMPLATE`):

```turtle
config:sail.impl [
    config:sail.type "opengdb:ChangeLogSail" ;
    config:delegate [
        config:sail.type "openrdf:NativeStore" ;
        config:native.tripleIndexes "spoc,posc,cosp"
    ]
]
```

Optional parameters on the `opengdb:ChangeLogSail` node, with `@prefix cl: <tag:fau-cdi.github.io,2026:opengdb/changelog#>`:

| Parameter | Default | Meaning |
|---|---|---|
| `cl:slots` | 2000 | Records in the ring. Changing it starts a new epoch. |
| `cl:maxNodes` | 200 | More distinct IRIs in one transaction make a `cl:Summary` record. |
| `cl:maxTerms` | 100 | More predicates, classes or graphs make a `cl:Everything` record. |

### Switching existing repositories

```bash
# Repositories with one of authproxy's default templates; others are reported, not changed.
docker compose exec authproxy python manage.py enable_changelog --all --dry-run
docker compose exec authproxy python manage.py enable_changelog --all   # or name slugs
docker compose restart rdf4j
```

`enable_changelog` keeps each repository's triple indexes (older defaults differ, and changed indexes would make NativeStore rebuild them on start), checks the configuration RDF4J has stored, removes a stale log graph, and posts the new configuration to `/repositories/{id}/config`. That only rewrites `config.ttl`; RDF4J uses it after the restart, which affects all repositories of the server. Afterwards `GET /rdf4j-server/repositories/{id}/config` shows `opengdb:ChangeLogSail`, and the data size (`/size` minus `/size?context=<tag:fau-cdi.github.io,2026:opengdb/changelog>`) is unchanged.

Back to the plain store, for example before returning to WissKI 4:

```bash
docker compose exec authproxy python manage.py disable_changelog --all
docker compose restart rdf4j
docker compose exec authproxy python manage.py disable_changelog --all --purge-log
```

Never run a repository configured with `opengdb:ChangeLogSail` on the stock `eclipse/rdf4j-workbench` image: RDF4J can't load it without the Sail.

### Contract

WissKI keeps the namespace in one constant. Tell the WissKI side if anything here changes.

- Namespace `cl:` = `tag:fau-cdi.github.io,2026:opengdb/changelog#`, log graph `tag:fau-cdi.github.io,2026:opengdb/changelog`.
- State: `cl:state cl:epoch "uuid"` (a new value means the log restarted: refresh everything), `cl:state cl:slots "R"^^xsd:long`, and `cl:state cl:lastEverythingSlot cl:slot-k` / `cl:lastEverythingCycle "c"^^xsd:long` for the newest record with the scope "everything".
- Records: one per committed transaction that wrote statements. Revisions start at 1 and rise by exactly one per record, in commit order, without gaps; a failed commit doesn't use up its number. Record N is in slot `cl:slot-k` with `k = N mod R` and `cl:cycle c` with `c = N div R`, and replaces record N − R.

  | Triple | Meaning |
  |---|---|
  | `cl:slot-k cl:index "k"^^xsd:long`, `cl:cycle "c"^^xsd:long` | Revision `c × R + k`. |
  | `cl:slot-k cl:scope cl:Nodes / cl:Summary / cl:Everything` | Level of detail. |
  | `cl:slot-k cl:node <iri>` | Only with `cl:Nodes`: every IRI subject and IRI object of a written statement. |
  | `cl:slot-k cl:predicate <iri>`, `cl:class <iri>` | Predicates, and IRI objects of `rdf:type`. Not with `cl:Everything`. |
  | `cl:slot-k cl:graph <iri>` | Graphs; `cl:defaultGraph` for the default graph and for calls without a graph. With `cl:Everything`, no graph means all graphs. |

  | Scope | When |
  |---|---|
  | `cl:Nodes` | Up to `cl:maxNodes` distinct IRIs. |
  | `cl:Summary` | More IRIs, a blank-node or triple-term subject, or a remove with only the predicate bound. |
  | `cl:Everything` | Cleared graphs (also `DROP ALL`/`CLEAR ALL`, which keep the log), a remove bound only by graph, `rdf:type` removed by pattern, or more than `cl:maxTerms` predicates, classes or graphs. |

- Summary index for consumers that fell behind the ring: `cl:p-{h} cl:predicate <P>`, `cl:c-{h} cl:class <C>`, `cl:g-{h} cl:graph <G>`, each with `cl:lastSlot` and `cl:lastCycle` of the newest record that touched it. `{h}` is the first 16 hex digits of the SHA-256 of the IRI.
- Only IRIs are recorded, never literal values. Records reuse existing IRIs, so the log doesn't grow NativeStore's `values.dat` (it never frees values).
- Protection: adding to the log graph, removing with the log graph as context, and pattern removes with a `cl:` predicate fail with a `SailException`. Clearing the log graph (also by `CLEAR/DROP NAMED`) is skipped silently. Removes over all graphs skip log entries.

The queries WissKI runs are in `rdf4j/changelog-sail/src/test/java/de/fau/cdi/opengdb/changelog/Fixture.java` (`STATE_QUERY`, `RECORDS_QUERY`, `CATCH_UP_QUERY`).

### Caveats

- **The log graph is visible** in `contexts` listings, dumps and queries over all graphs. Log triples point to data IRIs, so queries for incoming links without `GRAPH` see them. WissKI 5 excludes the graph; other tools should too.
- **Over-approximation.** The log records write calls, not their net effect; a no-op write still makes a record.
- **Size.** At most R × (`maxNodes` + 3 × `maxTerms`) statements, 1 million with the defaults, plus one entry per distinct predicate, class and graph. A WissKI edit touches few IRIs.
- **Slot count.** A consumer more than R records behind catches up through the summary index, at bundle level instead of entity level. A WissKI save writes about two transactions per changed field value; raise R for busy repositories.
- **Inferencers** below the Sail aren't seen. Inferred changes follow from the recorded explicit ones.
- **Old snapshots.** A `SNAPSHOT` or `SERIALIZABLE` transaction that doesn't see the newest record gets its record written right after its commit, in a transaction of its own.
- **Storage.** WissKI's own edits keep growing `values.dat` on NativeStore. The remedy is a dump and reload, or the LMDB store.

### Building and testing the Sail

```bash
docker run --rm -v "$PWD/rdf4j/changelog-sail":/src -w /src maven:3.9-eclipse-temurin-25 mvn -B verify
# Benchmarks, not part of verify:
docker run --rm -v "$PWD/rdf4j/changelog-sail":/src -w /src maven:3.9-eclipse-temurin-25 \
  mvn -B -Pperf test -Dtest=PerformanceTest -Dperf.large=100000000
```

## Future development:
- Ideally we want to make this a drop in replacement for the GraphBB server that also works with the standalone [GraphDB Workbench](https://github.com/Ontotext-AD/graphdb-workbench)
