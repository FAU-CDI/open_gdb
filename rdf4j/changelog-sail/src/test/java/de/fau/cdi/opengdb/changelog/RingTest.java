package de.fau.cdi.opengdb.changelog;

import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.CYCLE;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.GRAPH;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.INDEX;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.PREDICATE;
import static de.fau.cdi.opengdb.changelog.Fixture.ex;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.LongStream;

import org.eclipse.rdf4j.model.Model;
import org.eclipse.rdf4j.model.Resource;
import org.eclipse.rdf4j.model.Value;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedClass;
import org.junit.jupiter.params.provider.EnumSource;

import de.fau.cdi.opengdb.changelog.Fixture.Rec;

@ParameterizedClass
@EnumSource(Fixture.StoreType.class)
class RingTest extends StoreTest {

	RingTest(Fixture.StoreType store) {
		super(store);
	}

	@Test
	void ringHoldsTheLastRecords() {
		Fixture f = configure();
		f.slots = 5;
		f.open();
		for (int i = 1; i <= 10; i++) {
			int n = i;
			f.tx(con -> con.add(ex("s" + n), ex("p"), ex("o")));
		}

		List<Rec> records = f.records();
		assertEquals(List.of(6L, 7L, 8L, 9L, 10L), records.stream().map(Rec::revision).toList());
		assertEquals(Set.of(ex("s10"), ex("o")), records.get(4).nodes());
		assertOneCyclePerSlot(f.logGraph(), 5);
		Fixture.State state = f.state();
		assertEquals(Long.valueOf(10), state.newest());
		assertEquals(Long.valueOf(6), state.oldest());
	}

	@Test
	void catchUpReturnsWhatChangedSinceARevision() {
		Fixture f = configure();
		f.slots = 3;
		f.open();
		f.tx(con -> con.add(ex("s"), ex("early"), ex("o"), ex("g1")));
		f.tx(con -> con.add(ex("s"), ex("p"), ex("o"), ex("g1")));
		// Revision 3 is the cursor; everything after it is newer.
		f.tx(con -> con.add(ex("s"), ex("p"), ex("o"), ex("g1")));
		f.tx(con -> con.add(ex("s"), ex("late"), ex("C2"), ex("g2")));
		f.tx(con -> con.add(ex("t"), org.eclipse.rdf4j.model.vocabulary.RDF.TYPE, ex("C"), ex("g2")));
		f.tx(con -> con.add(ex("s"), ex("p"), ex("o2"), ex("g2")));
		f.tx(con -> con.add(ex("s"), ex("p"), ex("o3"), ex("g2")));

		assertEquals(Long.valueOf(5), f.state().oldest(), "the cursor is older than the ring");
		Set<List<Value>> changed = f.catchUp(3);
		assertEquals(Set.of(List.of(PREDICATE, ex("late")), List.of(PREDICATE, ex("p")),
				List.of(PREDICATE, org.eclipse.rdf4j.model.vocabulary.RDF.TYPE),
				List.of(ChangeLogVocabulary.CLASS, ex("C")), List.of(GRAPH, ex("g2"))), changed);
		assertOneValuePerEntry(f.logGraph());
	}

	@Test
	void repeatedEditsDoNotGrowTheValueStore() throws IOException {
		assumeTrue(store == Fixture.StoreType.NATIVE, "values.dat is NativeStore's value file");
		Fixture f = configure();
		f.slots = 20;
		f.open();
		f.tx(con -> con.add(ex("s"), ex("p"), ex("o"), ex("g")));
		// One round creates every slot IRI and index literal.
		toggle(f, 20);
		Path values = dir.resolve("store").resolve("values.dat");
		long before = Files.size(values);

		toggle(f, 10 * 20);

		long growth = Files.size(values) - before;
		// At most a few new cycle literals.
		assertTrue(growth < 512, "values.dat grew by " + growth + " bytes");
		assertEquals(Long.valueOf(1 + 20 + 200), f.state().newest());
	}

	private static void toggle(Fixture f, int times) {
		for (int i = 0; i < times; i++) {
			boolean remove = i % 2 == 0;
			f.tx(con -> {
				if (remove) {
					con.remove(ex("s"), ex("p"), ex("o"), ex("g"));
				} else {
					con.add(ex("s"), ex("p"), ex("o"), ex("g"));
				}
			});
		}
	}

	static void assertOneCyclePerSlot(Model log, long slots) {
		Set<Resource> slotIris = log.filter(null, INDEX, null).subjects();
		assertTrue(slotIris.size() <= slots);
		for (Resource slot : slotIris) {
			assertEquals(1, log.filter(slot, CYCLE, null).size(), "cycles of " + slot);
			assertEquals(1, log.filter(slot, INDEX, null).size(), "indexes of " + slot);
		}
		assertEquals(LongStream.range(0, slotIris.size()).boxed().collect(Collectors.toSet()),
				log.filter(null, INDEX, null).objects().stream()
						.map(v -> ((org.eclipse.rdf4j.model.Literal) v).longValue()).collect(Collectors.toSet()));
	}

	static void assertOneValuePerEntry(Model log) {
		for (Resource entry : log.filter(null, ChangeLogVocabulary.LAST_SLOT, null).subjects()) {
			assertEquals(1, log.filter(entry, ChangeLogVocabulary.LAST_SLOT, null).size(), "lastSlot of " + entry);
			assertEquals(1, log.filter(entry, ChangeLogVocabulary.LAST_CYCLE, null).size(), "lastCycle of " + entry);
		}
	}
}
