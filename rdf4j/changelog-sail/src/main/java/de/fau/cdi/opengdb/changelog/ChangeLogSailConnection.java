package de.fau.cdi.opengdb.changelog;

import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.LOG_GRAPH;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.inNamespace;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.isLogGraph;

import java.util.ArrayList;
import java.util.List;

import org.eclipse.rdf4j.common.iteration.CloseableIteration;
import org.eclipse.rdf4j.common.transaction.IsolationLevel;
import org.eclipse.rdf4j.model.IRI;
import org.eclipse.rdf4j.model.Resource;
import org.eclipse.rdf4j.model.Statement;
import org.eclipse.rdf4j.model.Value;
import org.eclipse.rdf4j.model.util.Values;
import org.eclipse.rdf4j.sail.SailConnection;
import org.eclipse.rdf4j.sail.SailException;
import org.eclipse.rdf4j.sail.UpdateContext;
import org.eclipse.rdf4j.sail.helpers.SailConnectionWrapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Records the arguments of the write calls and writes one record per transaction in
 * {@link #prepare()}, or in {@link #commit()} if the transaction wasn't prepared.
 */
public class ChangeLogSailConnection extends SailConnectionWrapper {

	private static final Logger logger = LoggerFactory.getLogger(ChangeLogSailConnection.class);

	private enum RecordState {
		/** No record written yet. */
		NONE,
		/** The record is part of this transaction. */
		IN_TRANSACTION,
		/** The transaction reads an old snapshot; the record is written right after the commit. */
		DEFERRED
	}

	private final ChangeLogSail sail;
	private final ChangeBuffer buffer;

	private boolean holdsLock;
	private RecordState recordState = RecordState.NONE;
	private Record record;
	private long revision;
	private String newEpoch;

	ChangeLogSailConnection(ChangeLogSail sail, SailConnection wrappedCon) {
		super(wrappedCon);
		this.sail = sail;
		this.buffer = new ChangeBuffer(sail.getMaxNodes(), sail.getMaxTerms());
	}

	@Override
	public void begin() throws SailException {
		resetTransaction();
		super.begin();
	}

	@Override
	public void begin(IsolationLevel level) throws SailException {
		resetTransaction();
		super.begin(level);
	}

	// --- Write calls ---------------------------------------------------------------------------

	@Override
	public void addStatement(Resource subj, IRI pred, Value obj, Resource... contexts) throws SailException {
		rejectLogGraph(contexts);
		super.addStatement(subj, pred, obj, contexts);
		buffer.statement(subj, pred, obj, contexts);
	}

	@Override
	public void addStatement(UpdateContext modify, Resource subj, IRI pred, Value obj, Resource... contexts)
			throws SailException {
		rejectLogGraph(contexts);
		super.addStatement(modify, subj, pred, obj, contexts);
		buffer.statement(subj, pred, obj, contexts);
	}

	@Override
	public void removeStatements(Resource subj, IRI pred, Value obj, Resource... contexts) throws SailException {
		remove(null, subj, pred, obj, contexts);
	}

	@Override
	public void removeStatement(UpdateContext modify, Resource subj, IRI pred, Value obj, Resource... contexts)
			throws SailException {
		remove(modify, subj, pred, obj, contexts);
	}

	@Override
	public void clear(Resource... contexts) throws SailException {
		if (contexts.length == 0) {
			// CLEAR ALL: every graph but the log, and the default graph.
			List<Resource> graphs = new ArrayList<>();
			try (CloseableIteration<? extends Resource> it = getWrappedConnection().getContextIDs()) {
				while (it.hasNext()) {
					Resource context = it.next();
					if (!isLogGraph(context)) {
						graphs.add(context);
					}
				}
			}
			graphs.add(null);
			super.clear(graphs.toArray(new Resource[0]));
			buffer.everything();
			return;
		}
		// RDF4J's CLEAR/DROP NAMED clear the graphs one by one, the log graph included; skip it.
		Resource[] rest = withoutLogGraph(contexts);
		if (rest.length == 0) {
			return;
		}
		super.clear(rest);
		buffer.everything(rest);
	}

	/**
	 * Handles both remove calls. {@code modify} is null for the variant without update context.
	 */
	private void remove(UpdateContext modify, Resource subj, IRI pred, Value obj, Resource... contexts) {
		rejectLogGraph(contexts);

		if (subj != null && pred != null && obj != null) {
			if (contexts.length == 0 && inNamespace(subj)) {
				// A log entry matched by a pattern over all graphs, e.g. DELETE WHERE { ?s ?p ?o }.
				return;
			}
			delegateRemove(modify, subj, pred, obj, contexts);
			buffer.statement(subj, pred, obj, contexts);
			return;
		}

		if (subj != null || obj != null) {
			// Few matches, because a subject or object is bound. Remove each in its own graph so that
			// the log graph is skipped and the record lists what was removed.
			List<Statement> matches = new ArrayList<>();
			try (CloseableIteration<? extends Statement> it = getWrappedConnection().getStatements(subj, pred, obj,
					false, contexts)) {
				while (it.hasNext()) {
					Statement statement = it.next();
					if (!isLogGraph(statement.getContext())) {
						matches.add(statement);
					}
				}
			}
			for (Statement statement : matches) {
				Resource[] context = { statement.getContext() };
				delegateRemove(modify, statement.getSubject(), statement.getPredicate(), statement.getObject(),
						context);
				buffer.statement(statement.getSubject(), statement.getPredicate(), statement.getObject(), context);
			}
			return;
		}

		if (pred != null) {
			if (inNamespace(pred)) {
				throw new SailException("The predicate <" + pred + "> belongs to the OpenGDB change log");
			}
			// RDF4J keeps its fast path for the pattern.
			delegateRemove(modify, null, pred, null, contexts);
			buffer.predicatePattern(pred, contexts);
			return;
		}

		clear(contexts);
	}

	private void delegateRemove(UpdateContext modify, Resource subj, IRI pred, Value obj, Resource... contexts) {
		if (modify == null) {
			super.removeStatements(subj, pred, obj, contexts);
		} else {
			super.removeStatement(modify, subj, pred, obj, contexts);
		}
	}

	private static void rejectLogGraph(Resource... contexts) {
		for (Resource context : contexts) {
			if (isLogGraph(context)) {
				throw new SailException("The graph <" + LOG_GRAPH + "> is reserved for the OpenGDB change log");
			}
		}
	}

	private static Resource[] withoutLogGraph(Resource... contexts) {
		List<Resource> rest = new ArrayList<>(contexts.length);
		for (Resource context : contexts) {
			if (!isLogGraph(context)) {
				rest.add(context);
			}
		}
		return rest.toArray(new Resource[0]);
	}

	// --- Transaction end -----------------------------------------------------------------------

	@Override
	public void prepare() throws SailException {
		writeRecord();
		super.prepare();
	}

	@Override
	public void commit() throws SailException {
		boolean committed = false;
		try {
			writeRecord();
			super.commit();
			committed = true;
			afterCommit();
		} finally {
			try {
				if (committed) {
					resetTransaction();
				} else {
					// The transaction is still open; a retry writes the record again.
					recordState = RecordState.NONE;
				}
			} finally {
				releaseLock();
			}
		}
	}

	@Override
	public void rollback() throws SailException {
		try {
			super.rollback();
		} finally {
			try {
				resetTransaction();
			} finally {
				releaseLock();
			}
		}
	}

	@Override
	public void close() throws SailException {
		try {
			super.close();
		} finally {
			try {
				resetTransaction();
			} finally {
				// An abandoned transaction must not keep the lock.
				releaseLock();
			}
		}
	}

	/**
	 * Writes the record for this transaction, unless nothing was recorded. Takes the commit lock and
	 * keeps it until the transaction ends.
	 */
	private void writeRecord() {
		if (recordState != RecordState.NONE || !buffer.isChanged()) {
			return;
		}
		if (!holdsLock) {
			sail.lock();
			holdsLock = true;
		}
		long slots = sail.getSlots();
		revision = sail.lastRevision() + 1;
		record = Record.of(buffer, sail.pendingEverything());
		newEpoch = null;
		if (seesNewestRecord(revision, slots)) {
			// Under the lock, a separate connection reads the newest log, without making RDF4J index
			// the pending changes of this transaction.
			try (SailConnection reader = sail.getBaseSail().getConnection()) {
				newEpoch = RecordWriter.write(getWrappedConnection(), reader, record, revision, slots);
			}
			recordState = RecordState.IN_TRANSACTION;
		} else {
			recordState = RecordState.DEFERRED;
		}
	}

	/**
	 * Stale-read guard. True if this transaction sees the record before {@code revision}, so its
	 * snapshot holds the newest log. A {@code SNAPSHOT} or {@code SERIALIZABLE} transaction reads
	 * from its start and may miss later records; removing from that view would leave two cycles in a
	 * slot or two values in a summary entry. Only exact lookups, which don't index the pending
	 * changes.
	 */
	private boolean seesNewestRecord(long revision, long slots) {
		long previous = revision - 1;
		if (sail.firstRevision() == 0 || previous < sail.firstRevision()) {
			// The first record of the epoch; the log only holds the state written at start-up.
			return true;
		}
		return getWrappedConnection().hasStatement(ChangeLogVocabulary.slot(previous % slots),
				ChangeLogVocabulary.CYCLE, Values.literal(previous / slots), false, LOG_GRAPH);
	}

	private void afterCommit() {
		switch (recordState) {
		case IN_TRANSACTION -> {
			sail.recordWritten(revision, record, newEpoch);
			logRecord();
		}
		case DEFERRED -> {
			// Still under the lock, so no other record can come in between.
			try (SailConnection con = sail.getBaseSail().getConnection()) {
				con.begin();
				String epoch = RecordWriter.write(con, con, record, revision, sail.getSlots());
				con.commit();
				sail.recordWritten(revision, record, epoch);
				logger.debug("Change log: the transaction read an old snapshot; revision {} written after the commit",
						revision);
				logRecord();
			} catch (RuntimeException e) {
				// The data is committed. The revision stays free and its record says "everything".
				sail.recordLost();
				logger.warn("Change log: could not write revision {} after the commit; the next record covers"
						+ " everything", revision, e);
			}
		}
		case NONE -> {
		}
		}
	}

	private void logRecord() {
		if (logger.isDebugEnabled()) {
			logger.debug("Change log: revision {} ({}): {} nodes, {} predicates, {} classes, {} graphs", revision,
					record.scope(), record.nodes().size(), record.predicates().size(), record.classes().size(),
					record.graphs().size());
		}
	}

	private void resetTransaction() {
		buffer.reset();
		recordState = RecordState.NONE;
		record = null;
		newEpoch = null;
	}

	private void releaseLock() {
		if (holdsLock) {
			holdsLock = false;
			sail.unlock();
		}
	}
}
