package de.fau.cdi.opengdb.changelog;

import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.DEFAULT_GRAPH;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.EVERYTHING;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.LOG_GRAPH;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.NODES;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.SUMMARY;
import static de.fau.cdi.opengdb.changelog.Fixture.ex;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Set;

import org.eclipse.rdf4j.model.Resource;
import org.eclipse.rdf4j.model.Statement;
import org.eclipse.rdf4j.model.util.Values;
import org.eclipse.rdf4j.model.vocabulary.RDF;
import org.eclipse.rdf4j.repository.RepositoryConnection;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedClass;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.junit.jupiter.params.provider.ValueSource;

import de.fau.cdi.opengdb.changelog.Fixture.Rec;

@ParameterizedClass
@EnumSource(Fixture.StoreType.class)
class RecordingTest extends StoreTest {

	RecordingTest(Fixture.StoreType store) {
		super(store);
	}

	@Test
	void insertDataMakesNodesRecord() {
		Fixture f = fixture();
		f.update("""
				PREFIX ex: <http://example.org/>
				INSERT DATA { GRAPH ex:g { ex:s a ex:C ; ex:label "secret value" ; ex:knows ex:o } }
				""");

		List<Rec> records = f.records();
		assertEquals(1, records.size());
		Rec rec = records.get(0);
		assertEquals(1, rec.revision());
		assertEquals(NODES, rec.scope());
		assertEquals(Set.of(ex("s"), ex("C"), ex("o")), rec.nodes());
		assertEquals(Set.of(RDF.TYPE, ex("label"), ex("knows")), rec.predicates());
		assertEquals(Set.of(ex("C")), rec.classes());
		assertEquals(Set.of(ex("g")), rec.graphs());
		for (Statement statement : f.logGraph()) {
			assertFalse(statement.getObject().stringValue().contains("secret"), "literal value in the log");
		}
	}

	@Test
	void deleteInsertWhereListsSubject() {
		Fixture f = fixture();
		f.update("INSERT DATA { GRAPH <http://example.org/g> { <http://example.org/d> <http://example.org/date> "
				+ "\"1900\" } }");
		f.update("""
				PREFIX ex: <http://example.org/>
				DELETE { GRAPH ex:g { ex:d ex:date ?old } } INSERT { GRAPH ex:g { ex:d ex:date "1901" } }
				WHERE { GRAPH ex:g { ex:d ex:date ?old } }
				""");

		Rec rec = f.last();
		assertEquals(2, rec.revision());
		assertEquals(NODES, rec.scope());
		assertEquals(Set.of(ex("d")), rec.nodes());
		assertEquals(Set.of(ex("date")), rec.predicates());
	}

	@Test
	void moreThanMaxNodesMakesSummaryWithPredicatesAndClasses() {
		Fixture f = configure();
		f.maxNodes = 10;
		f.open();
		f.tx(con -> {
			for (int i = 0; i < 20; i++) {
				con.add(ex("item" + i), RDF.TYPE, ex("Item"), ex("g"));
				con.add(ex("item" + i), ex("name"), Values.literal("n" + i), ex("g"));
			}
		});

		Rec rec = f.last();
		assertEquals(SUMMARY, rec.scope());
		assertTrue(rec.nodes().isEmpty());
		assertEquals(Set.of(RDF.TYPE, ex("name")), rec.predicates());
		assertEquals(Set.of(ex("Item")), rec.classes());
		assertEquals(Set.of(ex("g")), rec.graphs());
	}

	@Test
	void blankNodeSubjectMakesSummary() {
		Fixture f = fixture();
		f.update("INSERT DATA { _:b <http://example.org/p> <http://example.org/o> }");

		Rec rec = f.last();
		assertEquals(SUMMARY, rec.scope());
		assertEquals(Set.of(ex("p")), rec.predicates());
		assertEquals(Set.of(DEFAULT_GRAPH), rec.graphs());
	}

	@Test
	void removeByPredicateMakesSummary() {
		Fixture f = fixture();
		f.tx(con -> con.add(ex("s"), ex("p"), ex("o"), ex("g")));
		// DELETE /statements?pred=P
		f.tx(con -> con.remove((Resource) null, ex("p"), null));

		Rec rec = f.last();
		assertEquals(SUMMARY, rec.scope());
		assertEquals(Set.of(ex("p")), rec.predicates());
		assertEquals(0, f.dataSize());
	}

	@Test
	void removeTypeByPatternMakesEverything() {
		Fixture f = fixture();
		f.tx(con -> con.add(ex("s"), RDF.TYPE, ex("C"), ex("g")));
		f.tx(con -> con.remove((Resource) null, RDF.TYPE, null, ex("g")));

		Rec rec = f.last();
		assertEquals(EVERYTHING, rec.scope());
		assertEquals(Set.of(ex("g")), rec.graphs());
		assertEquals(rec.revision(), f.state().everything());
	}

