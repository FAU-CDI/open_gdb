# Change log: design and performance

This page explains what the change log Sail does, why it is built the way it is, and what it costs. The contract, the configuration and the commands are in the [README](../README.md#change-log).

## Why

WissKI shows data from the triplestore and must cache what it reads: entities, pages, titles, views. Caches are only safe if WissKI learns what changed, also when the change bypasses WissKI (SPARQL updates from scripts, the RDF4J Workbench, other systems). RDF4J has no change feed. OpenGDB therefore records every committed change in a reserved graph of the same repository, and WissKI 5 reads it with plain SPARQL through authproxy.

## What was built

| Part | Where | What it does |
|---|---|---|
| Change log Sail | `rdf4j/changelog-sail/` | A stacked Sail (`opengdb:ChangeLogSail`) over any store. It records the arguments of the write calls and writes one record per transaction into the log graph, in the same transaction. |
| Image | `rdf4j/Dockerfile` | The `eclipse/rdf4j-workbench` image with the Sail's jar added to `rdf4j-server.war`. Without a repository that uses the Sail, it behaves like the stock image. |
| CI | `.github/workflows/rdf4j.yml` | `mvn verify`, then build and push `ghcr.io/fau-cdi/open_gdb_rdf4j`. |
| Opt-in | `RDF4J_CHANGELOG` (authproxy) | `1` creates new repositories with the Sail. Default `0`. |
| Commands | `enable_changelog`, `disable_changelog` | Switch existing repositories to the Sail and back. |
| `create_remote()` | `authproxy/rdf4j/models.py` | Accepts RDF4J 6's 201, keeps the Django row on 409, and reports every other error. |

## Design decisions

### A plain wrapper instead of a listener

RDF4J offers `SailConnectionListener`, but with a listener attached `SailSourceConnection` runs an extra `hasStatement` for every added statement, gives up `deprecateByQuery` and enumerates every statement a pattern remove or `clear()` matches. The Sail instead wraps the connection and records the arguments of `addStatement`, `removeStatement(s)` and `clear`. Every write path ends in those calls: SPARQL updates, uploads, deletes and transactions. The store below keeps all its fast paths.

The price is over-approximation: a write that changes nothing (adding an existing statement) still makes a record. WissKI then refreshes a little more than needed, never less.

### Three levels of detail

A record lists IRIs, not statements, at the level of detail the transaction allows:

| Scope | When | What WissKI refreshes |
|---|---|---|
| `cl:Nodes` | Up to 200 distinct IRIs | The entities owning the IRIs. |
| `cl:Summary` | More IRIs, blank-node subjects, removes by predicate | Bundles whose paths use the predicates or classes. |
| `cl:Everything` | Cleared graphs, more than 100 predicates, classes or graphs | Everything shown from the listed graphs. |

A normal WissKI edit stays at entity level. A curation update over millions of triples still names its predicates, so WissKI refreshes bundles instead of everything.

### A ring of slots and a summary index

Records live in a fixed ring of 2000 slots; record N replaces record N − 2000 in slot `N mod 2000`. A summary index has one entry per predicate, class and graph with the newest record that touched it, so a consumer that fell behind the ring still learns what changed, at bundle level.

The reason is storage. NativeStore never frees values: every literal that was ever written stays in `values.dat`. A first draft stored a JSON literal per record, which would have grown `values.dat` by gigabytes per year. Records now reference only IRIs that already exist; slot IRIs and index literals are created once per slot, and a new cycle literal appears once every 2000 records. A test toggles one statement 200 times and checks that `values.dat` grows by less than 512 bytes.

### Revisions without a counter triple

Revisions rise by exactly one per record, in commit order, without gaps. A Sail-wide commit lock is taken before the transaction is prepared and held until it has committed, so the revision is assigned in commit order; a failed commit doesn't use its number. There is no counter triple: under snapshot isolation a triple that every commit rewrites would end up with two values. Consumers compute the newest and oldest revision from the slots.

The lock is a semaphore rather than a `ReentrantLock`, so it is released even if a transaction ends on another thread than the one that prepared it. It is always taken before RDF4J's own branch lock (held from `prepare` to the end of the commit), so the two can't deadlock.

### Old snapshots

A `SNAPSHOT` or `SERIALIZABLE` transaction reads from its start. If it doesn't see the newest record, writing its record from that view would leave two cycles in a slot or two values in an index entry. The Sail checks with one exact lookup whether the transaction sees the previous record. If not, it writes the record right after the commit in a transaction of its own, still under the lock. If even that fails, the next record says "everything", so no change goes unnoticed.

### Protection of the log

Clients can't add to the log graph or remove from it by naming it; pattern removes with a `cl:` predicate are rejected. Clearing the log graph is skipped silently, because `CLEAR/DROP NAMED` clear every graph one by one and must not fail. `DROP ALL`/`CLEAR ALL` keep the log and write a `cl:Everything` record. (`DROP ALL` calls `clear()` without contexts; only `NAMED` goes graph by graph.)

### Opt-in, because WissKI 4 is not compatible

Log triples point to data IRIs (`cl:slot-k cl:node <entity>`). WissKI 4 runs generic `GRAPH ?g` updates, for example in `deleteEntity()` (`DELETE { GRAPH ?g { ?s ?p <uri> } } WHERE { GRAPH ?g { ?s ?p <uri> } }`), and they match log entries. On a repository with the log, WissKI 4 fails to delete recently edited entities and to merge, its reference dialog refuses deletions, and its N-Quads export can't be imported again. WissKI 5 excludes the log graph. The log is therefore off by default: `RDF4J_CHANGELOG=1` for new repositories, `enable_changelog` for existing ones, only after the update to WissKI 5.

`enable_changelog` keeps each repository's triple indexes (authproxy's older defaults differ, and changed indexes would make NativeStore rebuild them on start), checks the configuration RDF4J has stored, and removes a stale log graph, so the Sail starts a new epoch. `disable_changelog` goes back; `--purge-log` removes the graph after the restart.

