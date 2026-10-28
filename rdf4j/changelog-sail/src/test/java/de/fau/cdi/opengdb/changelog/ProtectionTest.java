package de.fau.cdi.opengdb.changelog;

import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.LOG_GRAPH;
import static de.fau.cdi.opengdb.changelog.Fixture.ex;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;

import org.eclipse.rdf4j.model.IRI;
import org.eclipse.rdf4j.model.Literal;
import org.eclipse.rdf4j.model.Model;
import org.eclipse.rdf4j.model.Resource;
import org.eclipse.rdf4j.repository.RepositoryException;
import org.eclipse.rdf4j.query.UpdateExecutionException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedClass;
import org.junit.jupiter.params.provider.EnumSource;

@ParameterizedClass
@EnumSource(Fixture.StoreType.class)
class ProtectionTest extends StoreTest {

	ProtectionTest(Fixture.StoreType store) {
		super(store);
	}

	@Test
	void insertIntoTheLogGraphIsRejected() {
		Fixture f = withOneRecord();
		Model before = f.logGraph();

		assertThrows(UpdateExecutionException.class, () -> f.update(
				"INSERT DATA { GRAPH <tag:fau-cdi.github.io,2026:opengdb/changelog> { <http://example.org/x> "
						+ "<http://example.org/y> <http://example.org/z> } }"));
		assertThrows(RepositoryException.class,
				() -> f.tx(con -> con.add(ex("x"), ex("y"), ex("z"), LOG_GRAPH)));

		assertEquals(before, f.logGraph());
	}

	@Test
	void removeFromTheLogGraphIsRejected() {
		Fixture f = withOneRecord();
		Model before = f.logGraph();

		assertThrows(UpdateExecutionException.class, () -> f.update("""
				PREFIX cl: <tag:fau-cdi.github.io,2026:opengdb/changelog#>
				DELETE DATA { GRAPH <tag:fau-cdi.github.io,2026:opengdb/changelog> { cl:slot-1 cl:index 1 } }
				"""));
		assertThrows(RepositoryException.class,
				() -> f.tx(con -> con.remove(ChangeLogVocabulary.slot(1), null, null, LOG_GRAPH)));

		assertEquals(before, f.logGraph());
	}

	@Test
	void clearingTheLogGraphIsSkipped() {
		Fixture f = withOneRecord();
		Model before = f.logGraph();

		f.update("CLEAR GRAPH <tag:fau-cdi.github.io,2026:opengdb/changelog>");
		f.update("DROP SILENT GRAPH <tag:fau-cdi.github.io,2026:opengdb/changelog>");
		f.tx(con -> con.clear(LOG_GRAPH));
		// DELETE /statements?context=<log> goes through clear().
		f.tx(con -> con.remove((Resource) null, null, null, LOG_GRAPH));

		assertEquals(before, f.logGraph());
		assertEquals(1, f.records().size(), "no-op clears make no record");
	}

	@Test
	void patternRemoveWithLogPredicateIsRejected() {
		Fixture f = withOneRecord();
		assertThrows(RepositoryException.class,
				() -> f.tx(con -> con.remove((Resource) null, ChangeLogVocabulary.NODE, null)));
	}

	@Test
	void deleteWhereOverAllGraphsKeepsLogEntries() {
		Fixture f = withOneRecord();
		long records = f.records().size();

		f.update("DELETE WHERE { ?s ?p <http://example.org/o> }");
		assertEquals(0, f.dataSize());
		f.tx(con -> con.add(ex("s2"), ex("p"), ex("o2")));
		f.update("DELETE WHERE { ?s ?p ?o }");

		assertEquals(0, f.dataSize());
		assertEquals(records + 3, f.records().size(), "earlier records are kept");
		assertTrue(f.state() != null);
	}

	@Test
	void queriesWithoutTheLogGraphDontSeeIt() {
		Fixture f = withOneRecord();
		IRI slot = ChangeLogVocabulary.slot(1);

		assertEquals(List.of(ex("g")), f.select("SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }").stream()
				.map(row -> row.getValue("g")).toList());
		assertEquals(0, f.select("SELECT * WHERE { ?s ?p <http://example.org/s> }").size(),
				"the record lists <s>, but the default graph doesn't show it");
		assertEquals(0, f.select("SELECT * WHERE { <" + slot + "> ?p ?o }").size());
		assertEquals(1, ((Literal) f.select("SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }").get(0).getValue("n"))
				.longValue());
		assertTrue(f.select("SELECT * WHERE { GRAPH <" + LOG_GRAPH + "> { <" + slot + "> ?p ?o } }").size() > 0,
				"naming the log graph reads it");
	}

	@Test
	void readsOverAllGraphsDontSeeIt() {
		Fixture f = withOneRecord();
		IRI slot = ChangeLogVocabulary.slot(1);

		f.read(con -> {
			assertEquals(List.of(ex("g")), con.getContextIDs().stream().toList());
			assertEquals(1, con.getStatements(null, null, null, false).stream().count());
			assertEquals(1, con.size());
			assertFalse(con.hasStatement(slot, null, null, false));
			assertTrue(con.hasStatement(slot, null, null, false, LOG_GRAPH));
			assertTrue(con.size(LOG_GRAPH) > 0);
			return null;
		});
	}

	@Test
	void updatesOverAllGraphsLeaveTheLogAlone() {
		Fixture f = withOneRecord();
		f.tx(con -> con.add(ex("t"), ex("p"), ex("s"), ex("g")));
		long records = f.records().size();

		// WissKI's deleteEntity() and merge: the WHERE part no longer binds ?g to the log graph.
		f.update("""
				INSERT { GRAPH ?g { ?x ?p <http://example.org/merged> } }
				WHERE { GRAPH ?g { ?x ?p <http://example.org/s> } }
				""");
		f.update("""
				DELETE { GRAPH ?g { ?x ?p <http://example.org/s> } }
				WHERE { GRAPH ?g { ?x ?p <http://example.org/s> } }
				""");

		assertEquals(2, f.dataSize());
		assertTrue(f.<Boolean>read(con -> con.hasStatement(ex("t"), ex("p"), ex("merged"), false, ex("g"))));
		assertEquals(records + 2, f.records().size());
		assertTrue(f.last().nodes().contains(ex("s")));
	}

	private Fixture withOneRecord() {
		Fixture f = fixture();
		f.tx(con -> con.add(ex("s"), ex("p"), ex("o"), ex("g")));
		return f;
	}
}
