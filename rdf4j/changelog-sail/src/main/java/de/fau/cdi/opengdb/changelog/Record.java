package de.fau.cdi.opengdb.changelog;

import java.util.List;

import org.eclipse.rdf4j.model.IRI;

/**
 * One record, copied from a {@link ChangeBuffer} so that it can still be written after the
 * transaction's buffer was reset.
 *
 * @param scope      the level of detail
 * @param nodes      only with {@code cl:Nodes}
 * @param predicates not with {@code cl:Everything}
 * @param classes    not with {@code cl:Everything}
 * @param graphs     with {@code cl:Everything}, empty means all graphs
 * @param forced     the scope was raised to "everything" because an earlier record got lost
 */
record Record(ChangeBuffer.Scope scope, List<IRI> nodes, List<IRI> predicates, List<IRI> classes,
		List<IRI> graphs, boolean forced) {

	static Record of(ChangeBuffer buffer, boolean forceEverything) {
		if (forceEverything) {
			return new Record(ChangeBuffer.Scope.EVERYTHING, List.of(), List.of(), List.of(), List.of(), true);
		}
		return new Record(buffer.scope(), List.copyOf(buffer.nodes()), List.copyOf(buffer.predicates()),
				List.copyOf(buffer.classes()), List.copyOf(buffer.graphs()), false);
	}
}
