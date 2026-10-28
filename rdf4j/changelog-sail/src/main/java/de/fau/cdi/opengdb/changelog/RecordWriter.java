package de.fau.cdi.opengdb.changelog;

import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.CLASS;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.CYCLE;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.EPOCH;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.GRAPH;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.INDEX;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.LAST_CYCLE;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.LAST_EVERYTHING_CYCLE;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.LAST_EVERYTHING_SLOT;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.LAST_SLOT;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.LOG_GRAPH;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.NODE;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.PREDICATE;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.SCOPE;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.SLOTS;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.STATE;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import org.eclipse.rdf4j.common.iteration.CloseableIteration;
import org.eclipse.rdf4j.model.IRI;
import org.eclipse.rdf4j.model.Literal;
import org.eclipse.rdf4j.model.Resource;
import org.eclipse.rdf4j.model.Statement;
import org.eclipse.rdf4j.model.Value;
import org.eclipse.rdf4j.model.impl.SimpleValueFactory;
import org.eclipse.rdf4j.model.util.Values;
import org.eclipse.rdf4j.sail.SailConnection;

/**
 * Reads and writes the log graph. Every call works on an active transaction of a connection that
 * is not wrapped by the change log, so nothing here is recorded or rejected.
 */
final class RecordWriter {

	/** Revision bounds of the records in the log. */
	record Bounds(long newest, long oldest) {
		static final Bounds NONE = new Bounds(0, 0);

		boolean isEmpty() {
			return newest == 0;
		}
	}

	private RecordWriter() {
	}

	/**
	 * Writes record {@code revision} into its slot and updates the summary index and the state.
	 * <p>
	 * {@code reader} sees the committed log under the commit lock; {@code target} gets the changes.
	 * All removals name exact statements and come before all additions: a pattern, or a removal
	 * after an addition to the log graph, would make RDF4J index the whole pending changeset of a
	 * large transaction.
	 *
	 * @return a new epoch if the state had none, otherwise null
	 */
	static String write(SailConnection target, SailConnection reader, Record record, long revision, long slots) {
		long index = revision % slots;
		long cycle = revision / slots;
		IRI slot = ChangeLogVocabulary.slot(index);
		Literal cycleLiteral = Values.literal(cycle);
		List<Statement> removals = new ArrayList<>();
		List<Statement> additions = new ArrayList<>();

		collect(reader, slot, null, removals);
		additions.add(log(slot, INDEX, Values.literal(index)));
		additions.add(log(slot, CYCLE, cycleLiteral));
		additions.add(log(slot, SCOPE, record.scope().iri));
		for (IRI node : record.nodes()) {
			additions.add(log(slot, NODE, node));
		}
		for (IRI predicate : record.predicates()) {
			additions.add(log(slot, PREDICATE, predicate));
			entry(reader, ChangeLogVocabulary.predicateEntry(predicate), PREDICATE, predicate, slot, cycleLiteral,
					removals, additions);
		}
		for (IRI type : record.classes()) {
			additions.add(log(slot, CLASS, type));
			entry(reader, ChangeLogVocabulary.classEntry(type), CLASS, type, slot, cycleLiteral, removals,
					additions);
		}
		for (IRI graph : record.graphs()) {
			additions.add(log(slot, GRAPH, graph));
			entry(reader, ChangeLogVocabulary.graphEntry(graph), GRAPH, graph, slot, cycleLiteral, removals,
					additions);
		}
		if (record.scope() == ChangeBuffer.Scope.EVERYTHING) {
			collect(reader, STATE, LAST_EVERYTHING_SLOT, removals);
			collect(reader, STATE, LAST_EVERYTHING_CYCLE, removals);
			additions.add(log(STATE, LAST_EVERYTHING_SLOT, slot));
			additions.add(log(STATE, LAST_EVERYTHING_CYCLE, cycleLiteral));
		}

		// An earlier version or a manual edit may have removed the state.
		String newEpoch = null;
		if (!reader.hasStatement(STATE, EPOCH, null, false, LOG_GRAPH)) {
			newEpoch = UUID.randomUUID().toString();
			additions.add(log(STATE, EPOCH, Values.literal(newEpoch)));
		}
		if (!reader.hasStatement(STATE, SLOTS, null, false, LOG_GRAPH)) {
			additions.add(log(STATE, SLOTS, Values.literal(slots)));
		}

		for (Statement statement : removals) {
			target.removeStatements(statement.getSubject(), statement.getPredicate(), statement.getObject(),
					LOG_GRAPH);
		}
		for (Statement statement : additions) {
			target.addStatement(statement.getSubject(), statement.getPredicate(), statement.getObject(), LOG_GRAPH);
		}
		return newEpoch;
	}