## Performance

### The bulk-load problem and its fix

The first version made loading 1 million statements in one transaction 27–31 % slower. A profile showed almost all of it in `prepare()` (1.5 s): reading the log inside the large transaction. RDF4J keeps a transaction's pending statements in a `DynamicModel` that is a plain hash set until the first pattern lookup, which builds full indexes over all pending statements. The record's reads and pattern removes triggered that.

The Sail now reads the log through a separate connection (under the commit lock that is the newest state), removes only exact statements, and does all removals before all additions. The old-snapshot check uses one exact lookup. `prepare()` went from 1.5 s to 1–3 ms.

### Measurements

NativeStore (`spoc,posc,cosp`), JDK 25, medians of 5 runs on a 16-core workstation, in-process through the repository API:

| Workload | Without Sail | With Sail | Difference |
|---|---|---|---|
| 1 million statements in one transaction | 5,448 ms | 5,665 ms | +4.0 % |
| 100 SPARQL `INSERT DATA` of 1,000 statements | 1,809 ms | 1,894 ms | +4.7 % |

The consumer's queries read at most the 2000 slots and don't depend on the repository size (ring full, median of 25):

| Repository | State query | Records query (100 records) |
|---|---|---|
| 1 million statements | 10.0 ms | 21.8 ms |
| 10 million statements | 9.1 ms | 20.9 ms |
<!-- 100M -->

Over HTTP, a single-triple SPARQL update took 11–12 ms directly against RDF4J with and without the Sail. Through authproxy it took about 150 ms either way; that is authproxy's per-request password hashing with HTTP Basic, not the log.

What the log brings for WissKI: without it, WissKI can't cache data safely, or has to throw away all caches on every direct update. With it, a normal edit invalidates single entities, and a mass update invalidates the affected bundles.

### Reproducing

```bash
cd rdf4j/changelog-sail
docker run --rm -v "$PWD":/src -w /src maven:3.9-eclipse-temurin-25 mvn -B verify
docker run --rm -v "$PWD":/src -v perf:/data -w /src maven:3.9-eclipse-temurin-25 \
  mvn -B -Pperf test -Dtest=PerformanceTest -Dperf.dir=/data -Dperf.large=100000000
```

## Tests

- 67 JUnit tests over NativeStore and LMDB: recording and scopes, the ring and catch-up, no `values.dat` growth, protection, concurrent commits, old snapshots, failed commits, restarts, a changed slot count, wrapping an existing store, and the configuration through `LocalRepositoryManager`.
- 18 Django tests with a mocked RDF4J: template choice, `create_remote()` status codes, `enable_changelog`/`disable_changelog` incl. dry run and kept indexes.
- End to end with the image and authproxy: the RDF4J answers (204 new, 409 existing, 400 for an unknown Sail type), enabling on a repository with authproxy's oldest template without data loss, an edit (`cl:Nodes`), a curation update (`cl:Summary`), a rejected write to the log, `DROP ALL` (`cl:Everything`, log kept), catch-up after 2,010 updates, and the way back with `--purge-log`.
