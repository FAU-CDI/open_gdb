package de.fau.cdi.opengdb.changelog;

import static de.fau.cdi.opengdb.changelog.Fixture.ex;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.function.LongSupplier;

import org.eclipse.rdf4j.model.IRI;
import org.eclipse.rdf4j.model.util.Values;
import org.eclipse.rdf4j.model.vocabulary.RDF;
import org.eclipse.rdf4j.query.TupleQueryResult;
import org.eclipse.rdf4j.repository.RepositoryConnection;
import org.eclipse.rdf4j.repository.sail.SailRepository;
import org.eclipse.rdf4j.sail.Sail;
import org.eclipse.rdf4j.sail.nativerdf.NativeStore;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

/**
 * Numbers for the pull request. Not part of {@code mvn verify}:
 *
 * <pre>
 * mvn -Pperf test -Dtest=PerformanceTest -Dperf.dir=/data -Dperf.large=100000000
 * </pre>
 *
 * Prints medians and doesn't assert, because timings depend on the machine.
 */
@Tag("perf")
class PerformanceTest {

	private static final int RUNS = Integer.getInteger("perf.runs", 3);
	private static final long LOAD = Long.getLong("perf.load", 1_000_000);
	private static final long SMALL = Long.getLong("perf.small", 1_000_000);
	private static final long LARGE = Long.getLong("perf.large", 10_000_000);
	private static final Path DIR = Path.of(System.getProperty("perf.dir", "target/perf"));

	@Test
	void loadInOneTransaction() throws Exception {
		report("load " + LOAD + " statements in one transaction", wrapped -> {
			Path dir = fresh("load");
			SailRepository repo = repository(dir, wrapped);
			try (RepositoryConnection con = repo.getConnection()) {
				long start = System.nanoTime();
				con.begin();
				for (long i = 0; i < LOAD; i++) {
					addEntityStatement(con, i);
				}
				con.commit();
				return System.nanoTime() - start;
			} finally {
				repo.shutDown();
			}
		});
	}

	@Test
	void sparqlInsertDataRequests() throws Exception {
		report("100 INSERT DATA requests of 1000 statements", wrapped -> {
			Path dir = fresh("insert");
			SailRepository repo = repository(dir, wrapped);
			try (RepositoryConnection con = repo.getConnection()) {
				long start = System.nanoTime();
				for (int request = 0; request < 100; request++) {
					StringBuilder update = new StringBuilder("INSERT DATA { GRAPH <http://example.org/g> {\n");
					for (int i = 0; i < 1000; i++) {
						long n = request * 1000L + i;
						update.append("<http://example.org/e").append(n / 10).append("> <http://example.org/p")
								.append(n % 25).append("> \"value ").append(n).append("\" .\n");
					}
					update.append("} }");
					con.prepareUpdate(update.toString()).execute();
				}
				return System.nanoTime() - start;
			} finally {
				repo.shutDown();
			}
		});
	}

	@Test
	void logQueriesDontDependOnRepositorySize() throws Exception {
		for (long size : new long[] { SMALL, LARGE }) {
			Path dir = fresh("queries-" + size);
			SailRepository repo = repository(dir, true);
			try {
				fill(repo, size);
				List<Long> state = new ArrayList<>();
				List<Long> records = new ArrayList<>();
				long newest;
				try (RepositoryConnection con = repo.getConnection();
						TupleQueryResult result = con.prepareTupleQuery(Fixture.STATE_QUERY).evaluate()) {
					newest = ((org.eclipse.rdf4j.model.Literal) result.next().getValue("newest")).longValue();
				}
				for (int i = 0; i < 25; i++) {
					state.add(time(() -> count(repo, Fixture.STATE_QUERY)));
					records.add(time(() -> count(repo, Fixture.RECORDS_QUERY.formatted(newest - 100))));
				}
				System.out.printf("PERF %,d statements: state query %.2f ms, records query (100 records) %.2f ms%n",
						size, median(state) / 1e6, median(records) / 1e6);
			} finally {
				repo.shutDown();
			}
		}
	}

	/** Loads data in batches, then fills the ring with small WissKI-like edits. */
	private static void fill(SailRepository repo, long size) {
		try (RepositoryConnection con = repo.getConnection()) {
			long batch = 200_000;
			for (long offset = 0; offset < size; offset += batch) {
				con.begin();
				for (long i = offset; i < Math.min(size, offset + batch); i++) {
					addEntityStatement(con, i);
				}
				con.commit();
			}
			for (int edit = 0; edit < ChangeLogSail.DEFAULT_SLOTS; edit++) {
				con.begin();
				IRI entity = ex("e" + edit);
				con.remove(entity, ex("p1"), null, ex("g"));
				con.add(entity, ex("p1"), Values.literal("edited " + edit), ex("g"));
				con.commit();
			}
		}
	}

	private static void addEntityStatement(RepositoryConnection con, long i) {
		IRI entity = ex("e" + i / 10);
		long field = i % 10;
		if (field == 0) {
			con.add(entity, RDF.TYPE, ex("C" + (i / 10) % 20), ex("g"));
		} else if (field < 7) {
			con.add(entity, ex("p" + field), Values.literal("value " + i), ex("g"));
		} else {
			con.add(entity, ex("p" + field), ex("e" + (i * 7919) % Math.max(1, LARGE / 10)), ex("g"));
		}
	}

	private static long count(SailRepository repo, String query) {
		try (RepositoryConnection con = repo.getConnection();
				TupleQueryResult result = con.prepareTupleQuery(query).evaluate()) {
			long n = 0;
			while (result.hasNext()) {
				result.next();
				n++;
			}
			return n;
		}
	}

	private interface Run {
		long nanos(boolean wrapped) throws Exception;
	}

	private static void report(String what, Run run) throws Exception {
		// Warm-up.
		run.nanos(false);
		run.nanos(true);
		List<Long> plain = new ArrayList<>();
		List<Long> wrapped = new ArrayList<>();
		for (int i = 0; i < RUNS; i++) {
			plain.add(run.nanos(false));
			wrapped.add(run.nanos(true));
		}
		double p = median(plain) / 1e6;
		double w = median(wrapped) / 1e6;
		System.out.printf("PERF %s: plain %.0f ms, with change log %.0f ms (%+.1f %%)%n", what, p, w,
				(w - p) / p * 100);
	}

	private static SailRepository repository(Path dir, boolean wrapped) {
		Sail store = new NativeStore(dir.toFile(), "spoc,posc,cosp");
		SailRepository repo = new SailRepository(wrapped ? new ChangeLogSail(store) : store);
		repo.init();
		return repo;
	}

	private static Path fresh(String name) throws Exception {
		Path dir = DIR.resolve(name);
		if (Files.exists(dir)) {
			try (var paths = Files.walk(dir)) {
				for (Path path : paths.sorted(Collections.reverseOrder()).toList()) {
					Files.delete(path);
				}
			}
		}
		Files.createDirectories(dir);
		return dir;
	}

	private static long time(LongSupplier work) {
		long start = System.nanoTime();
		work.getAsLong();
		return System.nanoTime() - start;
	}

	private static double median(List<Long> values) {
		List<Long> sorted = new ArrayList<>(values);
		Collections.sort(sorted);
		return sorted.get(sorted.size() / 2);
	}
}