	@Test
	void clearGraphMakesEverythingWithGraph() {
		Fixture f = fixture();
		f.tx(con -> con.add(ex("s"), ex("p"), ex("o"), ex("g")));
		f.update("CLEAR GRAPH <http://example.org/g>");

		Rec rec = f.last();
		assertEquals(EVERYTHING, rec.scope());
		assertEquals(Set.of(ex("g")), rec.graphs());
		assertTrue(rec.predicates().isEmpty());
	}

	@ParameterizedTest
	@ValueSource(strings = { "DROP ALL", "CLEAR ALL", "DROP NAMED", "CLEAR NAMED", "DROP DEFAULT" })
	void clearingKeepsLogAndWritesEverything(String update) {
		Fixture f = fixture();
		f.tx(con -> {
			con.add(ex("s"), ex("p"), ex("o"), ex("g"));
			con.add(ex("s"), ex("p"), ex("o"));
		});
		String epoch = f.state().epoch();

		f.update(update);

		assertEquals(epoch, f.state().epoch());
		List<Rec> records = f.records();
		assertEquals(2, records.size(), "the earlier record is kept");
		Rec rec = records.get(1);
		assertEquals(EVERYTHING, rec.scope());
		assertEquals(Long.valueOf(2), f.state().everything());
		long expectedData = switch (update) {
		case "DROP NAMED", "CLEAR NAMED", "DROP DEFAULT" -> 1;
		default -> 0;
		};
		assertEquals(expectedData, f.dataSize());
		if (update.endsWith("ALL")) {
			assertTrue(rec.graphs().isEmpty(), "all graphs");
		}
	}

	@Test
	void tooManyPredicatesMakesEverythingKeepingGraphs() {
		Fixture f = configure();
		f.maxTerms = 5;
		f.open();
		f.tx(con -> {
			for (int i = 0; i < 10; i++) {
				con.add(ex("s"), ex("p" + i), ex("o"), ex("g"));
			}
		});

		Rec rec = f.last();
		assertEquals(EVERYTHING, rec.scope());
		assertTrue(rec.predicates().isEmpty());
		assertEquals(Set.of(ex("g")), rec.graphs());
	}

	@Test
	void tooManyGraphsMakesEverythingForAllGraphs() {
		Fixture f = configure();
		f.maxTerms = 5;
		f.open();
		f.tx(con -> {
			for (int i = 0; i < 10; i++) {
				con.add(ex("s"), ex("p"), ex("o"), ex("g" + i));
			}
		});

		Rec rec = f.last();
		assertEquals(EVERYTHING, rec.scope());
		assertTrue(rec.graphs().isEmpty());
	}

	@Test
	void removeWithBoundObjectRemovesEachMatchAndKeepsLog() {
		Fixture f = fixture();
		f.tx(con -> {
			con.add(ex("a"), ex("p"), ex("target"), ex("g1"));
			con.add(ex("b"), ex("q"), ex("target"), ex("g2"));
		});
		long logSize = f.logGraph().size();
		// DELETE /statements?obj=<target>; the first record lists <target> as a node.
		f.tx(con -> con.remove((Resource) null, null, ex("target")));

		assertEquals(0, f.dataSize());
		Rec rec = f.last();
		assertEquals(NODES, rec.scope());
		assertEquals(Set.of(ex("a"), ex("b"), ex("target")), rec.nodes());
		assertEquals(Set.of(ex("g1"), ex("g2")), rec.graphs());
		assertTrue(f.logGraph().size() >= logSize, "the log keeps its entries");
		assertTrue(f.records().get(0).nodes().contains(ex("target")));
	}

	@Test
	void rollbackRecordsNothingAndKeepsTheNumber() {
		Fixture f = fixture();
		try (RepositoryConnection con = f.repo.getConnection()) {
			con.begin();
			con.add(ex("s"), ex("p"), ex("o"));
			con.prepare();
			con.rollback();
		}
		assertTrue(f.records().isEmpty());
		f.tx(con -> con.add(ex("s"), ex("p"), ex("o")));
		assertEquals(1, f.last().revision());
	}

	@Test
	void readOnlyTransactionRecordsNothing() {
		Fixture f = fixture();
		f.tx(con -> con.size());
		assertTrue(f.records().isEmpty());
	}

	@Test
	void stateQueryReportsTheRing() {
		Fixture f = fixture();
		Fixture.State empty = f.state();
		assertNotNull(empty);
		assertEquals(ChangeLogSail.DEFAULT_SLOTS, empty.slots());
		assertEquals(null, empty.newest());

		f.tx(con -> con.add(ex("s"), ex("p"), ex("o")));
		f.tx(con -> con.add(ex("s"), ex("p"), ex("o2")));
		Fixture.State state = f.state();
		assertEquals(empty.epoch(), state.epoch());
		assertEquals(Long.valueOf(2), state.newest());
		assertEquals(Long.valueOf(1), state.oldest());
		assertEquals(null, state.everything());
		assertTrue(f.<Boolean>read(con -> con.hasStatement(null, null, null, false, LOG_GRAPH)));
	}
}
