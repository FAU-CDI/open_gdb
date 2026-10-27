package de.fau.cdi.opengdb.changelog;

import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.LOG_GRAPH;
import static de.fau.cdi.opengdb.changelog.Fixture.ex;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

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
		assertThrows(UpdateExecutionException.class, () -> f.update("""
				DELETE { GRAPH ?g { ?s ?p <http://example.org/o> } }
				WHERE { GRAPH ?g { ?s ?p <http://example.org/o> } }
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

	private Fixture withOneRecord() {
		Fixture f = fixture();
		f.tx(con -> con.add(ex("s"), ex("p"), ex("o"), ex("g")));
		return f;
	}
}
