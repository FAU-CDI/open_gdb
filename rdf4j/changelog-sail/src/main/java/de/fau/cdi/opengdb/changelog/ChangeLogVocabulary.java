package de.fau.cdi.opengdb.changelog;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

import org.eclipse.rdf4j.model.IRI;
import org.eclipse.rdf4j.model.Resource;
import org.eclipse.rdf4j.model.Value;
import org.eclipse.rdf4j.model.util.Values;

/**
 * Terms of the change log. WissKI keeps the same namespace in one constant; tell the WissKI side
 * when anything here changes.
 */
public final class ChangeLogVocabulary {

	public static final String NAMESPACE = "tag:fau-cdi.github.io,2026:opengdb/changelog#";

	public static final String PREFIX = "cl";

	/** The reserved graph that holds the log. */
	public static final IRI LOG_GRAPH = Values.iri("tag:fau-cdi.github.io,2026:opengdb/changelog");

	public static final IRI STATE = cl("state");
	public static final IRI EPOCH = cl("epoch");
	public static final IRI SLOTS = cl("slots");
	public static final IRI LAST_EVERYTHING_SLOT = cl("lastEverythingSlot");
	public static final IRI LAST_EVERYTHING_CYCLE = cl("lastEverythingCycle");

	public static final IRI INDEX = cl("index");
	public static final IRI CYCLE = cl("cycle");
	public static final IRI SCOPE = cl("scope");
	public static final IRI NODE = cl("node");
	public static final IRI PREDICATE = cl("predicate");
	public static final IRI CLASS = cl("class");
	public static final IRI GRAPH = cl("graph");

	public static final IRI NODES = cl("Nodes");
	public static final IRI SUMMARY = cl("Summary");
	public static final IRI EVERYTHING = cl("Everything");

	/** Stands for the default graph (null context) in graph lists. */
	public static final IRI DEFAULT_GRAPH = cl("defaultGraph");

	public static final IRI LAST_SLOT = cl("lastSlot");
	public static final IRI LAST_CYCLE = cl("lastCycle");

	/** Sail configuration parameters, used as predicates in the repository config. */
	public static final IRI MAX_NODES = cl("maxNodes");
	public static final IRI MAX_TERMS = cl("maxTerms");

	private ChangeLogVocabulary() {
	}

	private static IRI cl(String localName) {
		return Values.iri(NAMESPACE, localName);
	}

	public static IRI slot(long index) {
		return cl("slot-" + index);
	}

	public static IRI predicateEntry(IRI predicate) {
		return cl("p-" + hash(predicate));
	}

	public static IRI classEntry(IRI type) {
		return cl("c-" + hash(type));
	}

	public static IRI graphEntry(IRI graph) {
		return cl("g-" + hash(graph));
	}

	public static boolean isLogGraph(Resource context) {
		return LOG_GRAPH.equals(context);
	}

	/** True for IRIs in the {@code cl:} namespace, such as slots and index entries. */
	public static boolean inNamespace(Value value) {
		return value != null && value.isIRI() && value.stringValue().startsWith(NAMESPACE);
	}

	/** First 16 hex digits of the SHA-256 of the IRI. */
	static String hash(IRI iri) {
		try {
			byte[] digest = MessageDigest.getInstance("SHA-256")
					.digest(iri.stringValue().getBytes(StandardCharsets.UTF_8));
			return HexFormat.of().formatHex(digest, 0, 8);
		} catch (NoSuchAlgorithmException e) {
			// Every Java platform has SHA-256.
			throw new IllegalStateException(e);
		}
	}
}
