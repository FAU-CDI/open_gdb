package de.fau.cdi.opengdb.changelog;

import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.LOG_GRAPH;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.isLogGraph;

import java.util.Comparator;
import java.util.Set;

import org.eclipse.rdf4j.common.iteration.CloseableIteration;
import org.eclipse.rdf4j.common.iteration.EmptyIteration;
import org.eclipse.rdf4j.common.iteration.FilterIteration;
import org.eclipse.rdf4j.common.order.StatementOrder;
import org.eclipse.rdf4j.model.IRI;
import org.eclipse.rdf4j.model.Resource;
import org.eclipse.rdf4j.model.Statement;
import org.eclipse.rdf4j.model.TripleTerm;
import org.eclipse.rdf4j.model.Value;
import org.eclipse.rdf4j.model.ValueFactory;
import org.eclipse.rdf4j.query.QueryEvaluationException;
import org.eclipse.rdf4j.query.algebra.evaluation.NativeTripleTermSource;
import org.eclipse.rdf4j.query.algebra.evaluation.TripleSource;

/**
 * The triple source of query evaluation without the log graph. A pattern that doesn't name a graph
 * ({@code GRAPH ?g}, the default graph) never matches log entries; a pattern that names the log
 * graph reads it.
 */
class LogHidingTripleSource implements TripleSource {

	private final TripleSource delegate;

	LogHidingTripleSource(TripleSource delegate) {
		this.delegate = delegate;
	}

	static TripleSource wrap(TripleSource source) {
		if (source instanceof LogHidingTripleSource) {
			return source;
		}
		return source instanceof NativeTripleTermSource tripleTerms ? new WithTripleTerms(tripleTerms)
				: new LogHidingTripleSource(source);
	}

	/**
	 * Drops the statements of the log graph. Only for reads over all graphs, so the iteration never
	 * holds a log entry that was asked for.
	 */
	static CloseableIteration<? extends Statement> withoutLog(CloseableIteration<? extends Statement> statements) {
		if (statements instanceof EmptyIteration) {
			return statements;
		}
		return new FilterIteration<Statement>(statements) {
			@Override
			protected boolean accept(Statement statement) {
				return !isLogGraph(statement.getContext());
			}

			@Override
			protected void handleClose() {
			}
		};
	}

	@Override
	public CloseableIteration<? extends Statement> getStatements(Resource subj, IRI pred, Value obj,
			Resource... contexts) throws QueryEvaluationException {
		CloseableIteration<? extends Statement> statements = delegate.getStatements(subj, pred, obj, contexts);
		return contexts.length == 0 ? withoutLog(statements) : statements;
	}

	@Override
	public long getStatementCount(Resource subj, IRI pred, Value obj, Resource... contexts)
			throws QueryEvaluationException {
		long count = delegate.getStatementCount(subj, pred, obj, contexts);
		return contexts.length == 0 ? count - delegate.getStatementCount(subj, pred, obj, LOG_GRAPH) : count;
	}

	@Override
	public CloseableIteration<? extends Statement> getStatements(StatementOrder order, Resource subj, IRI pred,
			Value obj, Resource... contexts) throws QueryEvaluationException {
		CloseableIteration<? extends Statement> statements = delegate.getStatements(order, subj, pred, obj,
				contexts);
		return contexts.length == 0 ? withoutLog(statements) : statements;
	}

	@Override
	public Set<StatementOrder> getSupportedOrders(Resource subj, IRI pred, Value obj, Resource... contexts) {
		return delegate.getSupportedOrders(subj, pred, obj, contexts);
	}

	@Override
	public Comparator<Value> getComparator() {
		return delegate.getComparator();
	}

	@Override
	public ValueFactory getValueFactory() {
		return delegate.getValueFactory();
	}

	/** Keeps RDF 1.2 triple terms available; the log holds none. */
	private static final class WithTripleTerms extends LogHidingTripleSource implements NativeTripleTermSource {

		private final NativeTripleTermSource tripleTerms;

		WithTripleTerms(NativeTripleTermSource tripleTerms) {
			super(tripleTerms);
			this.tripleTerms = tripleTerms;
		}

		@Override
		public CloseableIteration<? extends TripleTerm> getTripleTerms(Resource subj, IRI pred, Value obj)
				throws QueryEvaluationException {
			return tripleTerms.getTripleTerms(subj, pred, obj);
		}
	}
}
