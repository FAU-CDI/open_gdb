package de.fau.cdi.opengdb.changelog;

import static de.fau.cdi.opengdb.changelog.Fixture.ex;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.stream.LongStream;

import org.eclipse.rdf4j.common.transaction.IsolationLevels;
import org.eclipse.rdf4j.model.IRI;
import org.eclipse.rdf4j.model.Value;
import org.eclipse.rdf4j.repository.RepositoryConnection;
import org.eclipse.rdf4j.repository.RepositoryException;
import org.eclipse.rdf4j.repository.sail.SailRepository;
import org.eclipse.rdf4j.sail.Sail;
import org.eclipse.rdf4j.sail.SailConnection;
import org.eclipse.rdf4j.sail.SailException;
import org.eclipse.rdf4j.sail.helpers.SailConnectionWrapper;
import org.eclipse.rdf4j.sail.helpers.SailWrapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedClass;
import org.junit.jupiter.params.provider.EnumSource;

import de.fau.cdi.opengdb.changelog.Fixture.Rec;

@ParameterizedClass
@EnumSource(Fixture.StoreType.class)
class ConcurrencyTest extends StoreTest {

	ConcurrencyTest(Fixture.StoreType store) {
		super(store);
	}

	@Test
	void concurrentCommitsGetConsecutiveRevisionsInCommitOrder() throws Exception {
		Fixture f = fixture();
		int threads = 4;
		int perThread = 40;
		ExecutorService executor = Executors.newFixedThreadPool(threads);
		try {
			List<Future<?>> futures = new ArrayList<>();
			for (int t = 0; t < threads; t++) {
				int thread = t;
				futures.add(executor.submit(() -> {
					for (int i = 0; i < perThread; i++) {
						int n = i;
						f.tx(con -> con.add(ex("t" + thread + "-" + n), ex("p"), ex("o")));
					}
				}));
			}
			for (Future<?> future : futures) {
				future.get();
			}
		} finally {
			executor.shutdownNow();
		}

		List<Rec> records = f.records();
		assertEquals(LongStream.rangeClosed(1, threads * perThread).boxed().toList(),
				records.stream().map(Rec::revision).toList());
		// Each thread commits its transactions one after the other, so their revisions must rise.
		Map<String, Integer> lastIndex = new HashMap<>();
		for (Rec rec : records) {
			String node = rec.nodes().stream().map(Value::stringValue).filter(s -> s.contains("/t")).findFirst()
					.orElseThrow();
			String[] parts = node.substring(node.lastIndexOf('/') + 2).split("-");
			int index = Integer.parseInt(parts[1]);
			Integer previous = lastIndex.put(parts[0], index);
			assertTrue(previous == null || previous < index, "thread " + parts[0] + " out of order");
		}
	}

	@Test
	void staleSnapshotStillLeavesOneCyclePerSlot() {
		Fixture f = configure();
		f.slots = 5;
		f.open();
		f.tx(con -> con.add(ex("first"), ex("p"), ex("o")));

		try (RepositoryConnection old = f.repo.getConnection()) {
			old.begin(IsolationLevels.SNAPSHOT);
			// Fixes the snapshot.
			old.size();
			for (int i = 0; i < 8; i++) {
				int n = i;
				f.tx(con -> con.add(ex("other" + n), ex("q"), ex("o")));
			}
			old.add(ex("late"), ex("p"), ex("o"));
			old.commit();
		}

		RingTest.assertOneCyclePerSlot(f.logGraph(), 5);
		RingTest.assertOneValuePerEntry(f.logGraph());
		Rec last = f.last();
		assertEquals(10, last.revision());
		assertTrue(last.nodes().contains(ex("late")));
		assertEquals(LongStream.rangeClosed(6, 10).boxed().toList(), f.records().stream().map(Rec::revision).toList());

		f.tx(con -> con.add(ex("after"), ex("p"), ex("o")));
		assertEquals(11, f.last().revision());
		RingTest.assertOneCyclePerSlot(f.logGraph(), 5);
	}

	@Test
	void failedCommitLeavesNoRecordAndNoGap() {
		Fixture f = configure();
		FailingSail[] failing = new FailingSail[1];
		f.between = base -> failing[0] = new FailingSail(base);
		f.open();
		f.tx(con -> con.add(ex("a"), ex("p"), ex("o")));

		failing[0].failNextCommit = true;
		try (RepositoryConnection con = f.repo.getConnection()) {
			con.begin();
			con.add(ex("b"), ex("p"), ex("o"));
			assertThrows(RepositoryException.class, con::commit);
			con.rollback();
		}
		f.tx(con -> con.add(ex("c"), ex("p"), ex("o")));

		List<Rec> records = f.records();
		assertEquals(List.of(1L, 2L), records.stream().map(Rec::revision).toList());
		assertTrue(records.get(1).nodes().contains(ex("c")));
		assertTrue(records.stream().noneMatch(rec -> rec.nodes().contains(ex("b"))));
	}

	@Test
	void restartKeepsEpochAndContinues() {
		Fixture f = fixture();
		f.tx(con -> con.add(ex("a"), ex("p"), ex("o")));
		f.tx(con -> con.add(ex("b"), ex("p"), ex("o")));
		String epoch = f.state().epoch();

		f.reopen();
		f.tx(con -> con.add(ex("c"), ex("p"), ex("o")));

		assertEquals(epoch, f.state().epoch());
		assertEquals(List.of(1L, 2L, 3L), f.records().stream().map(Rec::revision).toList());
	}

	@Test
	void changingTheSlotCountRestartsTheLog() {
		Fixture f = configure();
		f.slots = 5;
		f.open();
		for (int i = 0; i < 3; i++) {
			int n = i;
			f.tx(con -> con.add(ex("s" + n), ex("p"), ex("o")));
		}
		String epoch = f.state().epoch();

		f.slots = 7;
		f.reopen();

		Fixture.State state = f.state();
		assertNotEquals(epoch, state.epoch());
		assertEquals(7, state.slots());
		assertTrue(f.records().isEmpty());
		f.tx(con -> con.add(ex("next"), ex("p"), ex("o")));
		assertEquals(List.of(4L), f.records().stream().map(Rec::revision).toList(), "revisions continue");
		assertEquals(4, f.dataSize());
	}

	@Test
	void wrappingAnExistingStoreKeepsItsData() {
		Sail plain = store.create(dir.resolve("store"));
		SailRepository repo = new SailRepository(plain);
		repo.init();
		try (RepositoryConnection con = repo.getConnection()) {
			con.begin();
			for (int i = 0; i < 100; i++) {
				con.add(ex("s" + i), ex("p"), ex("o"), ex("g"));
			}
			con.commit();
		} finally {
			repo.shutDown();
		}

		Fixture f = fixture();

		assertEquals(100, f.dataSize());
		assertTrue(f.records().isEmpty());
		IRI subject = ex("s42");
		assertTrue(f.<Boolean>read(con -> con.hasStatement(subject, ex("p"), ex("o"), false, ex("g"))));
	}

	/** Lets a test make the next commit fail below the change log. */
	static final class FailingSail extends SailWrapper {

		volatile boolean failNextCommit;

		FailingSail(Sail base) {
			super(base);
		}

		@Override
		public SailConnection getConnection() throws SailException {
			return new SailConnectionWrapper(super.getConnection()) {
				@Override
				public void commit() throws SailException {
					if (failNextCommit) {
						failNextCommit = false;
						throw new SailException("forced commit failure");
					}
					super.commit();
				}
			};
		}
	}
}
