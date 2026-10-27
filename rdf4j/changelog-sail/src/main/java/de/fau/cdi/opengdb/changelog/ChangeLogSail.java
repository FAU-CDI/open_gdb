package de.fau.cdi.opengdb.changelog;

import java.util.List;
import java.util.concurrent.Semaphore;

import org.eclipse.rdf4j.sail.Sail;
import org.eclipse.rdf4j.sail.SailConnection;
import org.eclipse.rdf4j.sail.SailException;
import org.eclipse.rdf4j.sail.helpers.SailWrapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Records every committed transaction that wrote statements in the reserved graph
 * {@link ChangeLogVocabulary#LOG_GRAPH} of the same repository, in the same transaction.
 * <p>
 * The connection wrapper records the arguments of the write calls. It doesn't use a
 * {@code SailConnectionListener}, so the store below keeps its fast paths. An inferencer below this
 * Sail isn't seen; inferred changes follow from the explicit ones that are recorded.
 */
public class ChangeLogSail extends SailWrapper {

	public static final long DEFAULT_SLOTS = 2000;
	public static final int DEFAULT_MAX_NODES = 200;
	public static final int DEFAULT_MAX_TERMS = 100;

	private static final Logger logger = LoggerFactory.getLogger(ChangeLogSail.class);

	private long slots = DEFAULT_SLOTS;
	private int maxNodes = DEFAULT_MAX_NODES;
	private int maxTerms = DEFAULT_MAX_TERMS;

	/**
	 * Held from writing a record until its transaction has committed or ended, so that revisions
	 * follow the commit order. A semaphore, not a lock, because the end of a transaction may run on
	 * another thread than its prepare.
	 */
	private final Semaphore commitLock = new Semaphore(1, true);

	// Guarded by commitLock once the Sail is initialized.
	private long lastRevision;
	/** Oldest revision in the ring of the current epoch, 0 before the first record. */
	private long firstRevision;
	private String epoch;
	/** A record after a successful commit got lost; the next record says "everything". */
	private boolean pendingEverything;

	public ChangeLogSail() {
	}

	public ChangeLogSail(Sail baseSail) {
		super(baseSail);
	}

	public long getSlots() {
		return slots;
	}

	public void setSlots(long slots) {
		if (slots < 1) {
			throw new IllegalArgumentException("slots must be at least 1");
		}
		this.slots = slots;
	}

	public int getMaxNodes() {
		return maxNodes;
	}

	public void setMaxNodes(int maxNodes) {
		if (maxNodes < 0) {
			throw new IllegalArgumentException("maxNodes must not be negative");
		}
		this.maxNodes = maxNodes;
	}

	public int getMaxTerms() {
		return maxTerms;
	}

	public void setMaxTerms(int maxTerms) {
		if (maxTerms < 1) {
			throw new IllegalArgumentException("maxTerms must be at least 1");
		}
		this.maxTerms = maxTerms;
	}

	@Override
	public void init() throws SailException {
		super.init();
		initLog();
	}

	@Override
	public SailConnection getConnection() throws SailException {
		verifyBaseSailSet();
		return new ChangeLogSailConnection(this, getBaseSail().getConnection());
	}

	/**
	 * Writes the state if it is missing. A changed slot count restarts the log with a new epoch; the
	 * revisions continue.
	 */
	private void initLog() {
		try (SailConnection con = getBaseSail().getConnection()) {
			con.begin();
			List<Long> storedSlots = RecordWriter.longs(con, ChangeLogVocabulary.STATE, ChangeLogVocabulary.SLOTS);
			List<String> epochs = RecordWriter.strings(con, ChangeLogVocabulary.STATE, ChangeLogVocabulary.EPOCH);
			Long stored = storedSlots.size() == 1 ? storedSlots.get(0) : null;
			RecordWriter.Bounds bounds = stored != null && stored > 0 ? RecordWriter.bounds(con, stored)
					: RecordWriter.Bounds.NONE;
			lastRevision = bounds.newest();

			if (stored == null || stored != slots) {
				if (RecordWriter.hasAny(con)) {
					logger.info("Change log: slot count changed from {} to {}, starting a new epoch", stored, slots);
				}
				con.clear(ChangeLogVocabulary.LOG_GRAPH);
				epoch = RecordWriter.newEpoch(con, slots);
				firstRevision = 0;
			} else {
				if (epochs.size() == 1) {
					epoch = epochs.get(0);
				} else {
					epoch = RecordWriter.newEpoch(con, slots);
				}
				firstRevision = bounds.oldest();
			}
			con.commit();
		}
		logger.info("Change log: epoch {}, {} slots, last revision {}", epoch, slots, lastRevision);
	}

	void lock() {
		try {
			commitLock.acquire();
		} catch (InterruptedException e) {
			Thread.currentThread().interrupt();
			throw new SailException("Interrupted while waiting to write the change log", e);
		}
	}

	void unlock() {
		commitLock.release();
	}

	// The accessors below are only called while holding the commit lock.

	long lastRevision() {
		return lastRevision;
	}

	long firstRevision() {
		return firstRevision;
	}

	boolean pendingEverything() {
		return pendingEverything;
	}

	void recordLost() {
		pendingEverything = true;
	}

	void recordWritten(long revision, Record record, String newEpoch) {
		lastRevision = revision;
		if (firstRevision == 0) {
			firstRevision = revision;
		}
		if (record.forced()) {
			pendingEverything = false;
		}
		if (newEpoch != null) {
			epoch = newEpoch;
		}
	}

	String epoch() {
		return epoch;
	}
}
