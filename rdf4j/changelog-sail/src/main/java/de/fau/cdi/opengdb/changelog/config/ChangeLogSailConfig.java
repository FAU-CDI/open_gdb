package de.fau.cdi.opengdb.changelog.config;

import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.MAX_NODES;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.MAX_TERMS;
import static de.fau.cdi.opengdb.changelog.ChangeLogVocabulary.SLOTS;

import java.util.Optional;

import org.eclipse.rdf4j.model.IRI;
import org.eclipse.rdf4j.model.Literal;
import org.eclipse.rdf4j.model.Model;
import org.eclipse.rdf4j.model.Resource;
import org.eclipse.rdf4j.model.util.Models;
import org.eclipse.rdf4j.model.util.Values;
import org.eclipse.rdf4j.sail.config.AbstractDelegatingSailImplConfig;
import org.eclipse.rdf4j.sail.config.SailConfigException;
import org.eclipse.rdf4j.sail.config.SailImplConfig;

import de.fau.cdi.opengdb.changelog.ChangeLogSail;
import de.fau.cdi.opengdb.changelog.ChangeLogVocabulary;

/**
 * Configuration of {@link ChangeLogSail}. The store below is the {@code config:delegate}. Optional
 * parameters: {@code cl:slots}, {@code cl:maxNodes}, {@code cl:maxTerms}.
 */
public class ChangeLogSailConfig extends AbstractDelegatingSailImplConfig {

	private Long slots;
	private Integer maxNodes;
	private Integer maxTerms;

	public ChangeLogSailConfig() {
		super(ChangeLogSailFactory.SAIL_TYPE);
	}

	public ChangeLogSailConfig(SailImplConfig delegate) {
		super(ChangeLogSailFactory.SAIL_TYPE, delegate);
	}

	public long getSlots() {
		return slots != null ? slots : ChangeLogSail.DEFAULT_SLOTS;
	}

	public void setSlots(long slots) {
		this.slots = slots;
	}

	public int getMaxNodes() {
		return maxNodes != null ? maxNodes : ChangeLogSail.DEFAULT_MAX_NODES;
	}

	public void setMaxNodes(int maxNodes) {
		this.maxNodes = maxNodes;
	}

	public int getMaxTerms() {
		return maxTerms != null ? maxTerms : ChangeLogSail.DEFAULT_MAX_TERMS;
	}

	public void setMaxTerms(int maxTerms) {
		this.maxTerms = maxTerms;
	}

	@Override
	public void validate() throws SailConfigException {
		super.validate();
		if (getSlots() < 1) {
			throw new SailConfigException("cl:slots must be at least 1");
		}
		if (getMaxNodes() < 0) {
			throw new SailConfigException("cl:maxNodes must not be negative");
		}
		if (getMaxTerms() < 1) {
			throw new SailConfigException("cl:maxTerms must be at least 1");
		}
	}

	@Override
	public Resource export(Model m) {
		Resource implNode = super.export(m);
		m.setNamespace(ChangeLogVocabulary.PREFIX, ChangeLogVocabulary.NAMESPACE);
		if (slots != null) {
			m.add(implNode, SLOTS, Values.literal(slots.longValue()));
		}
		if (maxNodes != null) {
			m.add(implNode, MAX_NODES, Values.literal(maxNodes.intValue()));
		}
		if (maxTerms != null) {
			m.add(implNode, MAX_TERMS, Values.literal(maxTerms.intValue()));
		}
		return implNode;
	}

	@Override
	public void parse(Model m, Resource implNode) throws SailConfigException {
		super.parse(m, implNode);
		number(m, implNode, SLOTS).ifPresent(value -> slots = value.longValue());
		number(m, implNode, MAX_NODES).ifPresent(value -> maxNodes = value.intValue());
		number(m, implNode, MAX_TERMS).ifPresent(value -> maxTerms = value.intValue());
	}

	private static Optional<Literal> number(Model m, Resource implNode, IRI predicate) {
		Optional<Literal> literal = Models.objectLiteral(m.getStatements(implNode, predicate, null));
		literal.ifPresent(value -> {
			try {
				value.longValue();
			} catch (NumberFormatException e) {
				throw new SailConfigException("Invalid value for <" + predicate + ">: " + value.getLabel(), e);
			}
		});
		return literal;
	}
}
