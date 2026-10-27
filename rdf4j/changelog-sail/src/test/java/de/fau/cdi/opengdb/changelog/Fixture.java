package de.fau.cdi.opengdb.changelog;

import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.LOG_GRAPH;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Consumer;
import java.util.function.Function;
import java.util.function.UnaryOperator;

import org.eclipse.rdf4j.model.IRI;
import org.eclipse.rdf4j.model.Model;
import org.eclipse.rdf4j.model.Value;
import org.eclipse.rdf4j.model.impl.LinkedHashModel;
import org.eclipse.rdf4j.model.util.Values;
import org.eclipse.rdf4j.query.BindingSet;
import org.eclipse.rdf4j.query.TupleQueryResult;
import org.eclipse.rdf4j.repository.RepositoryConnection;
import org.eclipse.rdf4j.repository.sail.SailRepository;
import org.eclipse.rdf4j.sail.Sail;
import org.eclipse.rdf4j.sail.lmdb.LmdbStore;
import org.eclipse.rdf4j.sail.lmdb.config.LmdbStoreConfig;
import org.eclipse.rdf4j.sail.nativerdf.NativeStore;

/** A repository with the change log over a store in a temporary directory. */
final class Fixture implements AutoCloseable {

	static final String EX = "http://example.org/";

	enum StoreType {
		NATIVE, LMDB;

		Sail create(Path dir) {
			return switch (this) {
			case NATIVE -> new NativeStore(dir.toFile(), "spoc,posc,cosp");
			case LMDB -> new LmdbStore(dir.toFile(), new LmdbStoreConfig("spoc,posc,cosp"));
			};
		}
	}

	/** A record as the consumer's records query returns it. */
	record Rec(long revision, IRI scope, Set<Value> nodes, Set<Value> predicates, Set<Value> classes,
			Set<Value> graphs) {
	}

	/** The result of the consumer's state query. */
	record State(String epoch, long slots, Long everything, Long newest, Long oldest) {
	}

	static final String STATE_QUERY = """
			PREFIX cl: <tag:fau-cdi.github.io,2026:opengdb/changelog#>
			SELECT ?epoch ?slots ?everything (MAX(?rev) AS ?newest) (MIN(?rev) AS ?oldest) WHERE {
			  GRAPH <tag:fau-cdi.github.io,2026:opengdb/changelog> {
			    cl:state cl:epoch ?epoch ; cl:slots ?slots .
			    OPTIONAL {
			      cl:state cl:lastEverythingSlot ?eslot ; cl:lastEverythingCycle ?ecycle .
			      ?eslot cl:index ?eindex .
			    }
			    OPTIONAL { ?slot cl:index ?index ; cl:cycle ?cycle . }
			  }
			  BIND (?cycle * ?slots + ?index AS ?rev)
			  BIND (?ecycle * ?slots + ?eindex AS ?everything)
			} GROUP BY ?epoch ?slots ?everything
			""";

	static final String RECORDS_QUERY = """
			PREFIX cl: <tag:fau-cdi.github.io,2026:opengdb/changelog#>
			SELECT ?rev ?scope ?kind ?value WHERE {
			  GRAPH <tag:fau-cdi.github.io,2026:opengdb/changelog> {
			    cl:state cl:slots ?slots .
			    ?slot cl:index ?index ; cl:cycle ?cycle ; cl:scope ?scope .
			    OPTIONAL {
			      ?slot ?kind ?value .
			      FILTER (?kind IN (cl:node, cl:predicate, cl:class, cl:graph))
			    }
			  }
			  BIND (?cycle * ?slots + ?index AS ?rev)
			  FILTER (?rev > %d)
			} ORDER BY ?rev
			""";

	static final String CATCH_UP_QUERY = """
			PREFIX cl: <tag:fau-cdi.github.io,2026:opengdb/changelog#>
			SELECT ?kind ?value WHERE {
			  GRAPH <tag:fau-cdi.github.io,2026:opengdb/changelog> {
			    cl:state cl:slots ?slots .
			    ?entry cl:lastSlot ?slot ; cl:lastCycle ?cycle ; ?kind ?value .
			    ?slot cl:index ?index .
			    FILTER (?kind IN (cl:predicate, cl:class, cl:graph))
			  }
			  BIND (?cycle * ?slots + ?index AS ?rev)
			  FILTER (?rev > %d)
			}
			""";