	/** Writes a new epoch and the slot count, replacing earlier values. */
	static String newEpoch(SailConnection con, long slots) {
		String epoch = UUID.randomUUID().toString();
		replace(con, STATE, EPOCH, Values.literal(epoch));
		replace(con, STATE, SLOTS, Values.literal(slots));
		return epoch;
	}

	/** The {@code cl:cycle} values of a slot. More than one means the ring is damaged. */
	static List<Long> cycles(SailConnection con, IRI slot) {
		return longs(con, slot, CYCLE);
	}

	static List<Long> longs(SailConnection con, Resource subject, IRI predicate) {
		List<Long> values = new ArrayList<>();
		try (CloseableIteration<? extends Statement> it = con.getStatements(subject, predicate, null, false,
				LOG_GRAPH)) {
			while (it.hasNext()) {
				Long value = asLong(it.next().getObject());
				if (value != null) {
					values.add(value);
				}
			}
		}
		return values;
	}

	static List<String> strings(SailConnection con, Resource subject, IRI predicate) {
		List<String> values = new ArrayList<>();
		try (CloseableIteration<? extends Statement> it = con.getStatements(subject, predicate, null, false,
				LOG_GRAPH)) {
			while (it.hasNext()) {
				Value object = it.next().getObject();
				if (object.isLiteral()) {
					values.add(object.stringValue());
				}
			}
		}
		return values;
	}

	/** Newest and oldest revision in the ring, computed with the given slot count. */
	static Bounds bounds(SailConnection con, long slots) {
		long newest = 0;
		long oldest = Long.MAX_VALUE;
		List<Statement> indexes = new ArrayList<>();
		try (CloseableIteration<? extends Statement> it = con.getStatements(null, INDEX, null, false, LOG_GRAPH)) {
			while (it.hasNext()) {
				indexes.add(it.next());
			}
		}
		for (Statement statement : indexes) {
			Long index = asLong(statement.getObject());
			if (index == null || !(statement.getSubject() instanceof IRI slot)) {
				continue;
			}
			for (long cycle : cycles(con, slot)) {
				long revision = cycle * slots + index;
				newest = Math.max(newest, revision);
				oldest = Math.min(oldest, revision);
			}
		}
		return newest == 0 ? Bounds.NONE : new Bounds(newest, oldest);
	}

	static boolean hasAny(SailConnection con) {
		return con.hasStatement(null, null, null, false, LOG_GRAPH);
	}

	private static void entry(SailConnection reader, IRI entry, IRI kind, IRI value, IRI slot, Literal cycle,
			List<Statement> removals, List<Statement> additions) {
		// Adding an existing statement changes nothing, so no read is needed to create the entry.
		additions.add(log(entry, kind, value));
		collect(reader, entry, LAST_SLOT, removals);
		collect(reader, entry, LAST_CYCLE, removals);
		additions.add(log(entry, LAST_SLOT, slot));
		additions.add(log(entry, LAST_CYCLE, cycle));
	}

	private static void collect(SailConnection reader, Resource subject, IRI predicate, List<Statement> into) {
		try (CloseableIteration<? extends Statement> it = reader.getStatements(subject, predicate, null, false,
				LOG_GRAPH)) {
			while (it.hasNext()) {
				into.add(it.next());
			}
		}
	}

	private static Statement log(Resource subject, IRI predicate, Value object) {
		return SimpleValueFactory.getInstance().createStatement(subject, predicate, object, LOG_GRAPH);
	}

	private static void replace(SailConnection con, Resource subject, IRI predicate, Value object) {
		con.removeStatements(subject, predicate, null, LOG_GRAPH);
		add(con, subject, predicate, object);
	}

	private static void add(SailConnection con, Resource subject, IRI predicate, Value object) {
		con.addStatement(subject, predicate, object, LOG_GRAPH);
	}

	private static Long asLong(Value value) {
		if (!(value instanceof Literal literal)) {
			return null;
		}
		try {
			return literal.longValue();
		} catch (NumberFormatException e) {
			return null;
		}
	}
}
