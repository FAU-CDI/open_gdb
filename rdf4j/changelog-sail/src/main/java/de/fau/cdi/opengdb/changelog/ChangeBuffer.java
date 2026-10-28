package de.fau.cdi.opengdb.changelog;

import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.Set;

import org.eclipse.rdf4j.model.IRI;
import org.eclipse.rdf4j.model.Resource;
import org.eclipse.rdf4j.model.Value;
import org.eclipse.rdf4j.model.vocabulary.RDF;

/**
 * What one transaction wrote, at the level of detail its size allows. There is no net computation:
 * adding and removing the same statement is recorded, too.
 */
final class ChangeBuffer {

	/** Level of detail. The order matters: a buffer only moves to a later scope. */
	enum Scope {
		NODES(ChangeLogVocabulary.NODES),
		SUMMARY(ChangeLogVocabulary.SUMMARY),
		EVERYTHING(ChangeLogVocabulary.EVERYTHING);

		final IRI iri;

		Scope(IRI iri) {
			this.iri = iri;
		}
	}

	private final int maxNodes;
	private final int maxTerms;

	private Scope scope = Scope.NODES;
	private boolean changed;
	private final Set<IRI> nodes = new LinkedHashSet<>();
	private final Set<IRI> predicates = new LinkedHashSet<>();
	private final Set<IRI> classes = new LinkedHashSet<>();
	private final Set<IRI> graphs = new LinkedHashSet<>();
	/** Only with {@link Scope#EVERYTHING}: the graph list overflowed or a call covered all graphs. */
	private boolean allGraphs;

	ChangeBuffer(int maxNodes, int maxTerms) {
		this.maxNodes = maxNodes;
		this.maxTerms = maxTerms;
	}

	void reset() {
		scope = Scope.NODES;
		changed = false;
		nodes.clear();
		predicates.clear();
		classes.clear();
		graphs.clear();
		allGraphs = false;
	}

	/**
	 * A statement that was added or removed.
	 *
	 * @param contexts the contexts as given to the write call; none stands for the default graph.
	 */
	void statement(Resource subject, IRI predicate, Value object, Resource... contexts) {
		changed = true;
		if (subject.isIRI()) {
			node((IRI) subject);
		} else {
			// Blank nodes and triple terms can't be resolved to entities by IRI.
			downgrade(Scope.SUMMARY);
		}
		if (object.isIRI()) {
			node((IRI) object);
		}
		predicate(predicate);
		if (RDF.TYPE.equals(predicate) && object.isIRI()) {
			type((IRI) object);
		}
		if (contexts.length == 0) {
			graph(ChangeLogVocabulary.DEFAULT_GRAPH);
		}
		for (Resource context : contexts) {
			if (context == null) {
				graph(ChangeLogVocabulary.DEFAULT_GRAPH);
			} else if (context.isIRI()) {
				graph((IRI) context);
			}
		}
	}

	/** A remove with only the predicate bound. */
	void predicatePattern(IRI predicate, Resource... contexts) {
		if (RDF.TYPE.equals(predicate)) {
			// Removed types change bundle membership of unknown entities.
			everything(contexts);
			return;
		}
		changed = true;
		downgrade(Scope.SUMMARY);
		predicate(predicate);
		if (contexts.length == 0) {
			graph(ChangeLogVocabulary.DEFAULT_GRAPH);
		}
		for (Resource context : contexts) {
			if (context == null) {
				graph(ChangeLogVocabulary.DEFAULT_GRAPH);
			} else if (context.isIRI()) {
				graph((IRI) context);
			}
		}
	}

	/**
	 * Cleared graphs, or a remove that is unbound except for the graph.
	 *
	 * @param contexts the cleared graphs; none means all graphs.
	 */
	void everything(Resource... contexts) {
		changed = true;
		downgrade(Scope.EVERYTHING);
		if (contexts.length == 0) {
			allGraphs();
		}
		for (Resource context : contexts) {
			if (context == null) {
				graph(ChangeLogVocabulary.DEFAULT_GRAPH);
			} else if (context.isIRI()) {
				graph((IRI) context);
			} else {
				// A blank-node graph can't be named in the list.
				allGraphs();
			}
		}
	}

	boolean isChanged() {
		return changed;
	}

	Scope scope() {
		return scope;
	}

	Set<IRI> nodes() {
		return Collections.unmodifiableSet(nodes);
	}

	Set<IRI> predicates() {
		return Collections.unmodifiableSet(predicates);
	}

	Set<IRI> classes() {
		return Collections.unmodifiableSet(classes);
	}

	/** The graphs. Empty with {@link Scope#EVERYTHING} means all graphs. */
	Set<IRI> graphs() {
		return Collections.unmodifiableSet(graphs);
	}

	private void node(IRI iri) {
		if (scope != Scope.NODES) {
			return;
		}
		nodes.add(iri);
		if (nodes.size() > maxNodes) {
			downgrade(Scope.SUMMARY);
		}
	}

	private void predicate(IRI iri) {
		if (scope == Scope.EVERYTHING) {
			return;
		}
		predicates.add(iri);
		if (predicates.size() > maxTerms) {
			downgrade(Scope.EVERYTHING);
		}
	}

	private void type(IRI iri) {
		if (scope == Scope.EVERYTHING) {
			return;
		}
		classes.add(iri);
		if (classes.size() > maxTerms) {
			downgrade(Scope.EVERYTHING);
		}
	}

	private void graph(IRI iri) {
		if (allGraphs) {
			return;
		}
		graphs.add(iri);
		if (graphs.size() > maxTerms) {
			downgrade(Scope.EVERYTHING);
			allGraphs();
		}
	}

	private void allGraphs() {
		allGraphs = true;
		graphs.clear();
	}

	private void downgrade(Scope target) {
		if (target.ordinal() <= scope.ordinal()) {
			return;
		}
		scope = target;
		nodes.clear();
		if (scope == Scope.EVERYTHING) {
			predicates.clear();
			classes.clear();
		}
	}
}