	final Path dir;
	final StoreType type;
	long slots = ChangeLogSail.DEFAULT_SLOTS;
	int maxNodes = ChangeLogSail.DEFAULT_MAX_NODES;
	int maxTerms = ChangeLogSail.DEFAULT_MAX_TERMS;
	UnaryOperator<Sail> between = UnaryOperator.identity();
	ChangeLogSail sail;
	SailRepository repo;

	Fixture(StoreType type, Path dir) {
		this.type = type;
		this.dir = dir;
	}

	static IRI ex(String localName) {
		return Values.iri(EX, localName);
	}

	Fixture open() {
		sail = new ChangeLogSail(between.apply(type.create(dir.resolve("store"))));
		sail.setSlots(slots);
		sail.setMaxNodes(maxNodes);
		sail.setMaxTerms(maxTerms);
		repo = new SailRepository(sail);
		repo.init();
		return this;
	}

	Fixture reopen() {
		repo.shutDown();
		return open();
	}

	@Override
	public void close() {
		if (repo != null) {
			repo.shutDown();
		}
	}

	void update(String sparql) {
		try (RepositoryConnection con = repo.getConnection()) {
			con.prepareUpdate(sparql).execute();
		}
	}

	void tx(Consumer<RepositoryConnection> work) {
		try (RepositoryConnection con = repo.getConnection()) {
			con.begin();
			work.accept(con);
			con.commit();
		}
	}

	<T> T read(Function<RepositoryConnection, T> work) {
		try (RepositoryConnection con = repo.getConnection()) {
			return work.apply(con);
		}
	}

	List<BindingSet> select(String sparql) {
		return read(con -> {
			List<BindingSet> rows = new ArrayList<>();
			try (TupleQueryResult result = con.prepareTupleQuery(sparql).evaluate()) {
				result.forEach(rows::add);
			}
			return rows;
		});
	}

	State state() {
		List<BindingSet> rows = select(STATE_QUERY);
		if (rows.isEmpty()) {
			return null;
		}
		if (rows.size() > 1) {
			throw new AssertionError("State query returned " + rows.size() + " rows: " + rows);
		}
		BindingSet row = rows.get(0);
		return new State(row.getValue("epoch").stringValue(), longValue(row, "slots"),
				row.hasBinding("everything") ? longValue(row, "everything") : null,
				row.hasBinding("newest") ? longValue(row, "newest") : null,
				row.hasBinding("oldest") ? longValue(row, "oldest") : null);
	}

	List<Rec> records(long after) {
		Map<Long, Rec> records = new LinkedHashMap<>();
		for (BindingSet row : select(RECORDS_QUERY.formatted(after))) {
			long revision = longValue(row, "rev");
			Rec rec = records.computeIfAbsent(revision, r -> new Rec(r, (IRI) row.getValue("scope"),
					new LinkedHashSet<>(), new LinkedHashSet<>(), new LinkedHashSet<>(), new LinkedHashSet<>()));
			if (!row.hasBinding("kind")) {
				continue;
			}
			Value kind = row.getValue("kind");
			Value value = row.getValue("value");
			if (kind.equals(ChangeLogVocabulary.NODE)) {
				rec.nodes().add(value);
			} else if (kind.equals(ChangeLogVocabulary.PREDICATE)) {
				rec.predicates().add(value);
			} else if (kind.equals(ChangeLogVocabulary.CLASS)) {
				rec.classes().add(value);
			} else if (kind.equals(ChangeLogVocabulary.GRAPH)) {
				rec.graphs().add(value);
			}
		}
		return new ArrayList<>(records.values());
	}

	List<Rec> records() {
		return records(0);
	}

	Rec last() {
		List<Rec> records = records();
		return records.get(records.size() - 1);
	}

	/** (kind, value) pairs of the catch-up query. */
	Set<List<Value>> catchUp(long after) {
		Set<List<Value>> entries = new LinkedHashSet<>();
		for (BindingSet row : select(CATCH_UP_QUERY.formatted(after))) {
			entries.add(List.of(row.getValue("kind"), row.getValue("value")));
		}
		return entries;
	}

	Model logGraph() {
		return read(con -> {
			Model model = new LinkedHashModel();
			con.getStatements(null, null, null, false, LOG_GRAPH).forEach(model::add);
			return model;
		});
	}

	/** Statements outside the log graph. */
	long dataSize() {
		return read(con -> con.size() - con.size(LOG_GRAPH));
	}

	private static long longValue(BindingSet row, String name) {
		return ((org.eclipse.rdf4j.model.Literal) row.getValue(name)).longValue();
	}
}
