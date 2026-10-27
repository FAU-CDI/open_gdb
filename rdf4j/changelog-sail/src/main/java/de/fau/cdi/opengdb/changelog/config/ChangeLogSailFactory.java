package de.fau.cdi.opengdb.changelog.config;

import org.eclipse.rdf4j.sail.Sail;
import org.eclipse.rdf4j.sail.config.SailConfigException;
import org.eclipse.rdf4j.sail.config.SailFactory;
import org.eclipse.rdf4j.sail.config.SailImplConfig;

import de.fau.cdi.opengdb.changelog.ChangeLogSail;

/**
 * Creates {@link ChangeLogSail} for the Sail type {@value #SAIL_TYPE}. RDF4J sets the configured
 * delegate as its base Sail.
 */
public class ChangeLogSailFactory implements SailFactory {

	public static final String SAIL_TYPE = "opengdb:ChangeLogSail";

	@Override
	public String getSailType() {
		return SAIL_TYPE;
	}

	@Override
	public SailImplConfig getConfig() {
		return new ChangeLogSailConfig();
	}

	@Override
	public Sail getSail(SailImplConfig config) throws SailConfigException {
		if (!SAIL_TYPE.equals(config.getType())) {
			throw new SailConfigException("Invalid Sail type: " + config.getType());
		}
		ChangeLogSail sail = new ChangeLogSail();
		if (config instanceof ChangeLogSailConfig changeLogConfig) {
			sail.setSlots(changeLogConfig.getSlots());
			sail.setMaxNodes(changeLogConfig.getMaxNodes());
			sail.setMaxTerms(changeLogConfig.getMaxTerms());
		}
		return sail;
	}
}
